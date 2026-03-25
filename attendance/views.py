from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q

from .models import (
    TrainerAttendanceRecord,
    ClassSessionAttendance,
    PrivateClassAttendance,
)
from accounts.models import User
from classes.models import ClassSession, PrivateClass, ClassBooking
from pool.models import Pool, TrainerPoolAssignment

from datetime import date, datetime


# Create your views here.
def _get_substitute_candidates(pool, today, start_time, end_time, exclude_trainer_ids=None):
    exclude_trainer_ids = exclude_trainer_ids or []
    assigned_trainer_ids = TrainerPoolAssignment.objects.filter(
        pool=pool,
        is_active=True,
        start_date__lte=today,
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=today)
    ).values_list('trainer_id', flat=True)

    present_trainer_ids = TrainerAttendanceRecord.objects.filter(
        date=today,
        status='present',
    ).values_list('trainer_id', flat=True)

    trainers = User.objects.filter(
        role='trainer',
        is_active=True,
        pk__in=assigned_trainer_ids,
    ).filter(pk__in=present_trainer_ids
    ).exclude(pk__in=exclude_trainer_ids).distinct()
    
    candidates = []

    for trainer in trainers:
        class_conflict = ClassSession.objects.filter(
            Q(trainer=trainer) | Q(substitute_trainer=trainer),
            start_date__lte=today,
            end_date__gte=today,
            start_time__lt=end_time,
            end_time__gt=start_time,
            is_cancelled=False,
        ).exists()
        private_conflict = PrivateClass.objects.filter(
            Q(trainer=trainer) | Q(substitute_trainer=trainer),
            start_date__lte=today,
            end_date__gte=today,
            start_time__lt=end_time,
            end_time__gt=start_time,
            is_cancelled=False,
        ).exists()

        has_conflict = class_conflict or private_conflict
        if has_conflict:
            conflict_label = 'Busy at this time'
        else:
            conflict_label = 'Available'

        candidates.append(
            {
                'trainer': trainer,
                'is_available': not has_conflict,
                'conflict_label': conflict_label,
            }
        )
    return candidates

