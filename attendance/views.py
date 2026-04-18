from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.utils import timezone

from .models import (
    TrainerAttendanceRecord,
    ClassSessionAttendance,
    PrivateClassAttendance,
)
from accounts.models import User
from classes.models import ClassSession, PrivateClass, ClassBooking
from pool.models import Pool, TrainerPoolAssignment

from datetime import date, datetime, timedelta


# Create your views here.
def _get_substitute_candidates(pool, today, exclude_trainer_ids=None):
    exclude_trainer_ids = exclude_trainer_ids or []

    assigned_trainer_ids  = TrainerPoolAssignment.objects.filter(
        pool=pool,
        is_active=True,
        start_date__lte=today,
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=today)
    ).values_list('trainer_id', flat=True)

    present_trainer_ids = TrainerAttendanceRecord.objects.filter(
        date=today,
        status='present',
    ).filter(trainer_id__in=assigned_trainer_ids ).values_list('trainer_id', flat=True)

    trainers = User.objects.filter(
        role='trainer',
        is_active=True,
        pk__in=assigned_trainer_ids,
    ).filter(
        pk__in=present_trainer_ids,
    ).exclude(pk__in=exclude_trainer_ids)

    candidates = []

    for trainer in trainers:
        candidates.append({
            'trainer': trainer,
            'is_available' : True,
            'conflict_label': 'Available',
        })

    return candidates

@login_required
def select_trainer_for_attendance(request):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    today = date.today()
    trainers = User.objects.filter(role='trainer', is_active=True).order_by('full_name', 'username')
    q = (request.GET.get('q') or '').strip()
    status_filter = (request.GET.get('status') or '').strip().lower()

    if q:
        trainers = trainers.filter(
            Q(username__icontains=q) |
            Q(full_name__icontains=q) |
            Q(email__icontains=q)
        )

    attendance_map = {}
    attendance_records = TrainerAttendanceRecord.objects.filter(date=today).select_related('trainer')
    for record in attendance_records:
        attendance_map[record.trainer_id] = record.status

    trainer_rows = []
    for trainer in trainers:
        row_status = attendance_map.get(trainer.pk, 'pending')
        if status_filter and row_status != status_filter:
            continue

        trainer_rows.append({
            'trainer': trainer,
            'status': row_status,
        })
    return render(
        request,
        'dashboards/admin/attendance/trainer/select_trainer_for_attendance.html',
        {'trainer_rows': trainer_rows, 'today': today},
    )


