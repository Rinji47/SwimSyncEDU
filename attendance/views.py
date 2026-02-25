from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q

from .models import TrainerAttendanceRecord, ClassSessionAttendance, PrivateClassAttendance
from accounts.models import User
from classes.models import ClassSession, PrivateClass, ClassBooking
from pool.models import TrainerPoolAssignment

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

    trainers = (
        User.objects.filter(
            role='trainer',
            is_active=True,
            pk__in=assigned_trainer_ids,
        )
        .filter(pk__in=present_trainer_ids)
        .exclude(pk__in=exclude_trainer_ids)
        .distinct()
    )

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
        candidates.append(
            {
                'trainer': trainer,
                'is_available': not has_conflict,
                'conflict_label': 'Busy at this time' if has_conflict else 'Available',
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
    attendance_map = {
        record.trainer_id: record.status
        for record in TrainerAttendanceRecord.objects.filter(date=today).select_related('trainer')
    }
    trainer_rows = [
        {'trainer': trainer, 'status': attendance_map.get(trainer.pk, 'pending')}
        for trainer in trainers
    ]
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

        attendance_record, created = TrainerAttendanceRecord.objects.update_or_create(
            trainer=trainer, date=date_str, defaults={'status': status}
        )

        if attendance_record.status == 'present':
            class_sessions_today = ClassSession.objects.filter(
                Q(trainer=trainer) | Q(substitute_trainer=trainer),
                start_date__lte=today,
                end_date__gte=today,
                is_cancelled=False,
            )
            private_classes_today = PrivateClass.objects.filter(
                Q(trainer=trainer) | Q(substitute_trainer=trainer),
                start_date__lte=today,
                end_date__gte=today,
                is_cancelled=False,
            )

            class_sessions_updated = class_sessions_today.filter(substitute_trainer=trainer).update(substitute_trainer=None)
            if class_sessions_updated:
                messages.info(request, 'Trainer substitute assignments for group classes were cleared for today.')

            private_classes_updated = private_classes_today.filter(substitute_trainer=trainer).update(substitute_trainer=None)
            if private_classes_updated:
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
    attendance_today = {
        record.student_id: record.status
        for record in ClassSessionAttendance.objects.filter(class_session=class_session, date=today)
    }
    booking_rows = [
        {'booking': booking, 'status': attendance_today.get(booking.user_id, 'pending')}
        for booking in bookings
    ]

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

    if request.method == 'POST':
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

        if date_str.weekday() >= 5:  # Saturday or Sunday
            messages.error(request, "Attendance cannot be marked on weekends.")
            return redirect('select_student_for_attendance', class_session_id=class_session.id)

        ClassSessionAttendance.objects.update_or_create(
            class_session=class_session, student=student, date=date_str,
            defaults={'status': status, 'marked_by': request.user}
        )
        messages.success(request, 'Class attendance marked successfully.')
        return redirect('select_student_for_attendance', class_session_id=class_session.id)

    today_record = ClassSessionAttendance.objects.filter(
        class_session=class_session,
        student=class_booking.user,
        date=date.today(),
    ).first()
    return render(
        request,
        'dashboards/trainer/attendance/mark_class_attendance.html',
        {'class_booking': class_booking, 'today': date.today(), 'today_record': today_record},
    )


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

    if request.method == 'POST':
        try:
            date_str = datetime.strptime(request.POST.get('date', ''), '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'Invalid date.')
            return redirect('mark_private_class_attendance', private_class_id=private_class_id)

        status = request.POST.get('status')
        if status not in {'present', 'absent', 'class_cancelled'}:
            messages.error(request, 'Invalid attendance status.')
            return redirect('mark_private_class_attendance', private_class_id=private_class_id)

        student = private_class.user

        if date_str != date.today():
            messages.error(request, 'You can only mark attendance for today.')
            return redirect('mark_private_class_attendance', private_class_id=private_class_id)

        if date_str.weekday() >= 5:  # Saturday or Sunday
            messages.error(request, "Attendance cannot be marked on weekends.")
            return redirect('mark_private_class_attendance', private_class_id=private_class_id)

        PrivateClassAttendance.objects.update_or_create(
            private_class=private_class, student=student, date=date_str,
            defaults={'status': status, 'marked_by': request.user}
        )
        messages.success(request, 'Private class attendance marked successfully.')
        return redirect('mark_private_class_attendance', private_class_id=private_class_id)

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
    available_trainer_ids = [row['trainer'].pk for row in candidate_rows if row['is_available']]

    selected_trainer = None
    selected_trainer_id = request.GET.get('selected_trainer_id') or request.POST.get('selected_trainer_id')
    if selected_trainer_id:
        try:
            selected_trainer_id = int(selected_trainer_id)
        except ValueError:
            selected_trainer_id = None
    if selected_trainer_id in available_trainer_ids:
        selected_trainer = next(row['trainer'] for row in candidate_rows if row['trainer'].pk == selected_trainer_id)

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
        'dashboards/admin/attendance/assign_substitute_trainer.html',
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
    available_trainer_ids = [row['trainer'].pk for row in candidate_rows if row['is_available']]

    selected_trainer = None
    selected_trainer_id = request.GET.get('selected_trainer_id') or request.POST.get('selected_trainer_id')
    if selected_trainer_id:
        try:
            selected_trainer_id = int(selected_trainer_id)
        except ValueError:
            selected_trainer_id = None
    if selected_trainer_id in available_trainer_ids:
        selected_trainer = next(row['trainer'] for row in candidate_rows if row['trainer'].pk == selected_trainer_id)

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
def list_trainer_classes(request, trainer_id):
    if request.user.role != 'admin' and request.user.pk != trainer_id:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    trainer = get_object_or_404(User, pk=trainer_id)
    today = date.today()
    ongoing_classes = ClassSession.objects.filter(
        Q(trainer=trainer) | Q(substitute_trainer=trainer),
        start_date__lte=today,
        end_date__gte=today,
        is_cancelled=False,
    ).order_by('start_time')

    ongoing_private_classes = PrivateClass.objects.filter(
        Q(trainer=trainer) | Q(substitute_trainer=trainer),
        start_date__lte=today,
        end_date__gte=today,
        is_cancelled=False,
    ).order_by('start_date')

    return render(
        request,
        'dashboards/admin/attendance/list_trainer_classes.html',
        {'trainer': trainer, 'ongoing_classes': ongoing_classes, 'ongoing_private_classes': ongoing_private_classes, 'today': today},
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