@login_required
def select_trainer_for_attendance(request):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    today = date.today()
    trainers = User.objects.filter(role='trainer', is_active=True).order_by('full_name', 'username')
    attendance_map = {}
    attendance_records = TrainerAttendanceRecord.objects.filter(date=today).select_related('trainer')
    for record in attendance_records:
        attendance_map[record.trainer_id] = record.status

    trainer_rows = []
    for trainer in trainers:
        trainer_rows.append({
            'trainer': trainer,
            'status': attendance_map.get(trainer.pk, 'pending'),
        })
    return render(
        request,
        'dashboards/admin/attendance/select_trainer_for_attendance.html',
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
                'dashboards/admin/attendance/mark_trainer_attendance.html',
                {
                    'trainer': trainer,
                    'today': today,
                    'today_record': today_record,
                    'require_substitute_clear_confirmation': True,
                    'pending_group_substitute_count': substitute_group_qs.count(),
                    'pending_private_substitute_count': substitute_private_qs.count(),
                    'pending_group_substitute_classes': substitute_group_qs[:3],
                    'pending_private_substitute_classes': substitute_private_qs[:3],
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
        'dashboards/admin/attendance/mark_trainer_attendance.html',
        {'trainer': trainer, 'today': today, 'today_record': today_record},
    )


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

    ClassSessionAttendance.objects.update_or_create(
        class_session=class_session, student=student, date=date_str,
        defaults={'status': status, 'marked_by': request.user}
    )
    messages.success(request, 'Class attendance marked successfully.')
    return redirect('select_student_for_attendance', class_session_id=class_session.id)


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
        Q(trainer_id__in=absent_trainers) | Q(substitute_trainer_id__in=absent_trainers),
        start_date__lte=today,
        end_date__gte=today,
        is_cancelled=False,
    ).order_by('start_time')

    return render(
        request,
        'dashboards/admin/attendance/list_ongoing_classes_of_absent_trainer.html',
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
        Q(trainer_id__in=absent_trainers) | Q(substitute_trainer_id__in=absent_trainers),
        start_date__lte=today,
        end_date__gte=today,
        is_cancelled=False,
    ).order_by('start_date')

    return render(
        request,
        'dashboards/admin/attendance/list_ongoing_private_classes_of_absent_trainer.html',
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
    
    if class_session.substitute_trainer is not None:
        messages.error(request, 'This class session already has a substitute trainer.')
        return redirect('list_ongoing_classes_of_absent_trainer')
    
    if class_session.trainer_id not in absent_trainer_ids:
        messages.error(request, 'The trainer of this class session is not marked as absent today.')
        return redirect('list_ongoing_classes_of_absent_trainer')
    
    candidate_rows = _get_substitute_candidates(
        pool=class_session.pool,
        today=today,
        start_time=class_session.start_time,
        end_time=class_session.end_time,
        exclude_trainer_ids=[class_session.trainer_id, class_session.substitute_trainer_id],
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
        class_session.substitute_trainer = selected_trainer
        class_session.save()
        messages.success(request, 'Substitute trainer assigned successfully.')
        return redirect('list_ongoing_classes_of_absent_trainer')
    
    return render(
        request,
        'dashboards/admin/attendance/assign_substitute_trainer_for_class_session.html',
        {
            'class_session': class_session,
            'today': today,
            'selected_trainer': selected_trainer,
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
        start_time=class_session.start_time,
        end_time=class_session.end_time,
        exclude_trainer_ids=[class_session.trainer_id, class_session.substitute_trainer_id],
    )
    return render(
        request,
        'dashboards/admin/attendance/choose_substitute_trainer_for_class_session.html',
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

    if private_class.substitute_trainer is not None:
        messages.error(request, 'This private class already has a substitute trainer.')
        return redirect('list_ongoing_private_classes_of_absent_trainer')

    if private_class.trainer_id not in absent_trainer_ids:
        messages.error(request, 'The trainer of this private class is not marked as absent today.')
        return redirect('list_ongoing_private_classes_of_absent_trainer')

    candidate_rows = _get_substitute_candidates(
        pool=private_class.pool,
        today=today,
        start_time=private_class.start_time,
        end_time=private_class.end_time,
        exclude_trainer_ids=[private_class.trainer_id, private_class.substitute_trainer_id],
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

        private_class.substitute_trainer = selected_trainer
        private_class.save()
        messages.success(request, 'Substitute trainer assigned successfully.')
        return redirect('list_ongoing_private_classes_of_absent_trainer')

    return render(
        request,
        'dashboards/admin/attendance/assign_substitute_trainer_for_private_class.html',
        {
            'private_class': private_class,
            'today': today,
            'selected_trainer': selected_trainer,
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
        start_time=private_class.start_time,
        end_time=private_class.end_time,
        exclude_trainer_ids=[private_class.trainer_id, private_class.substitute_trainer_id],
    )
    return render(
        request,
        'dashboards/admin/attendance/choose_substitute_trainer_for_private_class.html',
        {'private_class': private_class, 'today': today, 'candidate_rows': candidate_rows},
    )


@login_required
def cancel_group_class_for_today(request, class_session_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('index')

    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('list_ongoing_classes_of_absent_trainer')

    class_session = get_object_or_404(ClassSession, id=class_session_id)
    today = date.today()

    if class_session.start_date > today or class_session.end_date < today:
        messages.error(request, 'This class session is not ongoing today.')
        return redirect('list_ongoing_classes_of_absent_trainer')

    if class_session.substitute_trainer_id is not None:
        messages.error(request, 'A substitute trainer is already assigned for today.')
        return redirect('assign_substitute_trainer_for_class_session', class_session_id=class_session_id)

    bookings = (
        ClassBooking.objects.filter(class_session=class_session)
        .select_related('user')
        .distinct()
    )
    if not bookings.exists():
        messages.info(request, 'No bookings found for this class. Nothing to mark as cancelled.')
        return redirect('list_ongoing_classes_of_absent_trainer')

    cancelled_count = 0
    for booking in bookings:
        ClassSessionAttendance.objects.update_or_create(
            class_session=class_session,
            student=booking.user,
            date=today,
            defaults={'status': 'class_cancelled', 'marked_by': request.user},
        )
        cancelled_count += 1

    messages.success(
        request,
        f'Cancelled class for today and marked {cancelled_count} student attendance record(s) as class cancelled.',
    )
    return redirect('list_ongoing_classes_of_absent_trainer')


@login_required
def cancel_private_class_for_today(request, private_class_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('index')

    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('list_ongoing_private_classes_of_absent_trainer')

    private_class = get_object_or_404(PrivateClass, id=private_class_id)
    today = date.today()

    if private_class.start_date > today or private_class.end_date < today:
        messages.error(request, 'This private class is not ongoing today.')
        return redirect('list_ongoing_private_classes_of_absent_trainer')

    if private_class.substitute_trainer_id is not None:
        messages.error(request, 'A substitute trainer is already assigned for today.')
        return redirect('assign_substitute_trainer_for_private_class', private_class_id=private_class_id)

    PrivateClassAttendance.objects.update_or_create(
        private_class=private_class,
        student=private_class.user,
        date=today,
        defaults={'status': 'class_cancelled', 'marked_by': request.user},
    )
    messages.success(request, 'Cancelled private class for today and marked attendance as class cancelled.')
    return redirect('list_ongoing_private_classes_of_absent_trainer')


@login_required
def list_trainer_classes(request, trainer_id):
    if request.user.role != 'admin' and request.user.pk != trainer_id:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    trainer = get_object_or_404(User, pk=trainer_id)
    classes = ClassSession.objects.filter(
        Q(trainer=trainer) | Q(substitute_trainer=trainer)
    ).order_by('-start_date', '-start_time')

    private_classes = PrivateClass.objects.filter(
        Q(trainer=trainer) | Q(substitute_trainer=trainer)
    ).order_by('-start_date', '-start_time')

    return render(
        request,
        'dashboards/admin/attendance/list_trainer_classes.html',
        {'trainer': trainer, 'classes': classes, 'private_classes': private_classes},
    )


@login_required
def class_session_attendance_history(request, class_session_id):
    if request.user.role != 'trainer':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    class_session = get_object_or_404(ClassSession, id=class_session_id)

    if class_session.trainer != request.user and class_session.substitute_trainer != request.user:
        messages.error(request, 'You can only view attendance history for your own classes or subsitute class.')
        return redirect('select_class_for_attendance')

    attendance_records = ClassSessionAttendance.objects.filter(class_session=class_session).order_by('-date')
    return render(
        request,
        'dashboards/trainer/attendance/class_session_attendance_history.html',
        {'class_session': class_session, 'attendance_records': attendance_records},
    )


@login_required
def private_class_attendance_history(request, private_class_id):
    if request.user.role != 'trainer':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    private_class = get_object_or_404(PrivateClass, id=private_class_id)

    if private_class.trainer != request.user and private_class.substitute_trainer != request.user:
        messages.error(request, 'You can only view attendance history for your own classes or subsitute class.')
        return redirect('select_private_class_for_attendance')

    attendance_records = PrivateClassAttendance.objects.filter(private_class=private_class).order_by('-date')
    return render(
        request,
        'dashboards/trainer/attendance/private_class_attendance_history.html',
        {'private_class': private_class, 'attendance_records': attendance_records},
    )


@login_required
def admin_private_class_attendance_history(request, private_class_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    private_class = get_object_or_404(PrivateClass, id=private_class_id)
    attendance_records = PrivateClassAttendance.objects.filter(private_class=private_class).order_by('-date')
    return render(
        request,
        'dashboards/admin/attendance/private_class_attendance_history.html',
        {'private_class': private_class, 'attendance_records': attendance_records},
    )


@login_required
def admin_class_session_attendance_history(request, class_session_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    class_session = get_object_or_404(ClassSession, id=class_session_id)
    attendance_records = ClassSessionAttendance.objects.filter(class_session=class_session).order_by('-date')
    return render(
        request,
        'dashboards/admin/attendance/class_session_attendance_history.html',
        {'class_session': class_session, 'attendance_records': attendance_records},
    )

@login_required
def trainer_attendance_history(request, trainer_id):
    if request.user.role != 'admin' and request.user.pk != trainer_id:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    trainer = get_object_or_404(User, pk=trainer_id)
    attendance_records = TrainerAttendanceRecord.objects.filter(trainer=trainer).order_by('-date')
    return render(
        request,
        'dashboards/admin/attendance/trainer_attendance_history.html',
        {'trainer': trainer, 'attendance_records': attendance_records},
    )


@login_required
def class_and_private_classes_cancellation_and_substitute_history(request):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    today = date.today()
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    section = request.GET.get('section', 'all')
    pool_id = request.GET.get('pool')
    trainer_q = (request.GET.get('trainer') or '').strip()

    try:
        if date_from:
            from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
        else:
            from_date = today
    except ValueError:
        from_date = today
    try:
        if date_to:
            to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
        else:
            to_date = today
    except ValueError:
        to_date = today
    if from_date > to_date:
        from_date, to_date = to_date, from_date

    if section not in {'all', 'group', 'private'}:
        section = 'all'

    group_classes = ClassSession.objects.filter(
        start_date__lte=to_date,
        end_date__gte=from_date,
    ).select_related('pool', 'trainer', 'substitute_trainer')

    private_classes = PrivateClass.objects.filter(
        start_date__lte=to_date,
        end_date__gte=from_date,
    ).select_related('pool', 'trainer', 'substitute_trainer')

    try:
        if pool_id:
            selected_pool_id = int(pool_id)
        else:
            selected_pool_id = None
    except (TypeError, ValueError):
        selected_pool_id = None

    if selected_pool_id is not None:
        group_classes = group_classes.filter(pool_id=selected_pool_id)
        private_classes = private_classes.filter(pool_id=selected_pool_id)

    if trainer_q:
        group_classes = group_classes.filter(
            Q(trainer__full_name__icontains=trainer_q) |
            Q(trainer__email__icontains=trainer_q) |
            Q(substitute_trainer__full_name__icontains=trainer_q) |
            Q(substitute_trainer__email__icontains=trainer_q)
        )
        private_classes = private_classes.filter(
            Q(trainer__full_name__icontains=trainer_q) |
            Q(trainer__email__icontains=trainer_q) |
            Q(substitute_trainer__full_name__icontains=trainer_q) |
            Q(substitute_trainer__email__icontains=trainer_q)
        )

    group_classes = group_classes.distinct().order_by('-start_date', '-start_time')
    private_classes = private_classes.distinct().order_by('-start_date', '-start_time')

    if selected_pool_id is not None:
        selected_pool_id_value = str(selected_pool_id)
    else:
        selected_pool_id_value = ''

    if section in {'all', 'group'}:
        visible_group_classes = group_classes
    else:
        visible_group_classes = []

    if section in {'all', 'private'}:
        visible_private_classes = private_classes
    else:
        visible_private_classes = []

    return render(
        request,
        'dashboards/admin/attendance/class_and_private_classes_cancellation_and_substitute_history.html',
        {
            'today': today,
            'from_date': from_date,
            'to_date': to_date,
            'section': section,
            'pool_id': selected_pool_id_value,
            'trainer_q': trainer_q,
            'pools': Pool.objects.all().order_by('name'),
            'group_classes': visible_group_classes,
            'private_classes': visible_private_classes
        },
    )


@login_required
def admin_group_class_activity_detail(request, class_session_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    class_session = get_object_or_404(ClassSession, id=class_session_id)
    today = date.today()
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    try:
        if date_from:
            from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
        else:
            from_date = today
    except ValueError:
        from_date = today
    try:
        if date_to:
            to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
        else:
            to_date = today
    except ValueError:
        to_date = today
    if from_date > to_date:
        from_date, to_date = to_date, from_date

    active_from = max(class_session.start_date, from_date)
    active_to = min(class_session.end_date, to_date)

    trainer_records = TrainerAttendanceRecord.objects.filter(
        trainer=class_session.trainer,
        date__gte=active_from,
        date__lte=active_to,
    )
    trainer_status_map = {}
    trainer_dates = set()
    for record in trainer_records:
        trainer_status_map[record.date] = record.status
        trainer_dates.add(record.date)

    cancelled_dates = set()
    cancelled_date_rows = ClassSessionAttendance.objects.filter(
        class_session=class_session,
        date__gte=active_from,
        date__lte=active_to,
        status='class_cancelled',
    ).values_list('date', flat=True).distinct()
    for cancelled_date in cancelled_date_rows:
        cancelled_dates.add(cancelled_date)

    candidate_dates = sorted(trainer_dates.union(cancelled_dates), reverse=True)
    daily_rows = []
    for class_date in candidate_dates:
        trainer_status_raw = trainer_status_map.get(class_date)
        if trainer_status_raw == 'absent':
            trainer_status = 'Absent'
        elif trainer_status_raw == 'present':
            trainer_status = 'Present'
        else:
            trainer_status = 'Not Marked'

        has_substitute = bool(class_session.substitute_trainer_id and trainer_status_raw == 'absent')
        is_cancelled_for_day = class_date in cancelled_dates or class_session.is_cancelled
        if is_cancelled_for_day:
            status = 'Cancelled'
        elif trainer_status_raw == 'absent' and not has_substitute:
            status = 'Not Conducted'
        else:
            status = 'Conducted'

        if has_substitute:
            substitute_name = class_session.substitute_trainer.full_name or class_session.substitute_trainer.username
        else:
            substitute_name = '-'

        daily_rows.append({
            'date': class_date,
            'main_trainer_status': trainer_status,
            'substitute_name': substitute_name,
            'status': status,
        })

    return render(
        request,
        'dashboards/admin/attendance/group_class_activity_detail.html',
        {
            'class_session': class_session,
            'from_date': from_date,
            'to_date': to_date,
            'daily_rows': daily_rows,
        },
    )


@login_required
def admin_private_class_activity_detail(request, private_class_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    private_class = get_object_or_404(PrivateClass, id=private_class_id)
    today = date.today()
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    try:
        if date_from:
            from_date = datetime.strptime(date_from, '%Y-%m-%d').date()
        else:
            from_date = today
    except ValueError:
        from_date = today
    try:
        if date_to:
            to_date = datetime.strptime(date_to, '%Y-%m-%d').date()
        else:
            to_date = today
    except ValueError:
        to_date = today
    if from_date > to_date:
        from_date, to_date = to_date, from_date

    active_from = max(private_class.start_date, from_date)
    active_to = min(private_class.end_date, to_date)

    trainer_records = TrainerAttendanceRecord.objects.filter(
        trainer=private_class.trainer,
        date__gte=active_from,
        date__lte=active_to,
    )
    trainer_status_map = {}
    trainer_dates = set()
    for record in trainer_records:
        trainer_status_map[record.date] = record.status
        trainer_dates.add(record.date)

    cancelled_dates = set()
    cancelled_date_rows = PrivateClassAttendance.objects.filter(
        private_class=private_class,
        date__gte=active_from,
        date__lte=active_to,
        status='class_cancelled',
    ).values_list('date', flat=True).distinct()
    for cancelled_date in cancelled_date_rows:
        cancelled_dates.add(cancelled_date)

    candidate_dates = sorted(trainer_dates.union(cancelled_dates), reverse=True)
    daily_rows = []
    for class_date in candidate_dates:
        trainer_status_raw = trainer_status_map.get(class_date)
        if trainer_status_raw == 'absent':
            trainer_status = 'Absent'
        elif trainer_status_raw == 'present':
            trainer_status = 'Present'
        else:
            trainer_status = 'Not Marked'

        has_substitute = bool(private_class.substitute_trainer_id and trainer_status_raw == 'absent')
        is_cancelled_for_day = class_date in cancelled_dates or private_class.is_cancelled
        if is_cancelled_for_day:
            status = 'Cancelled'
        elif trainer_status_raw == 'absent' and not has_substitute:
            status = 'Not Conducted'
        else:
            status = 'Conducted'

        if has_substitute:
            substitute_name = private_class.substitute_trainer.full_name or private_class.substitute_trainer.username
        else:
            substitute_name = '-'

        daily_rows.append({
            'date': class_date,
            'main_trainer_status': trainer_status,
            'substitute_name': substitute_name,
            'status': status,
        })

    return render(
        request,
        'dashboards/admin/attendance/private_class_activity_detail.html',
        {
            'private_class': private_class,
            'from_date': from_date,
            'to_date': to_date,
            'daily_rows': daily_rows,
        },
    )