@login_required
def mark_trainer_attendance(request, trainer_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('select_trainer_for_attendance')

    trainer = get_object_or_404(User, pk=trainer_id, role='trainer')

    today = date.today()

    if request.method == 'POST':
        try:
            date_str = datetime.strptime(request.POST.get('date', ''), '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'Invalid date.')
            return redirect('mark_trainer_attendance', trainer_id=trainer_id)

        status = request.POST.get('status')
        if status not in {'present', 'absent'}:
            messages.error(request, 'Invalid attendance status.')
            return redirect('mark_trainer_attendance', trainer_id=trainer_id)

        if date_str != today:
            messages.error(request, 'You can only mark attendance for today.')
            return redirect('mark_trainer_attendance', trainer_id=trainer_id)
        
        if date_str.weekday() >= 5:
            messages.error(request, "Attendance cannot be marked on weekends.")
            return redirect('mark_trainer_attendance', trainer_id=trainer_id)

        substitute_group_qs = ClassSession.objects.filter(
            substitute_trainer=trainer,
            start_date__lte=today,
            end_date__gte=today,
            is_cancelled=False,
        ).select_related('pool')
        substitute_private_qs = PrivateClass.objects.filter(
            substitute_trainer=trainer,
            start_date__lte=today,
            end_date__gte=today,
            is_cancelled=False,
        ).select_related('pool', 'user')
        has_substitute_assignments_today = substitute_group_qs.exists() or substitute_private_qs.exists()
        confirm_clear_substitute = request.POST.get('confirm_clear_substitute') == '1'

        if status == 'absent' and has_substitute_assignments_today and not confirm_clear_substitute:
            messages.warning(
                request,
                'This trainer is currently assigned as substitute today. Confirm to mark absent and clear substitute assignments.',
            )
            today_record = TrainerAttendanceRecord.objects.filter(trainer=trainer, date=today).first()
            return render(
                request,
                'dashboards/admin/attendance/trainer/mark_trainer_attendance.html',
                {
                    'trainer': trainer,
                    'today': today,
                    'today_record': today_record,
                    'require_substitute_clear_confirmation': True,
                },
            )

        attendance_record, created = TrainerAttendanceRecord.objects.update_or_create(
            trainer=trainer, date=date_str, defaults={'status': status}
        )

        if attendance_record.status in {'present', 'absent'}:
            class_sessions_updated = substitute_group_qs.update(substitute_trainer=None)
            if class_sessions_updated:
                if attendance_record.status == 'absent':
                    messages.info(request, 'Trainer was marked absent, so substitute assignments for group classes were cleared.')
                else:
                    messages.info(request, 'Trainer substitute assignments for group classes were cleared for today.')

            private_classes_updated = substitute_private_qs.update(substitute_trainer=None)
            if private_classes_updated:
                if attendance_record.status == 'absent':
                    messages.info(request, 'Trainer was marked absent, so substitute assignments for private classes were cleared.')
                else:
                    messages.info(request, 'Trainer substitute assignments for private classes were cleared for today.')

        if created:
            messages.success(request, 'Trainer attendance marked successfully.')
        else:
            messages.success(request, 'Trainer attendance updated successfully.')

        return redirect('mark_trainer_attendance', trainer_id=trainer_id)

    today_record = TrainerAttendanceRecord.objects.filter(trainer=trainer, date=today).first()
    return render(
        request,
        'dashboards/admin/attendance/trainer/mark_trainer_attendance.html',
        {'trainer': trainer, 'today': today, 'today_record': today_record},
    )


@login_required
def admin_todays_classes(request):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    today = timezone.localdate()
    is_weekday = today.weekday() < 5

    class_sessions = ClassSession.objects.none()
    private_classes = PrivateClass.objects.none()
    if is_weekday:
        class_sessions = ClassSession.objects.filter(
            is_cancelled=False,
            start_date__lte=today,
            end_date__gte=today,
        ).select_related(
            'trainer',
            'substitute_trainer',
            'pool',
            'class_type',
        ).order_by('start_time')

        private_classes = PrivateClass.objects.filter(
            is_cancelled=False,
            start_date__lte=today,
            end_date__gte=today,
        ).select_related(
            'trainer',
            'substitute_trainer',
            'pool',
            'user',
        ).order_by('start_time')

    q = (request.GET.get('q') or '').strip()
    private_or_group = (request.GET.get('private_or_group') or '').strip()

    if q:
        class_sessions = class_sessions.filter(
            Q(class_name__icontains=q) |
            Q(pool__name__icontains=q) |
            Q(class_type__name__icontains=q) |
            Q(trainer__full_name__icontains=q) |
            Q(trainer__username__icontains=q) |
            Q(substitute_trainer__full_name__icontains=q) |
            Q(substitute_trainer__username__icontains=q)
        )
        private_classes = private_classes.filter(
            Q(user__full_name__icontains=q) |
            Q(user__username__icontains=q) |
            Q(pool__name__icontains=q) |
            Q(trainer__full_name__icontains=q) |
            Q(trainer__username__icontains=q) |
            Q(substitute_trainer__full_name__icontains=q) |
            Q(substitute_trainer__username__icontains=q)
        )

    if private_or_group == 'group':
        private_classes = PrivateClass.objects.none()
    elif private_or_group == 'private':
        class_sessions = ClassSession.objects.none()

    context = {
        'today': today,
        'is_weekday': is_weekday,
        'class_sessions': class_sessions,
        'private_classes': private_classes,
    }

    if not is_weekday:
        context['weekend'] = "It is weekend today. No classes are scheduled for today."

    return render(request, 'dashboards/admin/todays_classes.html', context)


@login_required
def select_class_for_attendance(request):
    if request.user.role != 'trainer':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    today = date.today()
    ongoing_classes = ClassSession.objects.filter(
        (Q(trainer=request.user) | Q(substitute_trainer=request.user)),
        start_date__lte=today,
        end_date__gte=today,
        is_cancelled=False,
    ).order_by('start_time')
    q = (request.GET.get('q') or '').strip()
    if q:
        ongoing_classes = ongoing_classes.filter(
            Q(class_name__icontains=q) |
            Q(pool__name__icontains=q) |
            Q(class_type__name__icontains=q)
        )

    return render(
        request,
        'dashboards/trainer/attendance/select_class_for_attendance.html',
        {'ongoing_classes': ongoing_classes, 'today': today},
    )


@login_required
def select_student_for_attendance(request, class_session_id):
    if request.user.role != 'trainer':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    class_session = get_object_or_404(ClassSession, id=class_session_id)

    if class_session.trainer != request.user and class_session.substitute_trainer != request.user:
        messages.error(request, 'You can only mark attendance for your own classes or subsitute class.')
        return redirect('select_class_for_attendance')

    today = date.today()
    bookings = ClassBooking.objects.filter(class_session=class_session, is_cancelled=False).select_related('user')
    q = (request.GET.get('q') or '').strip()
    if q:
        bookings = bookings.filter(
            Q(user__username__icontains=q) |
            Q(user__full_name__icontains=q) |
            Q(user__email__icontains=q)
        )
    attendance_today = {}
    attendance_records = ClassSessionAttendance.objects.filter(class_session=class_session, date=today)
    for record in attendance_records:
        attendance_today[record.student_id] = record.status

    booking_rows = []
    for booking in bookings:
        booking_rows.append({
            'booking': booking,
            'status': attendance_today.get(booking.user_id, 'pending'),
        })

    return render(
        request,
        'dashboards/trainer/attendance/select_student_for_attendance.html',
        {'class_session': class_session, 'booking_rows': booking_rows, 'today': today},
    )


@login_required
def mark_class_attendance(request, class_booking_id):
    if request.user.role != 'trainer':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    class_booking = get_object_or_404(ClassBooking, id=class_booking_id)
    class_session = class_booking.class_session

    if class_session.trainer != request.user and class_session.substitute_trainer != request.user:
        messages.error(request, 'You can only mark attendance for your own classes or subsitute class.')
        return redirect('index')

    teacher_present = TrainerAttendanceRecord.objects.filter(
        trainer=request.user,
        date=date.today(),
        status='present',
    ).exists()
    if not teacher_present:
        messages.error(request, 'Cannot mark attendance because you are not marked as present today.')
        return redirect('select_student_for_attendance', class_session_id=class_session.id)

    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('select_student_for_attendance', class_session_id=class_session.id)

    try:
        date_str = datetime.strptime(request.POST.get('date', ''), '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, 'Invalid date.')
        return redirect('select_student_for_attendance', class_session_id=class_session.id)

    status = request.POST.get('status')
    if status not in {'present', 'absent', 'class_cancelled'}:
        messages.error(request, 'Invalid attendance status.')
        return redirect('select_student_for_attendance', class_session_id=class_session.id)

    student = class_booking.user

    if date_str != date.today():
        messages.error(request, 'You can only mark attendance for today.')
        return redirect('select_student_for_attendance', class_session_id=class_session.id)

    if date_str.weekday() >= 5:
        messages.error(request, "Attendance cannot be marked on weekends.")
        return redirect('select_student_for_attendance', class_session_id=class_session.id)

    current_time = timezone.localtime().time()
    if current_time < class_session.start_time:
        messages.error(
            request,
            f"Attendance can only be marked after the class starts at {class_session.start_time.strftime('%I:%M %p')}."
        )
        return redirect('select_student_for_attendance', class_session_id=class_session.id)

    existing_cancel_record = ClassSessionAttendance.objects.filter(
        class_session=class_session,
        student=student,
        date=date_str,
        status='class_cancelled',
    ).exists()
    if existing_cancel_record:
        messages.error(request, 'Attendance cannot be changed because this class was already cancelled for today.')
        return redirect('select_student_for_attendance', class_session_id=class_session.id)

    ClassSessionAttendance.objects.update_or_create(
        class_session=class_session, student=student, date=date_str,
        defaults={'status': status, 'marked_by': request.user}
    )
    messages.success(request, 'Class attendance marked successfully.')
    return redirect('select_student_for_attendance', class_session_id=class_session.id)

@login_required
def admin_mark_class_attendance(request, class_session_id, student_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('admin_class_session_attendance_history', class_session_id=class_session_id)

    class_session = get_object_or_404(ClassSession, id=class_session_id)
    student = get_object_or_404(User, user_id=student_id)

    next_url = (request.POST.get('next') or '').strip()
    today = timezone.localdate()
    now_time = timezone.localtime().time()

    date_str = (request.POST.get('date') or '').strip()
    try:
        date_parsed = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, 'Invalid date.')
        return redirect(next_url or 'admin_class_session_attendance_history', class_session_id=class_session_id)

    if date_parsed > today:
        messages.error(request, 'You cannot mark attendance for a future date.')
        return redirect(next_url or 'admin_class_session_attendance_history', class_session_id=class_session_id)

    if date_parsed == today and now_time < class_session.start_time:
        messages.error(
            request,
            f"Attendance can only be updated after the class starts at {class_session.start_time.strftime('%I:%M %p')}."
        )
        return redirect(next_url or 'admin_class_session_attendance_history', class_session_id=class_session_id)

    if date_parsed < class_session.start_date or date_parsed > class_session.end_date:
        messages.error(request, 'Date is out of range for this class session.')
        return redirect(next_url or 'admin_class_session_attendance_history', class_session_id=class_session_id)

    if date_parsed.weekday() >= 5:
        messages.error(request, 'Attendance cannot be marked on weekends.')
        return redirect(next_url or 'admin_class_session_attendance_history', class_session_id=class_session_id)

    status = (request.POST.get('status') or '').strip()
    if status not in {'present', 'absent'}:
        messages.error(request, 'Invalid attendance status.')
        return redirect(next_url or 'admin_class_session_attendance_history', class_session_id=class_session_id)

    existing_record = ClassSessionAttendance.objects.filter(
        student=student,
        class_session=class_session,
        date=date_parsed,
    ).first()

    if existing_record and existing_record.status == 'class_cancelled':
        messages.error(request, 'Attendance cannot be changed because this class was already cancelled for this date.')
        return redirect(next_url or 'admin_class_session_attendance_history', class_session_id=class_session_id)

    if existing_record and existing_record.status == status:
        messages.error(request, f'Attendance is already marked as {status}.')
        return redirect(next_url or 'admin_class_session_attendance_history', class_session_id=class_session_id)

    ClassSessionAttendance.objects.update_or_create(
        student=student,
        class_session=class_session,
        date=date_parsed,
        defaults={'status': status, 'marked_by': request.user},
    )
    messages.success(request, 'Class attendance updated successfully.')
    return redirect(next_url or 'admin_class_session_attendance_history', class_session_id=class_session_id)


@login_required
def admin_mark_private_attendance(request, private_class_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('admin_private_class_attendance_history', private_class_id=private_class_id)

    private_class = get_object_or_404(PrivateClass, id=private_class_id)

    next_url = (request.POST.get('next') or '').strip()
    today = timezone.localdate()
    now_time = timezone.localtime().time()

    date_str = (request.POST.get('date') or '').strip()
    try:
        date_parsed = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, 'Invalid date.')
        return redirect(next_url or 'admin_private_class_attendance_history', private_class_id=private_class_id)

    if date_parsed > today:
        messages.error(request, 'You cannot mark attendance for a future date.')
        return redirect(next_url or 'admin_private_class_attendance_history', private_class_id=private_class_id)

    if date_parsed == today and now_time < private_class.start_time:
        messages.error(
            request,
            f"Attendance can only be updated after the class starts at {private_class.start_time.strftime('%I:%M %p')}."
        )
        return redirect(next_url or 'admin_private_class_attendance_history', private_class_id=private_class_id)

    if date_parsed < private_class.start_date or date_parsed > private_class.end_date:
        messages.error(request, 'Date is out of range for this private class.')
        return redirect(next_url or 'admin_private_class_attendance_history', private_class_id=private_class_id)

    if date_parsed.weekday() >= 5:
        messages.error(request, 'Attendance cannot be marked on weekends.')
        return redirect(next_url or 'admin_private_class_attendance_history', private_class_id=private_class_id)

    status = (request.POST.get('status') or '').strip()
    if status not in {'present', 'absent'}:
        messages.error(request, 'Invalid attendance status.')
        return redirect(next_url or 'admin_private_class_attendance_history', private_class_id=private_class_id)

    existing_record = PrivateClassAttendance.objects.filter(
        private_class=private_class,
        student=private_class.user,
        date=date_parsed,
    ).first()

    if existing_record and existing_record.status == 'class_cancelled':
        messages.error(request, 'Attendance cannot be changed because this class was already cancelled for this date.')
        return redirect(next_url or 'admin_private_class_attendance_history', private_class_id=private_class_id)

    if existing_record and existing_record.status == status:
        messages.error(request, f'Attendance is already marked as {status}.')
        return redirect(next_url or 'admin_private_class_attendance_history', private_class_id=private_class_id)

    PrivateClassAttendance.objects.update_or_create(
        private_class=private_class,
        student=private_class.user,
        date=date_parsed,
        defaults={'status': status, 'marked_by': request.user},
    )
    messages.success(request, 'Private class attendance updated successfully.')
    return redirect(next_url or 'admin_private_class_attendance_history', private_class_id=private_class_id)

@login_required
def select_private_class_for_attendance(request):
    if request.user.role != 'trainer':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    today = date.today()
    ongoing_private_classes = PrivateClass.objects.filter(
        (Q(trainer=request.user) | Q(substitute_trainer=request.user)),
        start_date__lte=today,
        end_date__gte=today,
        is_cancelled=False,
    ).order_by('start_date')
    q = (request.GET.get('q') or '').strip()
    if q:
        ongoing_private_classes = ongoing_private_classes.filter(
            Q(user__full_name__icontains=q) |
            Q(user__username__icontains=q) |
            Q(pool__name__icontains=q)
        )

    return render(
        request,
        'dashboards/trainer/attendance/select_private_class_for_attendance.html',
        {'ongoing_private_classes': ongoing_private_classes, 'today': today},
    )


@login_required
def mark_private_class_attendance(request, private_class_id):
    if request.user.role != 'trainer':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    private_class = get_object_or_404(PrivateClass, id=private_class_id)
    if private_class.trainer != request.user and private_class.substitute_trainer != request.user:
        messages.error(request, 'You can only mark attendance for your own classes or subsitute class.')
        return redirect('index')

    teacher_present = TrainerAttendanceRecord.objects.filter(
        trainer=request.user,
        date=date.today(),
        status='present',
    ).exists()
    if not teacher_present:
        messages.error(request, 'Cannot mark attendance because you are not marked as present today.')
        return redirect('select_private_class_for_attendance')

    if request.method == 'POST':
        try:
            date_str = datetime.strptime(request.POST.get('date', ''), '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'Invalid date.')
            return redirect('select_private_class_for_attendance')

        status = request.POST.get('status')
        if status not in {'present', 'absent', 'class_cancelled'}:
            messages.error(request, 'Invalid attendance status.')
            return redirect('select_private_class_for_attendance')

        student = private_class.user

        if date_str != date.today():
            messages.error(request, 'You can only mark attendance for today.')
            return redirect('select_private_class_for_attendance')

        if date_str.weekday() >= 5:  # Saturday or Sunday
            messages.error(request, "Attendance cannot be marked on weekends.")
            return redirect('select_private_class_for_attendance')

        current_time = timezone.localtime().time()
        if current_time < private_class.start_time:
            messages.error(
                request,
                f"Attendance can only be marked after the class starts at {private_class.start_time.strftime('%I:%M %p')}."
            )
            return redirect('select_private_class_for_attendance')

        existing_cancel_record = PrivateClassAttendance.objects.filter(
            private_class=private_class,
            student=student,
            date=date_str,
            status='class_cancelled',
        ).exists()
        if existing_cancel_record:
            messages.error(request, 'Attendance cannot be changed because this private class was already cancelled for today.')
            return redirect('select_private_class_for_attendance')

        PrivateClassAttendance.objects.update_or_create(
            private_class=private_class, student=student, date=date_str,
            defaults={'status': status, 'marked_by': request.user}
        )
        messages.success(request, 'Private class attendance marked successfully.')
        return redirect('select_private_class_for_attendance')

    today_record = PrivateClassAttendance.objects.filter(
        private_class=private_class,
        student=private_class.user,
        date=date.today(),
    ).first()
    return render(
        request,
        'dashboards/trainer/attendance/mark_private_class_attendance.html',
        {'private_class': private_class, 'today': date.today(), 'today_record': today_record},
    )

@login_required
def list_ongoing_classes_of_absent_trainer(request):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    today = date.today()
    absent_trainers = TrainerAttendanceRecord.objects.filter(date=today, status='absent').values_list('trainer_id', flat=True)
    ongoing_classes = ClassSession.objects.filter(
        trainer_id__in=absent_trainers,
        start_date__lte=today,
        end_date__gte=today,
        is_cancelled=False,
    ).select_related('pool', 'trainer', 'substitute_trainer').order_by('start_time')
    q = (request.GET.get('q') or '').strip()

    if q:
        ongoing_classes = ongoing_classes.filter(
            Q(class_name__icontains=q) |
            Q(pool__name__icontains=q) |
            Q(trainer__full_name__icontains=q) |
            Q(trainer__username__icontains=q)
        )

    return render(
        request,
        'dashboards/admin/attendance/class_session/list_ongoing_classes_of_absent_trainer.html',
        {'ongoing_classes': ongoing_classes, 'today': today},
    )


@login_required
def list_ongoing_private_classes_of_absent_trainer(request):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    today = date.today()
    absent_trainers = TrainerAttendanceRecord.objects.filter(date=today, status='absent').values_list('trainer_id', flat=True)
    ongoing_private_classes = PrivateClass.objects.filter(
        trainer_id__in=absent_trainers,
        start_date__lte=today,
        end_date__gte=today,
        is_cancelled=False,
    ).select_related('pool', 'trainer', 'substitute_trainer', 'user').order_by('start_date')
    q = (request.GET.get('q') or '').strip()

    if q:
        ongoing_private_classes = ongoing_private_classes.filter(
            Q(user__full_name__icontains=q) |
            Q(user__username__icontains=q) |
            Q(pool__name__icontains=q) |
            Q(trainer__full_name__icontains=q) |
            Q(trainer__username__icontains=q)
        )

    return render(
        request,
        'dashboards/admin/attendance/private_class/list_ongoing_private_classes_of_absent_trainer.html',
        {'ongoing_private_classes': ongoing_private_classes, 'today': today},
    )


@login_required
def assign_substitute_trainer_for_class_session(request, class_session_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    class_session = get_object_or_404(ClassSession, id=class_session_id)
    today = date.today()
    absent_trainer_ids = list(
        TrainerAttendanceRecord.objects.filter(date=today, status='absent').values_list('trainer_id', flat=True)
    )

    if class_session.start_date > today or class_session.end_date < today:
        messages.error(request, 'This class session is not ongoing.')
        return redirect('list_ongoing_classes_of_absent_trainer')

    if class_session.trainer_id not in absent_trainer_ids:
        messages.error(request, 'The trainer of this class session is not marked as absent today.')
        return redirect('list_ongoing_classes_of_absent_trainer')

    candidate_rows = _get_substitute_candidates(
        pool=class_session.pool,
        today=today,
        exclude_trainer_ids=[class_session.trainer_id],
    )

    available_trainer_ids = []
    for row in candidate_rows:
        if row['is_available']:
            available_trainer_ids.append(row['trainer'].pk)

    selected_trainer = None
    selected_trainer_id = request.GET.get('selected_trainer_id') or request.POST.get('selected_trainer_id')
    if selected_trainer_id:
        try:
            selected_trainer_id = int(selected_trainer_id)
        except ValueError:
            selected_trainer_id = None

    if selected_trainer_id in available_trainer_ids:
        for row in candidate_rows:
            if row['trainer'].pk == selected_trainer_id:
                selected_trainer = row['trainer']
                break

    if request.method == 'POST':
        if not selected_trainer:
            messages.error(request, 'Please select an available trainer first.')
            return redirect('assign_substitute_trainer_for_class_session', class_session_id=class_session_id)
        had_existing_substitute = class_session.substitute_trainer_id is not None
        class_session.substitute_trainer = selected_trainer
        class_session.save(update_fields=['substitute_trainer'])
        if had_existing_substitute:
            messages.success(request, 'Substitute trainer updated successfully.')
        else:
            messages.success(request, 'Substitute trainer assigned successfully.')
        return redirect('list_ongoing_classes_of_absent_trainer')

    return render(
        request,
        'dashboards/admin/attendance/class_session/assign_substitute_trainer_for_class_session.html',
        {
            'class_session': class_session,
            'today': today,
            'selected_trainer': selected_trainer,
            'current_substitute_trainer': class_session.substitute_trainer,
            'available_count': len(available_trainer_ids),
        },
    )

@login_required
def choose_substitute_trainer_for_class_session(request, class_session_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    class_session = get_object_or_404(ClassSession, id=class_session_id)
    today = date.today()
    if class_session.start_date > today or class_session.end_date < today:
        messages.error(request, 'This class session is not ongoing.')
        return redirect('list_ongoing_classes_of_absent_trainer')

    candidate_rows = _get_substitute_candidates(
        pool=class_session.pool,
        today=today,
        exclude_trainer_ids=[class_session.trainer_id],
    )
    return render(
        request,
        'dashboards/admin/attendance/class_session/choose_substitute_trainer_for_class_session.html',
        {'class_session': class_session, 'today': today, 'candidate_rows': candidate_rows},
    )

@login_required
def assign_substitute_trainer_for_private_class(request, private_class_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    private_class = get_object_or_404(PrivateClass, id=private_class_id)
    today = date.today()
    absent_trainer_ids = list(
        TrainerAttendanceRecord.objects.filter(date=today, status='absent').values_list('trainer_id', flat=True)
    )

    if private_class.start_date > today or private_class.end_date < today:
        messages.error(request, 'This private class is not ongoing.')
        return redirect('list_ongoing_private_classes_of_absent_trainer')

    if private_class.trainer_id not in absent_trainer_ids:
        messages.error(request, 'The trainer of this private class is not marked as absent today.')
        return redirect('list_ongoing_private_classes_of_absent_trainer')

    candidate_rows = _get_substitute_candidates(
        pool=private_class.pool,
        today=today,
        exclude_trainer_ids=[private_class.trainer_id],
    )
    available_trainer_ids = []
    for row in candidate_rows:
        if row['is_available']:
            available_trainer_ids.append(row['trainer'].pk)

    selected_trainer = None
    selected_trainer_id = request.GET.get('selected_trainer_id') or request.POST.get('selected_trainer_id')
    if selected_trainer_id:
        try:
            selected_trainer_id = int(selected_trainer_id)
        except ValueError:
            selected_trainer_id = None
    if selected_trainer_id in available_trainer_ids:
        for row in candidate_rows:
            if row['trainer'].pk == selected_trainer_id:
                selected_trainer = row['trainer']
                break

    if request.method == 'POST':
        if not selected_trainer:
            messages.error(request, 'Please select an available trainer first.')
            return redirect('assign_substitute_trainer_for_private_class', private_class_id=private_class_id)

        had_existing_substitute = private_class.substitute_trainer_id is not None
        private_class.substitute_trainer = selected_trainer
        private_class.save(update_fields=['substitute_trainer'])
        if had_existing_substitute:
            messages.success(request, 'Substitute trainer updated successfully.')
        else:
            messages.success(request, 'Substitute trainer assigned successfully.')
        return redirect('list_ongoing_private_classes_of_absent_trainer')

    return render(
        request,
        'dashboards/admin/attendance/private_class/assign_substitute_trainer_for_private_class.html',
        {
            'private_class': private_class,
            'today': today,
            'selected_trainer': selected_trainer,
            'current_substitute_trainer': private_class.substitute_trainer,
            'available_count': len(available_trainer_ids),
        },
    )

@login_required
def choose_substitute_trainer_for_private_class(request, private_class_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    private_class = get_object_or_404(PrivateClass, id=private_class_id)
    today = date.today()
    if private_class.start_date > today or private_class.end_date < today:
        messages.error(request, 'This private class is not ongoing.')
        return redirect('list_ongoing_private_classes_of_absent_trainer')

    candidate_rows = _get_substitute_candidates(
        pool=private_class.pool,
        today=today,
        exclude_trainer_ids=[private_class.trainer_id],
    )
    return render(
        request,
        'dashboards/admin/attendance/private_class/choose_substitute_trainer_for_private_class.html',
        {'private_class': private_class, 'today': today, 'candidate_rows': candidate_rows},
    )

@login_required
def cancel_group_class_for_day(request, class_session_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('index')
    next_url = (request.POST.get('next') or request.GET.get('next') or '').strip()

    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect(next_url or 'list_ongoing_classes_of_absent_trainer')

    class_session = get_object_or_404(ClassSession, id=class_session_id)
    today = date.today()
    date_str = (request.POST.get('date') or request.GET.get('date') or '').strip()
    if not date_str:
        messages.error(request, 'Date is required.')
        return redirect(next_url or 'list_ongoing_classes_of_absent_trainer')

    try:
        date_parsed = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, 'Invalid date format.')
        return redirect(next_url or 'list_ongoing_classes_of_absent_trainer')
    
    if date_parsed > today:
        messages.error(request, 'Date cannot be in the future.')
        return redirect(next_url or 'list_ongoing_classes_of_absent_trainer')
    
    if date_parsed < class_session.start_date or date_parsed > class_session.end_date:
        messages.error(request, 'Date is out of range for this class session.')
        return redirect(next_url or 'list_ongoing_classes_of_absent_trainer')
    
    if date_parsed.weekday() >= 5:
        messages.error(request, "Date cannot be a weekend.")
        return redirect(next_url or 'list_ongoing_classes_of_absent_trainer')

    bookings = (
        ClassBooking.objects.filter(class_session=class_session)
        .select_related('user')
        .distinct()
    )
    if not bookings.exists():
        messages.info(request, 'No bookings found for this class. Nothing to mark as cancelled.')
        return redirect(next_url or 'list_ongoing_classes_of_absent_trainer')

    cancelled_count = 0
    for booking in bookings:
        ClassSessionAttendance.objects.update_or_create(
            class_session=class_session,
            student=booking.user,
            date=date_parsed,
            defaults={'status': 'class_cancelled', 'marked_by': request.user},
        )
        cancelled_count += 1

    messages.success(
        request,
        f'Cancelled class for {date_parsed} and marked {cancelled_count} student attendance record(s) as class cancelled.'
    )
    return redirect(next_url or 'list_ongoing_classes_of_absent_trainer')

@login_required
def cancel_private_class_for_day(request, private_class_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('index')
    next_url = (request.POST.get('next') or request.GET.get('next') or '').strip()

    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect(next_url or 'list_ongoing_private_classes_of_absent_trainer')

    private_class = get_object_or_404(PrivateClass, id=private_class_id)
    today = date.today()
    date_str = (request.POST.get('date') or request.GET.get('date') or '').strip()
    if not date_str:
        messages.error(request, 'Date is required.')
        return redirect(next_url or 'list_ongoing_private_classes_of_absent_trainer')

    try:
        date_parsed = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, 'Invalid date format.')
        return redirect(next_url or 'list_ongoing_private_classes_of_absent_trainer')
    
    if date_parsed > today:
        messages.error(request, 'Date cannot be in the future.')
        return redirect(next_url or 'list_ongoing_private_classes_of_absent_trainer')
    
    if date_parsed < private_class.start_date or date_parsed > private_class.end_date:
        messages.error(request, 'Date is out of range for this class session.')
        return redirect(next_url or 'list_ongoing_private_classes_of_absent_trainer')
    
    if date_parsed.weekday() >= 5:
        messages.error(request, "Date cannot be a weekend.")
        return redirect(next_url or 'list_ongoing_private_classes_of_absent_trainer')

    PrivateClassAttendance.objects.update_or_create(
        private_class=private_class,
        student=private_class.user,
        date=date_parsed,
        defaults={'status': 'class_cancelled', 'marked_by': request.user},
    )
    messages.success(
        request,
        f'Cancelled private class for {date_parsed} and marked attendance as class cancelled.'
    )
    return redirect(next_url or 'list_ongoing_private_classes_of_absent_trainer')
@login_required
def undo_cancel_group_class_for_day(request, class_session_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('index')
    next_url = (request.POST.get('next') or request.GET.get('next') or '').strip()

    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect(next_url or 'list_ongoing_classes_of_absent_trainer')

    class_session = get_object_or_404(ClassSession, id=class_session_id)
    today = date.today()

    date_str = (request.POST.get('date') or request.GET.get('date') or '').strip()
    if not date_str:
        messages.error(request, 'Date is required.')
        return redirect(next_url or 'list_ongoing_classes_of_absent_trainer')

    try:
        date_parsed = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, 'Invalid date format.')
        return redirect(next_url or 'list_ongoing_classes_of_absent_trainer')

    if date_parsed > today:
        messages.error(request, 'Date cannot be in the future.')
        return redirect(next_url or 'list_ongoing_classes_of_absent_trainer')
    
    if date_parsed < class_session.start_date or date_parsed > class_session.end_date:
        messages.error(request, 'Date is out of range for this class session.')
        return redirect(next_url or 'list_ongoing_classes_of_absent_trainer')

    if date_parsed.weekday() >= 5:
        messages.error(request, "Date cannot be a weekend.")
        return redirect(next_url or 'list_ongoing_classes_of_absent_trainer')

    attendances = ClassSessionAttendance.objects.filter(
        class_session=class_session,
        date=date_parsed,
        status='class_cancelled',
    )
    if not attendances.exists():
        messages.info(request, 'No cancelled attendance records found for the selected date. Nothing to undo.')
        return redirect(next_url or 'list_ongoing_classes_of_absent_trainer')

    undone_count = 0
    for attendance in attendances:
        attendance.status = 'absent'
        attendance.marked_by = request.user
        attendance.save(update_fields=['status', 'marked_by'])
        undone_count += 1

    messages.success(
        request,
        f'Undid cancellation of class for {date_parsed} and marked {undone_count} student attendance record(s) as absent.'
    )
    return redirect(next_url or 'list_ongoing_classes_of_absent_trainer')


@login_required
def undo_cancel_private_class_for_day(request, private_class_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('index')
    next_url = (request.POST.get('next') or request.GET.get('next') or '').strip()

    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect(next_url or 'list_ongoing_private_classes_of_absent_trainer')

    private_class = get_object_or_404(PrivateClass, id=private_class_id)
    today = date.today()

    date_str = (request.POST.get('date') or request.GET.get('date') or '').strip()
    if not date_str:
        messages.error(request, 'Date is required.')
        return redirect(next_url or 'list_ongoing_private_classes_of_absent_trainer')

    try:
        date_parsed = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, 'Invalid date format.')
        return redirect(next_url or 'list_ongoing_private_classes_of_absent_trainer')

    if date_parsed > today:
        messages.error(request, 'Date cannot be in the future.')
        return redirect(next_url or 'list_ongoing_private_classes_of_absent_trainer')
    
    if date_parsed < private_class.start_date or date_parsed > private_class.end_date:
        messages.error(request, 'Date is out of range for this class session.')
        return redirect(next_url or 'list_ongoing_private_classes_of_absent_trainer')

    if date_parsed.weekday() >= 5:
        messages.error(request, "Date cannot be a weekend.")
        return redirect(next_url or 'list_ongoing_private_classes_of_absent_trainer')

    attendance = PrivateClassAttendance.objects.filter(
        private_class=private_class,
        date=date_parsed,
        status='class_cancelled',
    ).first()
    if not attendance:
        messages.info(request, 'No cancelled attendance records found for the selected date. Nothing to undo.')
        return redirect(next_url or 'list_ongoing_private_classes_of_absent_trainer')
    
    attendance.status = 'absent'
    attendance.marked_by = request.user
    attendance.save(update_fields=['status', 'marked_by'])

    messages.success(
        request,
        f'Undid cancellation of private class for {date_parsed} and marked attendance as absent.'
    )
    return redirect(next_url or 'list_ongoing_private_classes_of_absent_trainer')

@login_required
def class_session_attendance_history(request, class_session_id):
    if request.user.role != 'trainer' and request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    class_session = get_object_or_404(ClassSession, id=class_session_id)

    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    student_and_trainer_name = request.GET.get('student_and_trainer_name', '').strip()
    status = request.GET.get('status')

    if request.user.role == 'trainer':
            if class_session.trainer != request.user and class_session.substitute_trainer != request.user:
                messages.error(request, 'You can only view attendance history for your own classes or substitute classes.')
                return redirect('select_class_for_attendance')

    attendance_records = ClassSessionAttendance.objects.filter(class_session=class_session).order_by('-date')

    if date_from:
        try:
            date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d').date()
            attendance_records = attendance_records.filter(date__gte=date_from_parsed)
        except ValueError:
            pass

    if date_to:
        try:
            date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d').date()
            attendance_records = attendance_records.filter(date__lte=date_to_parsed)
        except ValueError:
            pass

    if student_and_trainer_name:
        attendance_records = attendance_records.filter(
            Q(student__full_name__icontains=student_and_trainer_name) |
            Q(student__username__icontains=student_and_trainer_name) |
            Q(student__email__icontains=student_and_trainer_name) |
            Q(marked_by__full_name__icontains=student_and_trainer_name) |
            Q(marked_by__username__icontains=student_and_trainer_name) |
            Q(marked_by__email__icontains=student_and_trainer_name)
        )

    bookings = ClassBooking.objects.filter(
        class_session=class_session,
        is_cancelled=False
    ).select_related('user').distinct()
    history_rows = list(attendance_records)
    today = date.today()

    last_date = class_session.end_date
    if last_date > today:
        last_date = today

    current_date = class_session.start_date

    while current_date <= last_date:
        if current_date.weekday() < 5:
            for booking in bookings:
                if not attendance_records.filter(class_session=class_session, student=booking.user, date=current_date).exists():
                    history_rows.append({
                        'student': booking.user,
                        'student_id': booking.user.user_id,
                        'date': current_date,
                        'status': 'not_marked',
                        'marked_by': None,
                    })
        current_date += timedelta(days=1)

    if status in {'present', 'absent', 'class_cancelled', 'not_marked'}:
        filtered_rows = []
        for row in history_rows:
            if hasattr(row, 'status'):
                row_status = row.status
            else:
                row_status = row['status']

            if row_status == status:
                filtered_rows.append(row)
        history_rows = filtered_rows

    template=''
    if request.user.role == 'admin':
        template = 'dashboards/admin/attendance/class_session/class_session_attendance_history.html'
    elif request.user.role == 'trainer':
        template = 'dashboards/trainer/attendance/class_session_attendance_history.html'
    return render(
        request,
        template,
        {'class_session': class_session, 'attendance_records': history_rows},
    )


@login_required
def private_class_attendance_history(request, private_class_id):
    if request.user.role != 'trainer' and request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    private_class = get_object_or_404(PrivateClass, id=private_class_id)

    if request.user.role == 'trainer':
        if private_class.trainer != request.user and private_class.substitute_trainer != request.user:
            messages.error(request, 'You can only view attendance history for your own classes or subsitute class.')
            return redirect('select_private_class_for_attendance')

    attendance_records = PrivateClassAttendance.objects.filter(private_class=private_class).order_by('-date')

    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    trainer_name = request.GET.get('trainer_name', '').strip()
    status = request.GET.get('status')

    if date_from:
        try:
            date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d').date()
            attendance_records = attendance_records.filter(date__gte=date_from_parsed)
        except ValueError:
            pass
    if date_to:
        try:
            date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d').date()
            attendance_records = attendance_records.filter(date__lte=date_to_parsed)
        except ValueError:
            pass

    if trainer_name:
        attendance_records = attendance_records.filter(
            Q(marked_by__full_name__icontains=trainer_name) |
            Q(marked_by__username__icontains=trainer_name) |
            Q(marked_by__email__icontains=trainer_name)
        )

    history_rows = list(attendance_records)
    today = date.today()
    last_date = private_class.end_date
    if last_date > today:
        last_date = today

    current_date = private_class.start_date
    while current_date <= last_date:
        if current_date.weekday() < 5:
            if not attendance_records.filter(date=current_date).exists():
                history_rows.append({
                    'student': private_class.user,
                    'student_id': private_class.user.user_id,
                    'date': current_date,
                    'status': 'not_marked',
                    'marked_by': None,
                })
        current_date += timedelta(days=1)

    if status in {'present', 'absent', 'class_cancelled', 'not_marked'}:
        filtered_rows = []
        for row in history_rows:
            if hasattr(row, 'status'):
                row_status = row.status
            else:
                row_status = row['status']

            if row_status == status:
                filtered_rows.append(row)
        history_rows = filtered_rows

    template=''
    if request.user.role == 'admin':
        template = 'dashboards/admin/attendance/private_class/private_class_attendance_history.html'
    elif request.user.role == 'trainer':
        template = 'dashboards/trainer/attendance/private_class_attendance_history.html'
    return render(
        request,
        template,
        {'private_class': private_class, 'attendance_records': history_rows},
    )

@login_required
def class_and_private_classes_cancellation_and_substitute_history(request):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')
    
    q = (request.GET.get('q') or '').strip()
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    private_or_group = request.GET.get('private_or_group', 'all')
    pool_id = request.GET.get('pool')

    class_sessions = ClassSession.objects.filter(
        is_cancelled=False
    )
    private_classes = PrivateClass.objects.filter(
        is_cancelled=False
    )

    if q:
        class_sessions = class_sessions.filter(
            Q(class_name__icontains=q) |
            Q(pool__name__icontains=q) |
            Q(class_type__name__icontains=q) |
            Q(trainer__full_name__icontains=q) |
            Q(trainer__username__icontains=q) |
            Q(substitute_trainer__full_name__icontains=q) |
            Q(substitute_trainer__username__icontains=q)
        )

        private_classes = private_classes.filter(
            Q(user__full_name__icontains=q) |
            Q(user__username__icontains=q) |
            Q(pool__name__icontains=q) |
            Q(trainer__full_name__icontains=q) |
            Q(trainer__username__icontains=q) |
            Q(substitute_trainer__full_name__icontains=q) |
            Q(substitute_trainer__username__icontains=q)
        )

    if date_from:
        try:
            date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d').date()
            class_sessions = class_sessions.filter(end_date__gte=date_from_parsed)
            private_classes = private_classes.filter(end_date__gte=date_from_parsed)
        except ValueError:
            pass

    if date_to:
        try:
            date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d').date()
            class_sessions = class_sessions.filter(start_date__lte=date_to_parsed)
            private_classes = private_classes.filter(start_date__lte=date_to_parsed)
        except ValueError:
            pass

    if private_or_group == 'private':
        class_sessions = class_sessions.none()
    elif private_or_group == 'group':
        private_classes = private_classes.none()
    
    if pool_id:
        try:
            pool_id_int = int(pool_id)
            class_sessions = class_sessions.filter(pool_id=pool_id_int)
            private_classes = private_classes.filter(pool_id=pool_id_int)
        except ValueError:
            pass

    return render(
        request,
        'dashboards/admin/attendance/class_and_private_classes_cancellation_and_substitute_history.html',
        {
            'class_sessions': class_sessions.order_by('-start_date', '-start_time'),
            'private_classes': private_classes.order_by('-start_date', '-start_time'),
            'pools': Pool.objects.all().order_by('name'),
        }
    )


@login_required
def admin_group_class_activity_detail(request, class_session_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    class_session = get_object_or_404(ClassSession, id=class_session_id)
    
    all_daily_records = ClassSessionAttendance.objects.filter(class_session=class_session).select_related('student', 'marked_by').order_by('-date')
    
    daily_records = all_daily_records

    q = (request.GET.get('q') or '').strip()
    if q:
        daily_records = daily_records.filter(
            Q(marked_by__full_name__icontains=q) |
            Q(marked_by__username__icontains=q) |
            Q(marked_by__email__icontains=q)
        )
        if not daily_records.exists():
            return render(
                request,
                'dashboards/admin/attendance/class_session/group_class_activity_detail.html',
                {
                    'class_session': class_session,
                    'daily_record_rows': [],
                },
            )
    
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        try:
            date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d').date()
            daily_records = daily_records.filter(date__gte=date_from_parsed)
        except ValueError:
            pass
    if date_to:
        try:
            date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d').date()
            daily_records = daily_records.filter(date__lte=date_to_parsed)
        except ValueError:
            pass
    
    get_order_by = request.GET.get('order_by')
    if get_order_by == 'date_asc':
        daily_records = daily_records.order_by('date')

    seen_dates = set()
    daily_record_rows = []
    for record in daily_records:
        if record.date in seen_dates:
            continue

        seen_dates.add(record.date)

        if record.status == 'class_cancelled':
            daily_record_rows.append({
                'date': record.date,
                'status': 'Cancelled',
                'marked_by': 'Admin',
            })
        elif record.status == 'present' or record.status == 'absent':
            status = 'Conducted'
            daily_record_rows.append({
                'date': record.date,
                'status': status,
                'marked_by': record.marked_by.full_name or record.marked_by.username,
            })

    current_date = class_session.start_date

    last_date = min(class_session.end_date, date.today())

    if date_from:
        try:
            date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d').date()
            if date_from_parsed > current_date:
                current_date = date_from_parsed
        except ValueError:
            pass
    if date_to:
        try:
            date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d').date()
            if date_to_parsed < last_date:
                last_date = date_to_parsed
        except ValueError:
            pass
    
    if current_date > last_date:
        return render(
            request,
            'dashboards/admin/attendance/class_session/group_class_activity_detail.html',
            {
                'class_session': class_session,
                'daily_record_rows': [],
            },
        )

    while current_date <= last_date:
        has_record_for_date = all_daily_records.filter(date=current_date).exists()

        if not has_record_for_date:
            row = {
                'date': current_date,
                'status': 'Not Conducted',
                'marked_by': '-',
            }

            if current_date.weekday() >= 5:
                row['status'] = 'Weekend'

            daily_record_rows.append(row)

        current_date += timedelta(days=1)

    
    status = request.GET.get('status')
    if status in {'Conducted', 'Cancelled', 'Not Conducted', 'Weekend'}:
        filtered_rows = []
        for row in daily_record_rows:
            if row['status'] == status:
                filtered_rows.append(row)
        daily_record_rows = filtered_rows

    return render(
        request,
        'dashboards/admin/attendance/class_session/group_class_activity_detail.html',
        {
            'class_session': class_session,
            'daily_record_rows': daily_record_rows,
        },
    )


@login_required
def admin_private_class_activity_detail(request, private_class_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    private_class = get_object_or_404(PrivateClass, id=private_class_id)
    
    all_daily_records = PrivateClassAttendance.objects.filter(private_class=private_class).select_related('student', 'marked_by').order_by('-date')
    
    daily_records = all_daily_records

    q = (request.GET.get('q') or '').strip()
    if q:
        daily_records = daily_records.filter(
            Q(marked_by__full_name__icontains=q) |
            Q(marked_by__username__icontains=q) |
            Q(marked_by__email__icontains=q)
        )
        if not daily_records.exists():
            return render(
                request,
                'dashboards/admin/attendance/private_class/private_class_activity_detail.html',
                {
                    'private_class': private_class,
                    'daily_record_rows': [],
                },
            )
    
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        try:
            date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d').date()
            daily_records = daily_records.filter(date__gte=date_from_parsed)
        except ValueError:
            pass
    if date_to:
        try:
            date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d').date()
            daily_records = daily_records.filter(date__lte=date_to_parsed)
        except ValueError:
            pass
    
    get_order_by = request.GET.get('order_by')
    if get_order_by == 'date_asc':
        daily_records = daily_records.order_by('date')

    seen_dates = set()
    daily_record_rows = []
    for record in daily_records:
        if record.date in seen_dates:
            continue

        seen_dates.add(record.date)

        if record.status == 'class_cancelled':
            daily_record_rows.append({
                'date': record.date,
                'status': 'Cancelled',
                'marked_by': 'Admin',
            })
        elif record.status == 'present' or record.status == 'absent':
            status = 'Conducted'
            daily_record_rows.append({
                'date': record.date,
                'status': status,
                'marked_by': record.marked_by.full_name or record.marked_by.username,
            })

    current_date = private_class.start_date

    last_date = min(private_class.end_date, date.today())

    if date_from:
        try:
            date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d').date()
            if date_from_parsed > current_date:
                current_date = date_from_parsed
        except ValueError:
            pass
    if date_to:
        try:
            date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d').date()
            if date_to_parsed < last_date:
                last_date = date_to_parsed
        except ValueError:
            pass
    
    if current_date > last_date:
        return render(
            request,
            'dashboards/admin/attendance/private_class/private_class_activity_detail.html',
            {
                'private_class': private_class,
                'daily_record_rows': [],
            },
        )

    while current_date <= last_date:
        has_record_for_date = all_daily_records.filter(date=current_date).exists()

        if not has_record_for_date:
            row = {
                'date': current_date,
                'status': 'Not Conducted',
                'marked_by': '-',
            }

            if current_date.weekday() >= 5:
                row['status'] = 'Weekend'

            daily_record_rows.append(row)

        current_date += timedelta(days=1)

    
    status = request.GET.get('status')
    if status in {'Conducted', 'Cancelled', 'Not Conducted', 'Weekend'}:
        filtered_rows = []
        for row in daily_record_rows:
            if row['status'] == status:
                filtered_rows.append(row)
        daily_record_rows = filtered_rows

    return render(
        request,
        'dashboards/admin/attendance/private_class/private_class_activity_detail.html',
        {
            'private_class': private_class,
            'daily_record_rows': daily_record_rows,
        },
    )

@login_required
def select_trainer_for_attendance_history(request):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    trainers = User.objects.filter(role='trainer').order_by('full_name')
    q = (request.GET.get('q') or '').strip()

    if q:
        trainers = trainers.filter(
            Q(username__icontains=q) |
            Q(full_name__icontains=q) |
            Q(email__icontains=q)
        )

    return render(
        request,
        'dashboards/admin/attendance/trainer/select_trainer_for_attendance_history.html',
        {'trainers': trainers},
    )

@login_required
def trainers_attandance_history(request, trainer_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    trainer = get_object_or_404(User, pk=trainer_id)
    attendance_records = TrainerAttendanceRecord.objects.filter(trainer=trainer).order_by('-date')


    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    status = request.GET.get('status')

    if date_from:
        try:
            date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d').date()
            attendance_records = attendance_records.filter(date__gte=date_from_parsed)
        except ValueError:
            pass
    if date_to:
        try:
            date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d').date()
            attendance_records = attendance_records.filter(date__lte=date_to_parsed)
        except ValueError:
            pass
        
    history_rows = list(attendance_records)
    today = date.today()
    current_date = trainer.created_at.date()

    while current_date <= today:
        if current_date.weekday() < 5:
            if not attendance_records.filter(date=current_date).exists():
                history_rows.append({
                    'date': current_date,
                    'status': 'not_marked',
                })
        current_date += timedelta(days=1)

    if status in {'present', 'absent', 'not_marked'}:
        filtered_rows = []
        for row in history_rows:
            if hasattr(row, 'status'):
                row_status = row.status
            else:
                row_status = row['status']

            if row_status == status:
                filtered_rows.append(row)
        history_rows = filtered_rows

    return render(
        request,
        'dashboards/admin/attendance/trainer/trainer_attendance_history.html',
        {'trainer': trainer, 'attendance_records': history_rows},
    )


@login_required
def admin_mark_trainer_attendance_for_day(request, trainer_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('trainers_attandance_history', trainer_id=trainer_id)

    trainer = get_object_or_404(User, pk=trainer_id, role='trainer')
    next_url = (request.POST.get('next') or '').strip()

    date_str = (request.POST.get('date') or '').strip()
    try:
        date_parsed = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        messages.error(request, 'Invalid date.')
        return redirect(next_url or 'trainers_attandance_history', trainer_id=trainer_id)

    today = timezone.localdate()
    if date_parsed > today:
        messages.error(request, 'You cannot mark attendance for a future date.')
        return redirect(next_url or 'trainers_attandance_history', trainer_id=trainer_id)

    if date_parsed.weekday() >= 5:
        messages.error(request, 'Attendance cannot be marked on weekends.')
        return redirect(next_url or 'trainers_attandance_history', trainer_id=trainer_id)

    status = (request.POST.get('status') or '').strip()
    if status not in {'present', 'absent'}:
        messages.error(request, 'Invalid attendance status.')
        return redirect(next_url or 'trainers_attandance_history', trainer_id=trainer_id)

    TrainerAttendanceRecord.objects.update_or_create(
        trainer=trainer,
        date=date_parsed,
        defaults={'status': status},
    )
    messages.success(request, 'Trainer attendance updated successfully.')
    return redirect(next_url or 'trainers_attandance_history', trainer_id=trainer_id)

@login_required
def admin_class_session_list_for_attendance_history(request):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    class_session = ClassSession.objects.select_related('pool', 'trainer', 'class_type').all().order_by('-start_date', '-start_time')
    today = date.today()
    q = (request.GET.get('q') or '').strip()
    status = (request.GET.get('status') or '').strip()
    pool_filter = (request.GET.get('pool') or '').strip()
    trainer_filter = (request.GET.get('trainer') or '').strip()

    if q:
        class_session = class_session.filter(
            Q(class_name__icontains=q) |
            Q(pool__name__icontains=q) |
            Q(trainer__full_name__icontains=q) |
            Q(trainer__username__icontains=q)
        )

    if status == 'active':
        class_session = class_session.filter(is_cancelled=False, end_date__gte=today)
    elif status == 'completed':
        class_session = class_session.filter(is_cancelled=False, end_date__lt=today)
    elif status == 'cancelled':
        class_session = class_session.filter(is_cancelled=True)

    if pool_filter:
        class_session = class_session.filter(pool_id=pool_filter)

    if trainer_filter:
        class_session = class_session.filter(trainer_id=trainer_filter)

    return render(
        request,
        'dashboards/admin/attendance/class_session/select_class_session_for_attendance_history.html',
        {
            'class_sessions': class_session,
            'pools': Pool.objects.filter(is_closed=False).order_by('name'),
            'trainers': User.objects.filter(role='trainer', is_active=True).order_by('full_name', 'username'),
        },
    )


@login_required
def admin_private_class_list_for_attendance_history(request):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    private_classes = PrivateClass.objects.select_related('pool', 'trainer', 'user').all().order_by('-start_date', '-start_time')
    today = date.today()
    q = (request.GET.get('q') or '').strip()
    status = (request.GET.get('status') or '').strip()
    pool_filter = (request.GET.get('pool') or '').strip()
    trainer_filter = (request.GET.get('trainer') or '').strip()

    if q:
        private_classes = private_classes.filter(
            Q(user__full_name__icontains=q) |
            Q(user__username__icontains=q) |
            Q(pool__name__icontains=q) |
            Q(trainer__full_name__icontains=q) |
            Q(trainer__username__icontains=q)
        )

    if status == 'active':
        private_classes = private_classes.filter(is_cancelled=False, end_date__gte=today)
    elif status == 'completed':
        private_classes = private_classes.filter(is_cancelled=False, end_date__lt=today)
    elif status == 'cancelled':
        private_classes = private_classes.filter(is_cancelled=True)

    if pool_filter:
        private_classes = private_classes.filter(pool_id=pool_filter)

    if trainer_filter:
        private_classes = private_classes.filter(trainer_id=trainer_filter)

    return render(
        request,
        'dashboards/admin/attendance/private_class/select_private_class_for_attendance_history.html',
        {
            'private_classes': private_classes,
            'pools': Pool.objects.filter(is_closed=False).order_by('name'),
            'trainers': User.objects.filter(role='trainer', is_active=True).order_by('full_name', 'username'),
        },
    )

