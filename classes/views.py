from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.db.models import Q
from django.urls import reverse
from urllib3 import request
from .models import ClassSession, ClassType, ClassBooking, PrivateClass, PrivateClassDetails
from pool.models import Pool, TrainerPoolAssignment
from accounts.models import User
from datetime import date, datetime, timedelta
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from decimal import Decimal, ROUND_HALF_UP
from attendance.models import ClassSessionAttendance, PrivateClassAttendance

# Create your views here.

def get_pool_busy_slots(pool, busy_from, busy_to):
    slots = []
    class_sessions = ClassSession.objects.filter(
        pool=pool,
        is_cancelled=False,
        start_date__lte=busy_to,
        end_date__gte=busy_from
    ).values('start_date', 'end_date', 'start_time', 'end_time')

    for session in class_sessions:
        slots.append((session['start_date'],
                      session['end_date'],
                      session['start_time'],
                      session['end_time'],
                      'Group Class'))

    private_classes = PrivateClass.objects.filter(
        pool=pool,
        is_cancelled=False,
        start_date__lte=busy_to,
        end_date__gte=busy_from
    ).values('start_date', 'end_date', 'start_time', 'end_time')

    for private_class in private_classes:
        slots.append((private_class['start_date'],
                      private_class['end_date'],
                      private_class['start_time'],
                      private_class['end_time'],
                      'Private Class'))

    return slots


@login_required
def list_trainer_classes(request, trainer_id):
    if request.user.role != 'admin' and request.user.pk != trainer_id:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    trainer = get_object_or_404(User, pk=trainer_id)
    today = date.today()
    classes = ClassSession.objects.filter(
        trainer=trainer
    ).select_related('pool', 'class_type', 'trainer').order_by('-start_date', '-start_time')

    private_classes = PrivateClass.objects.filter(
        trainer=trainer
    ).select_related('pool', 'trainer', 'user').order_by('-start_date', '-start_time')

    q = (request.GET.get('q') or '').strip()
    status = request.GET.get('status')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    if q:
        classes = classes.filter(
            Q(class_name__icontains=q) |
            Q(pool__name__icontains=q) |
            Q(class_type__name__icontains=q)
        )
        private_classes = private_classes.filter(
            Q(user__full_name__icontains=q) |
            Q(user__username__icontains=q) |
            Q(pool__name__icontains=q)
        )

    if date_from:
        try:
            date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d').date()
            classes = classes.filter(end_date__gte=date_from_parsed)
            private_classes = private_classes.filter(end_date__gte=date_from_parsed)
        except ValueError:
            pass

    if date_to:
        try:
            date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d').date()
            classes = classes.filter(start_date__lte=date_to_parsed)
            private_classes = private_classes.filter(start_date__lte=date_to_parsed)
        except ValueError:
            pass

    if status == 'Upcoming':
        classes = classes.filter(start_date__gt=today, is_cancelled=False)
        private_classes = private_classes.filter(start_date__gt=today, is_cancelled=False)
    elif status == 'Ongoing':
        classes = classes.filter(start_date__lte=today, end_date__gte=today, is_cancelled=False)
        private_classes = private_classes.filter(start_date__lte=today, end_date__gte=today, is_cancelled=False)
    elif status == 'Completed':
        classes = classes.filter(end_date__lt=today, is_cancelled=False)
        private_classes = private_classes.filter(end_date__lt=today, is_cancelled=False)
    elif status == 'Cancelled':
        classes = classes.filter(is_cancelled=True)
        private_classes = private_classes.filter(is_cancelled=True)

    return render(
        request,
        'dashboards/admin/class_management/trainer_class_lists/list_trainer_classes.html',
        {
            'trainer': trainer,
            'classes': classes,
            'private_classes': private_classes,
            'today': today,
        },
    )


@login_required
def list_trainer_sub_classes(request, trainer_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    q = (request.GET.get('q') or '').strip()
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    status = request.GET.get('status')

    trainer = get_object_or_404(User, pk=trainer_id, role='trainer')
    sub_class_sessions = ClassSession.objects.filter(
        substitute_trainer=trainer
    ).select_related('pool', 'class_type', 'trainer').order_by('-start_date', '-start_time')
    sub_private_classes = PrivateClass.objects.filter(
        substitute_trainer=trainer
    ).select_related('pool', 'trainer', 'user').order_by('-start_date', '-start_time')

    if q:
        sub_class_sessions = sub_class_sessions.filter(
            Q(class_name__icontains=q) |
            Q(pool__name__icontains=q) |
            Q(class_type__name__icontains=q)
        )
        sub_private_classes = sub_private_classes.filter(
            Q(user__full_name__icontains=q) |
            Q(user__username__icontains=q) |
            Q(pool__name__icontains=q)
        )

    if date_from:
        try:
            date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d').date()
            sub_class_sessions = sub_class_sessions.filter(end_date__gte=date_from_parsed)
            sub_private_classes = sub_private_classes.filter(end_date__gte=date_from_parsed)
        except ValueError:
            pass

    if date_to:
        try:
            date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d').date()
            sub_class_sessions = sub_class_sessions.filter(start_date__lte=date_to_parsed)
            sub_private_classes = sub_private_classes.filter(start_date__lte=date_to_parsed)
        except ValueError:
            pass

    today = date.today()
    if status == 'Upcoming':
        sub_class_sessions = sub_class_sessions.filter(start_date__gt=today, is_cancelled=False)
        sub_private_classes = sub_private_classes.filter(start_date__gt=today, is_cancelled=False)
    elif status == 'Ongoing':
        sub_class_sessions = sub_class_sessions.filter(start_date__lte=today, end_date__gte=today, is_cancelled=False)
        sub_private_classes = sub_private_classes.filter(start_date__lte=today, end_date__gte=today, is_cancelled=False)
    elif status == 'Completed':
        sub_class_sessions = sub_class_sessions.filter(end_date__lt=today, is_cancelled=False)
        sub_private_classes = sub_private_classes.filter(end_date__lt=today, is_cancelled=False)
    elif status == 'Cancelled':
        sub_class_sessions = sub_class_sessions.filter(is_cancelled=True)
        sub_private_classes = sub_private_classes.filter(is_cancelled=True)

    return render(
        request,
        'dashboards/admin/class_management/trainer_class_lists/list_trainer_sub_classes.html',
        {
            'trainer': trainer,
            'sub_class_sessions': sub_class_sessions,
            'sub_private_classes': sub_private_classes,
            'today': today,
        },
    )


@login_required
def manage_class_types(request):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    class_types = ClassType.objects.all()

    q = (request.GET.get('q') or '').strip()
    status = request.GET.get('status')
    cost_min = request.GET.get('cost_min')
    cost_max = request.GET.get('cost_max')

    if q:
        class_types = class_types.filter(Q(name__icontains=q) | Q(description__icontains=q))

    if status == 'open':
        class_types = class_types.filter(is_closed=False)
    elif status == 'closed':
        class_types = class_types.filter(is_closed=True)

    if cost_min:
        try:
            class_types = class_types.filter(cost__gte=float(cost_min))
        except ValueError:
            pass
    if cost_max:
        try:
            class_types = class_types.filter(cost__lte=float(cost_max))
        except ValueError:
            pass

    return render(request, 'dashboards/admin/class_management/admin_manage_class_types.html', {'class_types': class_types})

@login_required
def view_class_type(request, class_type_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    class_type = get_object_or_404(ClassType, pk=class_type_id)
    return render(request, 'dashboards/admin/class_management/view_class_type.html', {'class_type': class_type})

@login_required
def add_class_type(request):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    if request.method == 'POST':
        name = request.POST.get('name')
        duration_days = request.POST.get('duration_days')
        description = request.POST.get('description')
        cost = request.POST.get('cost')

        if not name or not duration_days or not cost:
            messages.error(request, 'Name, duration, and cost are required fields.')
            return render(request, 'dashboards/admin/class_management/add_class_type.html', {
                'form_data': request.POST,
            })

        if not duration_days.isdigit() or int(duration_days) <= 0:
            messages.error(request, 'Duration must be a positive integer.')
            return render(request, 'dashboards/admin/class_management/add_class_type.html', {
                'form_data': request.POST,
            })

        try:
            cost_value = float(cost)
            if cost_value <= 0:
                messages.error(request, 'Cost cannot be zero or negative.')
                return render(request, 'dashboards/admin/class_management/add_class_type.html', {
                    'form_data': request.POST,
                })

        except ValueError:
            messages.error(request, 'Cost must be a valid number.')
            return render(request, 'dashboards/admin/class_management/add_class_type.html', {
                'form_data': request.POST,
            })

        ClassType.objects.create(
            name=name,
            description=description,
            duration_days=duration_days,
            cost=cost
        )
        messages.success(request, 'New class type added successfully.')
        return redirect('manage_class_types')

    return render(request, 'dashboards/admin/class_management/add_class_type.html')


@login_required
def edit_class_type(request, class_type_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    class_type = get_object_or_404(ClassType, pk=class_type_id)

    if request.method == 'POST':
        name = request.POST.get('name')
        duration_days = request.POST.get('duration_days')
        description = request.POST.get('description')
        cost = request.POST.get('cost')

        if not name or not duration_days or not cost:
            messages.error(request, 'Name, duration, and cost are required fields.')
            return render(request, 'dashboards/admin/class_management/edit_class_type.html', {
                'class_type': class_type,
                'form_data': request.POST,
            })

        if not duration_days.isdigit() or int(duration_days) <= 0:
            messages.error(request, 'Duration must be a positive integer.')
            return render(request, 'dashboards/admin/class_management/edit_class_type.html', {
                'class_type': class_type,
                'form_data': request.POST,
            })

        try:
            cost_value = float(cost)
            if cost_value <= 0:
                messages.error(request, 'Cost cannot be zero or negative.')
                return render(request, 'dashboards/admin/class_management/edit_class_type.html', {
                    'class_type': class_type,
                    'form_data': request.POST,
                })

        except ValueError:
            messages.error(request, 'Cost must be a valid number.')
            return render(request, 'dashboards/admin/class_management/edit_class_type.html', {
                'class_type': class_type,
                'form_data': request.POST,
            })

        class_type.name = name
        class_type.description = description
        class_type.duration_days = duration_days
        class_type.cost = cost
        class_type.save()
        messages.success(request, 'Class type updated successfully.')
        return redirect('manage_class_types')

    return render(request, 'dashboards/admin/class_management/edit_class_type.html', {
        'class_type': class_type,
    })

def close_class_type(request, class_type_id):
    class_type = get_object_or_404(ClassType, pk=class_type_id)
    if class_type.is_closed == True:
        messages.error(request, 'Class type is already closed.')
        return redirect('manage_class_types')

    class_type.is_closed = True

    if class_type.is_closed == True:
        messages.success(request, 'Class type has been closed successfully.')

    class_type.save()
    return redirect('manage_class_types')

def open_class_type(request, class_type_id):
    class_type = get_object_or_404(ClassType, pk=class_type_id)
    if class_type.is_closed == False:
        messages.error(request, 'Class type is already open.')
        return redirect('manage_class_types')

    class_type.is_closed = False
    if class_type.is_closed == False:
        messages.success(request, 'Class type has been opened successfully.')
    class_type.save()
    return redirect('manage_class_types')







############################
# Class Session management #
############################
def manage_class_sessions(request):
    class_sessions = ClassSession.objects.all()
    q = (request.GET.get('q') or '').strip()
    status = request.GET.get('status')
    pool_filter = request.GET.get('pool')
    trainer_filter = request.GET.get('trainer')
    start_filter = request.GET.get('start')
    end_filter = request.GET.get('end')

    # Only list and filter sessions, no edit logic
    if q:
        class_sessions = class_sessions.filter(
            Q(class_name__icontains=q) |
            Q(pool__name__icontains=q) |
            Q(trainer__full_name__icontains=q) |
            Q(trainer__username__icontains=q)
        )

    if status == 'open':
        class_sessions = class_sessions.filter(is_cancelled=False)
    elif status == 'cancelled':
        class_sessions = class_sessions.filter(is_cancelled=True)

    if pool_filter:
        class_sessions = class_sessions.filter(pool_id=pool_filter)
    if trainer_filter:
        class_sessions = class_sessions.filter(trainer_id=trainer_filter)

    if start_filter:
        try:
            start_date = datetime.strptime(start_filter, '%Y-%m-%d').date()
            class_sessions = class_sessions.filter(start_date__gte=start_date)
        except ValueError:
            pass
    if end_filter:
        try:
            end_date = datetime.strptime(end_filter, '%Y-%m-%d').date()
            class_sessions = class_sessions.filter(end_date__lte=end_date)
        except ValueError:
            pass
    pools = Pool.objects.filter(is_closed=False).all()
    class_types = ClassType.objects.filter(is_closed=False).all()
    trainers = User.objects.filter(role='trainer')

    return render(request, 'dashboards/admin/class_management/admin_manage_classes.html', {
        'classes': class_sessions,
        'pools': pools,
        'class_types': class_types,
        'trainers': trainers
    })


@login_required
def view_class_session(request, class_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    class_session = get_object_or_404(
        ClassSession.objects.select_related('pool', 'trainer', 'class_type'),
        pk=class_id
    )
    return render(request, 'dashboards/admin/class_management/view_class_session.html', {
        'class_session': class_session,
    })

def select_pool_for_class_session(request):
    if not request.user.is_authenticated or request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    pools = Pool.objects.filter(is_closed=False).all()
    q = (request.GET.get('q') or '').strip()
    if q:
        pools = pools.filter(Q(name__icontains=q) | Q(address__icontains=q))
    return render(request, 'dashboards/admin/class_management/class_session_management/select_pool_for_class_session.html', {'pools': pools})

def select_trainer_for_class_session(request, pool_id):
    if not request.user.is_authenticated or request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    pool = get_object_or_404(Pool, pk=pool_id, is_closed=False)
    trainers = User.objects.filter(
        role='trainer',
        trainerpoolassignment__pool=pool,
        trainerpoolassignment__is_active=True
    ).distinct().order_by('full_name', 'username')
    q = (request.GET.get('q') or '').strip()

    if q:
        trainers = trainers.filter(
            Q(username__icontains=q) |
            Q(full_name__icontains=q) |
            Q(email__icontains=q) |
            Q(specialization__icontains=q)
        )
    return render(request, 'dashboards/admin/class_management/class_session_management/select_trainer_for_class_session.html', {
        'pool': pool,
        'trainers': trainers,
    })

def calculate_weekday_end_date(start_date, duration_days):

    if duration_days <= 1:
        return start_date

    end_date = start_date
    days_added = 0
    while days_added < duration_days - 1:
        end_date += timedelta(days=1)
        if end_date.weekday() < 5:  # Monday to Friday are considered weekdays
            days_added += 1

    return end_date

def create_class_session_for_pool(request, pool_id, trainer_id):
    if not request.user.is_authenticated or request.user.is_superuser == False:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')
    pool = get_object_or_404(Pool, pk=pool_id, is_closed=False)
    trainer = get_object_or_404(User, pk=trainer_id, role='trainer')
    class_type_id = request.GET.get('class_type_id') or request.POST.get('class_type_id')
    busy_from = request.GET.get('busy_from') or request.POST.get('busy_from')
    busy_to =  request.GET.get('busy_to') or request.POST.get('busy_to')
    redirect_url = reverse('create_class_session_for_pool', args=[pool_id, trainer_id])

    if class_type_id:
        redirect_url = f"{redirect_url}?class_type_id={class_type_id}"

    if request.method == 'POST':
        try:
            trainer = trainer
            class_name = request.POST.get('class_name')
            seats = int(request.POST.get('seats'))

            class_type = get_object_or_404(ClassType, pk=class_type_id, is_closed=False)
            start_date = datetime.strptime(request.POST.get('start_date'), '%Y-%m-%d').date()
            start_time = datetime.strptime(request.POST.get('start_time'), '%H:%M').time()
            end_time = datetime.strptime(request.POST.get('end_time'), '%H:%M').time()

            if start_date.weekday() >= 5:
                messages.error(request, 'Start date cannot be on a weekend. Please select a weekday.')
                return redirect(redirect_url)

            end_date = calculate_weekday_end_date(start_date, class_type.duration_days)

            if seats <= 0:
                messages.error(request, 'Seats must be greater than zero.')
                return redirect(redirect_url)

            if seats > pool.capacity:
                messages.error(request, f'Seats cannot exceed the pool capacity of {pool.capacity}.')
                return redirect(redirect_url)

            if start_date > end_date:
                messages.error(request, 'Start date cannot be after end date.')
                return redirect(redirect_url)

            if start_time >= end_time:
                messages.error(request, 'Start time must be before end time. Overnight sessions are not allowed.')
                return redirect(redirect_url)

            today = datetime.now().date()

            if start_date <= today:
                messages.error(request, 'Start date must be after today.')
                return redirect(redirect_url)

            max_start_date = today + timedelta(days=31)
            if start_date > max_start_date:
                messages.error(request, 'Start date cannot be more than 1 month from today.')
                return redirect(redirect_url)

            if start_time < datetime.strptime('06:00', '%H:%M').time() or end_time > datetime.strptime('19:00', '%H:%M').time():
                messages.error(request, 'Class time must be between 06:00 and 19:00.')
                return redirect(redirect_url)

            duration = (datetime.combine(datetime.today(), end_time) - datetime.combine(datetime.today(), start_time))
            if duration > timedelta(hours=3):
                messages.error(request, 'Class session duration cannot exceed 3 hours.')
                return redirect(redirect_url)

            if TrainerPoolAssignment.objects.filter(trainer=trainer, pool_id=pool_id, is_active=True).exists() == False:
                messages.error(request, 'Selected trainer is not assigned to the selected pool. Please choose a different trainer or pool.')
                return redirect(redirect_url)

            assignment = TrainerPoolAssignment.objects.filter(trainer=trainer, pool_id=pool_id, is_active=True).first()
            if not assignment or (assignment.end_date is not None and assignment.end_date < end_date):
                end_date_str = assignment.end_date.strftime('%Y-%m-%d') if assignment and assignment.end_date else 'N/A'
                messages.error(
                    request,
                    f'Trainer assignment to this pool ends on {end_date_str}, before the class session ends. Please choose a different trainer, pool, or date.'
                )
                return redirect(redirect_url)

            busy_slots = get_pool_busy_slots(pool, start_date, end_date)
            for slot in busy_slots:
                dates_overlap = slot[0] <= end_date and slot[1] >= start_date
                times_overlap = slot[2] < end_time and slot[3] > start_time

                if dates_overlap and times_overlap:
                    messages.error(request, f'The selected time slot overlaps with an existing {slot[4]} from {slot[0]} to {slot[1]} between {slot[2]} and {slot[3]}. Please choose a different time or date.')
                    return redirect(redirect_url)

            ClassSession.objects.create(
                trainer=trainer,
                pool=pool,
                class_type=class_type,
                class_name=class_name,
                seats=seats,
                start_date=start_date,
                end_date=end_date,
                start_time=start_time,
                end_time=end_time
            )
            messages.success(request, 'Class session created successfully.')
            return redirect('manage_classes')

        except (ValueError, TypeError) as e:
            print(e)
            messages.error(request, 'Invalid input. Please check your data and try again.')
            return redirect(redirect_url)

    # For GET requests, just render the form
    selected_class_type = None
    busy_slots = []
    if busy_from and busy_to:
        try:
            busy_from_date = datetime.strptime(busy_from, '%Y-%m-%d').date()
            busy_to_date = datetime.strptime(busy_to, '%Y-%m-%d').date()
            if busy_from_date > busy_to_date:
                messages.error(request, 'Invalid date range for checking pool availability.')
                return redirect(redirect_url)
            busy_slots = get_pool_busy_slots(pool, busy_from_date, busy_to_date)
        except ValueError:
            messages.error(request, 'Invalid date format for checking pool availability.')
            return redirect(redirect_url)

    if class_type_id:
        try:
            selected_class_type = ClassType.objects.get(pk=int(class_type_id), is_closed=False)
        except (ClassType.DoesNotExist, ValueError, TypeError):
            messages.error(request, 'Please select a valid class type.')
            return redirect('select_class_type_for_class_session', pool_id=pool_id, trainer_id=trainer_id)
    else:
        messages.error(request, 'Class type is required.')
        return redirect('select_class_type_for_class_session', pool_id=pool_id, trainer_id=trainer_id)

    return render(request, 'dashboards/admin/class_management/class_session_management/create_class_session_for_pool.html', {
        'pool': pool,
        'trainer': trainer,
        'class_type': selected_class_type,
        'today': date.today(),
        'max_start_date': date.today() + timedelta(days=31),
        'busy_slots': busy_slots,
    })

def select_class_type_for_class_session(request, pool_id, trainer_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    pool = get_object_or_404(Pool, pk=pool_id, is_closed=False)
    trainer = get_object_or_404(User, pk=trainer_id, role='trainer')
    class_types = ClassType.objects.filter(is_closed=False).order_by('name')

    q = (request.GET.get('q') or '').strip()
    if q:
        class_types = class_types.filter(
            Q(name__icontains=q) |
            Q(description__icontains=q) |
            Q(cost__icontains=q) |
            Q(duration_days__icontains=q)
        )

    return render(request, 'dashboards/admin/class_management/class_session_management/select_class_type_for_class_session.html', {
        'pool': pool,
        'trainer': trainer,
        'class_types': class_types,
    })

def open_class_session(request, class_id):
    class_session = get_object_or_404(ClassSession, pk=class_id)
    today = datetime.now().date()
    if class_session.end_date <= today:
        messages.error(request, 'Cannot open a class session that has already ended.')
        return redirect('manage_classes')

    if class_session.is_cancelled == False:
        messages.error(request, 'Class session is already open.')
        return redirect('manage_classes')

    busy_slots = get_pool_busy_slots(class_session.pool, class_session.start_date, class_session.end_date)
    for slot in busy_slots:
        is_same_class = (
            slot[0] == class_session.start_date and
            slot[1] == class_session.end_date and
            slot[2] == class_session.start_time and
            slot[3] == class_session.end_time and
            slot[4] == 'Group Class'
        )

        if is_same_class:
            continue
        dates_overlap = slot[0] <= class_session.end_date and slot[1] >= class_session.start_date
        times_overlap = slot[2] < class_session.end_time and slot[3] > class_session.start_time

        if dates_overlap and times_overlap:
            messages.error(request, f'Cannot open class session because it overlaps with an existing {slot[4]} from {slot[0]} to {slot[1]} between {slot[2]} and {slot[3]}. Please resolve the conflict before opening this class session.')
            return redirect('manage_classes')

    class_session.is_cancelled = False
    if class_session.is_cancelled == False:
        messages.success(request, 'Class session has been opened successfully.')
    class_session.save()
    return redirect('manage_classes')

def close_class_session(request, class_id):
    class_session = get_object_or_404(ClassSession, pk=class_id)
    today = datetime.now().date()
    if class_session.end_date <= today:
        messages.error(request, 'Cannot cancel a class session that has already ended.')
        return redirect('manage_classes')

    if class_session.is_cancelled == True:
        messages.error(request, 'Class session is already cancelled.')
        return redirect('manage_classes')
    class_session.is_cancelled = True
    if class_session.is_cancelled == True:
        messages.success(request, 'Class session has been cancelled successfully.')

    class_session.save()
    return redirect('manage_classes')


@login_required
def book_class(request, class_id):
    class_session = get_object_or_404(ClassSession, pk=class_id)
    if class_session.is_cancelled:
        messages.error(request, 'Cannot book a cancelled class session.')
        return redirect('pool_classes')

    if class_session.end_date is not None and class_session.end_date < datetime.now().date():
        messages.error(request, 'Cannot book a past class session.')
        return redirect('pool_classes')
    return redirect('group_class_payment_checkout', class_id=class_session.id)

def cancel_booked_class(request, booking_id):
    booking = get_object_or_404(ClassBooking, pk=booking_id, user=request.user, is_cancelled=False)

    class_session = booking.class_session

    if class_session.end_date is not None and class_session.end_date < datetime.now().date():
        messages.error(request, 'Cannot cancel booking for a past class session.')
        return redirect('my_bookings')

    if class_session.total_bookings > 0:
        class_session.total_bookings -= 1
        class_session.save(update_fields=['total_bookings'])

    booking.is_cancelled = True
    booking.save(update_fields=['is_cancelled'])

    messages.success(request, 'Class session booking cancelled successfully.')
    return redirect('my_bookings')

def my_bookings(request):
    if not request.user.is_authenticated:
        messages.error(request, 'You need to log in to view your bookings.')
        return redirect('login')

    bookings = ClassBooking.objects.filter(user=request.user).select_related('class_session__pool', 'class_session__class_type').order_by('-booking_date')

    q = (request.GET.get('q') or '').strip()
    if q:
        bookings = bookings.filter(
            Q(class_session__class_name__icontains=q) |
            Q(class_session__pool__name__icontains=q) |
            Q(class_session__class_type__name__icontains=q) |
            Q(class_session__trainer__full_name__icontains=q) |
            Q(class_session__trainer__username__icontains=q)
        )

    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    status = request.GET.get('status')

    if date_from:
        try:
            date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d')
            bookings = bookings.filter(class_session__end_date__gte=date_from_parsed)
        except ValueError:
            pass
    if date_to:
        try:
            date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d')
            bookings = bookings.filter(class_session__start_date__lte=date_to_parsed)
        except ValueError:
            pass

    today = datetime.now().date()

    if status == 'Upcoming':
        bookings = bookings.filter(
            class_session__start_date__gt=today,
            class_session__is_cancelled=False
        )
    elif status == 'Ongoing':
        bookings = bookings.filter(
            class_session__start_date__lte=today,
            class_session__end_date__gte=today,
            class_session__is_cancelled=False
        )
    elif status == 'Completed':
        bookings = bookings.filter(
            class_session__end_date__lt=today,
            class_session__is_cancelled=False
        )
    elif status == 'Cancelled':
        bookings = bookings.filter(
            class_session__is_cancelled=True
        )

    today = datetime.now().date()
    return render(request, 'dashboards/user/my_classes_bookings.html', {'bookings': bookings, 'today': today})


@login_required
def view_my_booking(request, booking_id):
    booking = get_object_or_404(
        ClassBooking.objects.select_related('class_session__pool', 'class_session__trainer', 'class_session__class_type'),
        pk=booking_id,
        user=request.user,
    )
    today = datetime.now().date()
    return render(request, 'dashboards/user/view_my_booking.html', {
        'booking': booking,
        'today': today,
    })


def manage_private_class_prices(request):
    private_class_details = PrivateClassDetails.objects.order_by('-created_at').first()
    price_history = PrivateClassDetails.objects.order_by('-created_at')
    q = (request.GET.get('q') or '').strip()
    status = (request.GET.get('status') or '').strip()
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    if q:
        price_history = price_history.filter(
            Q(private_class_price_per_day__icontains=q) |
            Q(created_at__icontains=q)
        )

    if status == 'active':
        price_history = price_history.filter(end_date__isnull=True)
    elif status == 'ended':
        price_history = price_history.filter(end_date__isnull=False)

    if date_from:
        try:
            date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d')
            price_history = price_history.filter(created_at__date__gte=date_from_parsed)
        except ValueError:
            pass
    if date_to:
        try:
            date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d')
            price_history = price_history.filter(created_at__date__lte=date_to_parsed)
        except ValueError:
            pass

    context = {
        'private_class_price_per_day': private_class_details.private_class_price_per_day if private_class_details else None,
        'price_history': price_history
    }

    return render(request, 'dashboards/admin/admin_manage_private_class_prices.html', context)

def new_private_class_price(request):
    if not request.user.is_authenticated or request.user.role != 'admin':
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('index')

    if request.method == 'POST':
        try:
            new_price = request.POST.get('private_class_price_per_day')
            if not new_price:
                messages.error(request, 'Price is required.')
                return redirect('manage_private_class_prices')

            last_details = PrivateClassDetails.objects.order_by('-created_at').first()
            if last_details:
                last_details.end_date = timezone.now()
                last_details.save(update_fields=['end_date'])

            PrivateClassDetails.objects.create(private_class_price_per_day=float(new_price))
            messages.success(request, 'New private class price created successfully.')

        except (ValueError, TypeError):
            messages.error(request, 'Invalid price value.')
            return redirect('manage_private_class_prices')

    return redirect('manage_private_class_prices')

def manage_private_classes(request):
    private_classes = PrivateClass.objects.select_related('pool', 'trainer', 'user').order_by('-start_date')

    q = (request.GET.get('q') or '').strip()
    status = request.GET.get('status')
    pool_filter = request.GET.get('pool')
    trainer_filter = request.GET.get('trainer')

    if q:
        private_classes = private_classes.filter(
            Q(user__full_name__icontains=q) |
            Q(user__username__icontains=q) |
            Q(user__email__icontains=q) |
            Q(pool__name__icontains=q) |
            Q(trainer__full_name__icontains=q) |
            Q(trainer__username__icontains=q) |
            Q(trainer__email__icontains=q)
        )

    if status == 'active':
        private_classes = private_classes.filter(is_cancelled=False)
    elif status == 'cancelled':
        private_classes = private_classes.filter(is_cancelled=True)

    if pool_filter:
        private_classes = private_classes.filter(pool_id=pool_filter)
    if trainer_filter:
        private_classes = private_classes.filter(trainer_id=trainer_filter)

    pools = Pool.objects.filter(is_closed=False).all()
    trainers = User.objects.filter(role='trainer')

    return render(request, 'dashboards/admin/admin_manage_private_classes.html', {
        'private_classes': private_classes,
        'pools': pools,
        'trainers': trainers
    })

def select_trainer_for_private_class(request, pool_id):
    if not request.user.is_authenticated:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    pool = get_object_or_404(Pool, pk=pool_id, is_closed=False)
    trainers = User.objects.filter(
        role='trainer',
        trainerpoolassignment__pool=pool,
        trainerpoolassignment__is_active=True
    ).distinct().order_by('full_name', 'username')
    q = (request.GET.get('q') or '').strip()

    if q:
        trainers = trainers.filter(
            Q(username__icontains=q) |
            Q(full_name__icontains=q) |
            Q(email__icontains=q) |
            Q(specialization__icontains=q)
        )
    return render(request, 'classes/select_trainer_for_private_class.html', {
        'pool': pool,
        'trainers': trainers,
    })


def book_private_class(request, pool_id, trainer_id):

    if not request.user.is_authenticated:
        messages.error(request, 'You need to log in to book a private class.')
        return redirect('login')

    busy_from = request.GET.get('busy_from') or request.POST.get('busy_from')
    busy_to = request.GET.get('busy_to') or request.POST.get('busy_to')

    if request.method == 'POST':
        try:
            trainer_id = int(request.POST.get('trainer_id'))
            pool_id = int(request.POST.get('pool_id'))

            start_date = datetime.strptime(
                request.POST.get('start_date'), '%Y-%m-%d'
            ).date()

            end_date = datetime.strptime(
                request.POST.get('end_date'), '%Y-%m-%d'
            ).date()

            start_time = datetime.strptime(
                request.POST.get('start_time'), '%H:%M'
            ).time()

            end_time = datetime.strptime(
                request.POST.get('end_time'), '%H:%M'
            ).time()

        except (ValueError, TypeError):
            messages.error(request, 'Invalid input. Please check your data and try again.')
            return redirect('select_trainer_for_private_class', pool_id=pool_id)

        if start_date > end_date:
            messages.error(request, 'Start date cannot be after end date.')
            return redirect('book_private_class', pool_id=pool_id, trainer_id=trainer_id)

        if start_time >= end_time:
            messages.error(request, 'Start time must be before end time.')
            return redirect('book_private_class', pool_id=pool_id, trainer_id=trainer_id)

        today = datetime.now().date()
        if start_date <= today:
            messages.error(request, 'Start date must be after today.')
            return redirect('book_private_class', pool_id=pool_id, trainer_id=trainer_id)

        max_start_date = today + timedelta(days=31)
        if start_date > max_start_date:
            messages.error(request, 'Start date cannot be more than 1 month from today.')
            return redirect('book_private_class', pool_id=pool_id, trainer_id=trainer_id)

        if start_time < datetime.strptime('06:00', '%H:%M').time() or end_time > datetime.strptime('19:00', '%H:%M').time():
            messages.error(request, 'Class time must be between 06:00 and 19:00.')
            return redirect('book_private_class', pool_id=pool_id, trainer_id=trainer_id)

        duration = (
            datetime.combine(datetime.today(), end_time) -
            datetime.combine(datetime.today(), start_time)
        )

        if duration > timedelta(hours=3):
            messages.error(request, 'Class session duration cannot exceed 3 hours.')
            return redirect('book_private_class', pool_id=pool_id, trainer_id=trainer_id)

        trainer = get_object_or_404(User, pk=trainer_id, role='trainer')
        pool = get_object_or_404(Pool, pk=pool_id)

        assignment = TrainerPoolAssignment.objects.filter(
            trainer_id=trainer_id,
            pool_id=pool_id,
            is_active=True
        ).first()

        if not assignment:
            messages.error(
                request,
                'Selected trainer is not assigned to the selected pool.'
            )
            return redirect('select_trainer_for_private_class', pool_id=pool_id)

        if assignment.end_date and assignment.end_date < end_date:
            messages.error(
                request,
                f'Trainer assignment ends on {assignment.end_date.strftime("%Y-%m-%d")}.'
            )
            return redirect('select_trainer_for_private_class', pool_id=pool_id)

        busy_slots = get_pool_busy_slots(pool, start_date, end_date)
        for slot in busy_slots:
            dates_overlap = slot[0] <= end_date and slot[1] >= start_date
            times_overlap = slot[2] < end_time and slot[3] > start_time

            if dates_overlap and times_overlap:
                messages.error(
                    request,
                    f'The selected time slot overlaps with an existing {slot[4]} from {slot[0]} to {slot[1]} between {slot[2]} and {slot[3]}. Please choose a different time or date.'
                )
                return redirect('book_private_class', pool_id=pool_id, trainer_id=trainer_id)

        weekdays_count = 0
        day_cursor = start_date
        while day_cursor <= end_date:
            if day_cursor.weekday() < 5:
                weekdays_count += 1
            day_cursor += timedelta(days=1)
        if weekdays_count <= 0:
            messages.error(request, 'Selected date range has no weekdays for private class.')
            return redirect('book_private_class', pool_id=pool_id, trainer_id=trainer_id)

        pricing = PrivateClassDetails.objects.order_by('-created_at').first()
        price_per_day = Decimal(pricing.private_class_price_per_day if pricing else 0).quantize(Decimal('0.01'))
        base_amount = (price_per_day * Decimal(weekdays_count)).quantize(Decimal('0.01'))
        tax_amount = (base_amount * Decimal('0.13')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_amount = (base_amount + tax_amount).quantize(Decimal('0.01'))

        request.session['private_class_checkout'] = {
            'pool_id': pool_id,
            'trainer_id': trainer_id,
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat(),
            'start_time': start_time.strftime('%H:%M'),
            'end_time': end_time.strftime('%H:%M'),
            'weekdays_count': weekdays_count,
            'price_per_day': str(price_per_day),
            'base_amount': str(base_amount),
            'tax_amount': str(tax_amount),
            'total_amount': str(total_amount),
        }
        return redirect('private_class_payment_checkout')

    pool = get_object_or_404(Pool, pk=pool_id, is_closed=False)
    trainer = get_object_or_404(User, pk=trainer_id, role='trainer')
    busy_slots = []
    if busy_from and busy_to:
        try:
            busy_from_date = datetime.strptime(busy_from, '%Y-%m-%d').date()
            busy_to_date = datetime.strptime(busy_to, '%Y-%m-%d').date()
            if busy_from_date > busy_to_date:
                messages.error(request, 'Invalid date range for checking pool availability.')
                return redirect('book_private_class', pool_id=pool_id, trainer_id=trainer_id)
            busy_slots = get_pool_busy_slots(pool, busy_from_date, busy_to_date)
        except ValueError:
            messages.error(request, 'Invalid date format for checking pool availability.')
            return redirect('book_private_class', pool_id=pool_id, trainer_id=trainer_id)

    return render(request, 'classes/book_private_class.html', {
        'pool_id': pool_id,
        'trainer_id': trainer_id,
        'pool': pool,
        'trainer': trainer,
        'today': date.today(),
        'max_start_date': date.today() + timedelta(days=31),
        'busy_slots': busy_slots,
    })

def my_private_classes(request):
    if not request.user.is_authenticated:
        messages.error(request, 'You need to log in to view your private classes.')
        return redirect('login')

    private_classes = PrivateClass.objects.filter(user=request.user).select_related('trainer', 'pool').order_by('-created_at')

    q = (request.GET.get('q') or '').strip()
    if q:
        private_classes = private_classes.filter(
            Q(pool__name__icontains=q) |
            Q(trainer__full_name__icontains=q) |
            Q(trainer__username__icontains=q) |
            Q(trainer__email__icontains=q)
        )

    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    status = request.GET.get('status')

    if date_from:
        try:
            date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d')
            private_classes = private_classes.filter(end_date__gte=date_from_parsed)
        except ValueError:
            pass
    if date_to:
        try:
            date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d')
            private_classes = private_classes.filter(start_date__lte=date_to_parsed)
        except ValueError:
            pass

    today = datetime.now().date()

    if status == 'Upcoming':
        private_classes = private_classes.filter(
            end_date__gt=today,
            is_cancelled=False
        )
    elif status == 'Ongoing':
        private_classes = private_classes.filter(
            start_date__lte=today,
            end_date__gte=today,
            is_cancelled=False
        )
    elif status == 'Completed':
        private_classes = private_classes.filter(
            end_date__lt=today,
            is_cancelled=False
        )
    elif status == 'Cancelled':
        private_classes = private_classes.filter(
            is_cancelled=True
        )

    now_time = datetime.now().time()  # For checking ongoing status
    return render(request, 'dashboards/user/my_private_classes.html', {
        'private_classes': private_classes,
        'today': today,
        'now_time': now_time,
    })


@login_required
def view_my_private_class(request, private_class_id):
    private_class = get_object_or_404(
        PrivateClass.objects.select_related('trainer', 'pool', 'user'),
        pk=private_class_id,
        user=request.user,
    )
    today = datetime.now().date()
    return render(request, 'dashboards/user/view_my_private_class.html', {
        'private_class': private_class,
        'today': today,
    })

def cancel_private_class(request, private_class_id):
    private_class = get_object_or_404(PrivateClass, pk=private_class_id, user=request.user, is_cancelled=False)
    if private_class.end_date < datetime.now().date():
        messages.error(request, 'Cannot cancel a past private class.')
        return redirect('my_private_classes')
    if private_class.is_cancelled:
        messages.error(request, 'Private class is already cancelled.')
        return redirect('my_private_classes')
    private_class.is_cancelled = True
    private_class.save()
    messages.success(request, 'Private class cancelled successfully.')
    return redirect('my_private_classes')




## Trainer's view of managing their class sessions and private classes ##
def manage_trainer_class_session(request):
    if request.user.role != 'trainer':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    class_sessions = ClassSession.objects.filter(trainer=request.user).select_related('pool', 'class_type').order_by('-start_date', '-start_time')
    q = (request.GET.get('q') or '').strip()
    status = request.GET.get('status')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    if q:
        class_sessions = class_sessions.filter(
            Q(class_name__icontains=q) |
            Q(pool__name__icontains=q) |
            Q(class_type__name__icontains=q)
        )

    if date_from:
        try:
            date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d').date()
            class_sessions = class_sessions.filter(end_date__gte=date_from_parsed)
        except ValueError:
            pass

    if date_to:
        try:
            date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d').date()
            class_sessions = class_sessions.filter(start_date__lte=date_to_parsed)
        except ValueError:
            pass

    today = datetime.now().date()
    if status == 'Upcoming':
        class_sessions = class_sessions.filter(start_date__gt=today, is_cancelled=False)
    elif status == 'Ongoing':
        class_sessions = class_sessions.filter(start_date__lte=today, end_date__gte=today, is_cancelled=False)
    elif status == 'Completed':
        class_sessions = class_sessions.filter(end_date__lt=today, is_cancelled=False)
    elif status == 'Cancelled':
        class_sessions = class_sessions.filter(is_cancelled=True)

    return render(request, 'dashboards/trainer/attendance/manage_class_sessions.html', {'class_sessions': class_sessions})

def manage_trainer_private_classes(request):
    if request.user.role != 'trainer':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    private_classes = PrivateClass.objects.filter(trainer=request.user).select_related('pool').order_by('-created_at')
    q = (request.GET.get('q') or '').strip()
    status = request.GET.get('status')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    if q:
        private_classes = private_classes.filter(
            Q(user__full_name__icontains=q) |
            Q(user__username__icontains=q) |
            Q(pool__name__icontains=q)
        )

    if date_from:
        try:
            date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d').date()
            private_classes = private_classes.filter(end_date__gte=date_from_parsed)
        except ValueError:
            pass

    if date_to:
        try:
            date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d').date()
            private_classes = private_classes.filter(start_date__lte=date_to_parsed)
        except ValueError:
            pass

    today = datetime.now().date()
    if status == 'Upcoming':
        private_classes = private_classes.filter(start_date__gt=today, is_cancelled=False)
    elif status == 'Ongoing':
        private_classes = private_classes.filter(start_date__lte=today, end_date__gte=today, is_cancelled=False)
    elif status == 'Completed':
        private_classes = private_classes.filter(end_date__lt=today, is_cancelled=False)
    elif status == 'Cancelled':
        private_classes = private_classes.filter(is_cancelled=True)

    return render(request, 'dashboards/trainer/attendance/manage_private_classes.html', {'private_classes': private_classes})

def select_class_sessions_for_attendance_history(request, class_session_id):
    if request.user.role != 'trainer':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    class_session = get_object_or_404(ClassSession, id=class_session_id)

    if class_session.trainer != request.user and class_session.substitute_trainer != request.user:
        messages.error(request, 'You can only view attendance history for your own classes or substitute class.')
        return redirect('manage_trainer_class_session')

    return redirect('class_session_attendance_history', class_session_id=class_session_id)

def select_private_classes_for_attendance_history(request, private_class_id):
    if request.user.role != 'trainer':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    private_class = get_object_or_404(PrivateClass, id=private_class_id)

    if private_class.trainer != request.user and private_class.substitute_trainer != request.user:
        messages.error(request, 'You can only view attendance history for your own classes or substitute class.')
        return redirect('manage_trainer_private_classes')

    return redirect('private_class_attendance_history', private_class_id=private_class_id)


def trainer_susitute_class_sessions_list(request):
    if request.user.role != 'trainer':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    substitute_sessions = ClassSession.objects.filter(substitute_trainer=request.user).select_related('pool', 'class_type', 'trainer').order_by('-start_date')
    q = (request.GET.get('q') or '').strip()
    if q:
        substitute_sessions = substitute_sessions.filter(
            Q(class_name__icontains=q) |
            Q(pool__name__icontains=q) |
            Q(class_type__name__icontains=q) |
            Q(trainer__full_name__icontains=q) |
            Q(trainer__username__icontains=q)
        )
    return render(request, 'dashboards/trainer/attendance/substitute_class_sessions.html', {'substitute_sessions': substitute_sessions})

def trainer_susitute_private_classes_list(request):
    if request.user.role != 'trainer':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    substitute_private_classes = PrivateClass.objects.filter(substitute_trainer=request.user).select_related('pool', 'trainer').order_by('-created_at')
    q = (request.GET.get('q') or '').strip()
    if q:
        substitute_private_classes = substitute_private_classes.filter(
            Q(user__full_name__icontains=q) |
            Q(user__username__icontains=q) |
            Q(pool__name__icontains=q) |
            Q(trainer__full_name__icontains=q) |
            Q(trainer__username__icontains=q)
        )
    return render(request, 'dashboards/trainer/attendance/substitute_private_classes.html', {'substitute_private_classes': substitute_private_classes})

@login_required
def todays_classes(request):
    if request.user.role != 'user':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    today = timezone.localdate()
    now_time = timezone.localtime().time()
    is_weekday = today.weekday() < 5

    group_bookings = ClassBooking.objects.none()
    private_classes = PrivateClass.objects.none()
    if is_weekday:
        group_bookings = ClassBooking.objects.filter(
            user=request.user,
            is_cancelled=False,
            class_session__is_cancelled=False,
            class_session__start_date__lte=today,
            class_session__end_date__gte=today,
        ).select_related(
            'class_session',
            'class_session__trainer',
            'class_session__pool',
            'class_session__class_type',
        ).order_by('class_session__start_time')

    if is_weekday:
        private_classes = PrivateClass.objects.filter(
            user=request.user,
            is_cancelled=False,
            start_date__lte=today,
            end_date__gte=today,
        ).select_related(
            'trainer',
            'pool',
            'substitute_trainer',
        ).order_by('start_time')

    q = (request.GET.get('q') or '').strip()
    if q:
        group_bookings = group_bookings.filter(
            Q(class_session__class_name__icontains=q) |
            Q(class_session__pool__name__icontains=q) |
            Q(class_session__class_type__name__icontains=q) |
            Q(class_session__trainer__full_name__icontains=q) |
            Q(class_session__substitute_trainer__full_name__icontains=q) |
            Q(class_session__substitute_trainer__username__icontains=q)
        )

        private_classes = private_classes.filter(
            Q(pool__name__icontains=q) |
            Q(trainer__full_name__icontains=q) |
            Q(trainer__username__icontains=q) |
            Q(substitute_trainer__full_name__icontains=q) |
            Q(substitute_trainer__username__icontains=q)
        )

    if not is_weekday:
        group_bookings = ClassBooking.objects.none()
        private_classes = PrivateClass.objects.none()
        weekend = "It is weekend today. No classes are scheduled for today."
        context = {
            'today': today,
            'is_weekday': is_weekday,
            'group_bookings': group_bookings,
            'private_classes': private_classes,
            'weekend': weekend,
            'now_time': now_time,
        }

    else:   
        context = {
            'today': today,
            'is_weekday': is_weekday,
            'group_bookings': group_bookings,
            'private_classes': private_classes,
            'now_time': now_time,
        }

    return render(request, 'dashboards/user/todays_classes.html', context)

@login_required
def select_session_to_view_students_list(request):
    if request.user.role != 'trainer' and request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')
    q = (request.GET.get('q') or '').strip()
    status = (request.GET.get('status') or '').strip()

    if request.user.role == 'trainer':
        sessions = ClassSession.objects.filter(
            Q(trainer=request.user) | Q(substitute_trainer=request.user)
        ).select_related('pool', 'class_type', 'trainer', 'substitute_trainer').order_by('-end_date')
        if q:
            sessions = sessions.filter(
                Q(class_name__icontains=q) |
                Q(pool__name__icontains=q) |
                Q(class_type__name__icontains=q)
            )
        if status == 'active':
            sessions = sessions.filter(is_cancelled=False)
        elif status == 'cancelled':
            sessions = sessions.filter(is_cancelled=True)
        return render(request, 'dashboards/trainer/student_list/select_session_to_view_students_list.html', {'sessions': sessions})
    else:
        sessions = ClassSession.objects.all().select_related('pool', 'class_type', 'trainer', 'substitute_trainer').order_by('-end_date')
        if q:
            sessions = sessions.filter(
                Q(class_name__icontains=q) |
                Q(pool__name__icontains=q) |
                Q(class_type__name__icontains=q) |
                Q(trainer__full_name__icontains=q) |
                Q(trainer__username__icontains=q)
            )
        if status == 'active':
            sessions = sessions.filter(is_cancelled=False)
        elif status == 'cancelled':
            sessions = sessions.filter(is_cancelled=True)
        return render(request, 'dashboards/admin/student_list/select_session_to_view_students_list.html', {'sessions': sessions})

@login_required
def students_list_for_class_session(request, class_session_id):
    class_session = get_object_or_404(
        ClassSession.objects.select_related('pool', 'class_type', 'trainer', 'substitute_trainer'),
        pk=class_session_id
    )

    if request.user.role != 'trainer' and request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    if request.user.role == 'trainer' and class_session.trainer != request.user and class_session.substitute_trainer != request.user:
        messages.error(request, 'You can only view students list for your own classes or substitute class.')
        return redirect('index')

    bookings = ClassBooking.objects.filter(class_session=class_session, is_cancelled=False).select_related('user')

    student_name = (request.GET.get('student_name') or '').strip()
    if student_name:
        bookings = bookings.filter(
            Q(user__full_name__icontains=student_name) |
            Q(user__username__icontains=student_name)
        )

    if not bookings.exists():
        messages.info(request, 'No students have booked this class session.')
        return redirect('select_session_to_view_students_list')

    if request.user.role == 'trainer':
        return render(request, 'dashboards/trainer/student_list/students_list_for_class_session.html', {
            'class_session': class_session,
            'bookings': bookings,
        })
    else:
        return render(request, 'dashboards/admin/student_list/students_list_for_class_session.html', {
            'class_session': class_session,
            'bookings': bookings,
        })

@login_required
def select_private_class_to_view_students_list(request):
    if request.user.role != 'trainer' and request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')
    q = (request.GET.get('q') or '').strip()
    status = (request.GET.get('status') or '').strip()
    if request.user.role == 'trainer':
        private_classes = PrivateClass.objects.filter(
            Q(trainer=request.user) | Q(substitute_trainer=request.user)
        ).select_related('pool', 'user', 'trainer', 'substitute_trainer').order_by('-end_date')
        if q:
            private_classes = private_classes.filter(
                Q(user__full_name__icontains=q) |
                Q(user__username__icontains=q) |
                Q(pool__name__icontains=q)
            )
        if status == 'active':
            private_classes = private_classes.filter(is_cancelled=False)
        elif status == 'cancelled':
            private_classes = private_classes.filter(is_cancelled=True)
        return render(request, 'dashboards/trainer/student_list/select_private_class_to_view_students_list.html', {'private_classes': private_classes})
    else:
        private_classes = PrivateClass.objects.all().select_related('pool', 'user', 'trainer', 'substitute_trainer').order_by('-end_date')
        if q:
            private_classes = private_classes.filter(
                Q(user__full_name__icontains=q) |
                Q(user__username__icontains=q) |
                Q(pool__name__icontains=q) |
                Q(trainer__full_name__icontains=q) |
                Q(trainer__username__icontains=q)
            )
        if status == 'active':
            private_classes = private_classes.filter(is_cancelled=False)
        elif status == 'cancelled':
            private_classes = private_classes.filter(is_cancelled=True)
        return render(request, 'dashboards/admin/student_list/select_private_class_to_view_students_list.html', {'private_classes': private_classes})

@login_required
def students_list_for_private_class(request, private_class_id):
    private_class = get_object_or_404(
        PrivateClass.objects.select_related('pool', 'user', 'trainer', 'substitute_trainer'),
        pk=private_class_id
    )

    if request.user.role != 'trainer' and request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    if request.user.role == 'trainer' and private_class.trainer != request.user and private_class.substitute_trainer != request.user:
        messages.error(request, 'You can only view students list for your own classes or substitute class.')
        return redirect('index')

    if request.user.role == 'trainer':
        return render(request, 'dashboards/trainer/student_list/students_list_for_private_class.html', {
            'private_class': private_class,
        })
    else:
        return render(request, 'dashboards/admin/student_list/students_list_for_private_class.html', {
            'private_class': private_class,
        })

@login_required
def edit_class_session(request, class_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    class_session = get_object_or_404(ClassSession, pk=class_id)
    busy_from = request.GET.get('busy_from') or request.POST.get('busy_from')
    busy_to = request.GET.get('busy_to') or request.POST.get('busy_to')

    class_type = class_session.class_type

    if class_session.end_date < datetime.now().date():
        messages.error(request, 'Cannot edit a class session that has already ended.')
        return redirect('manage_classes')

    selected_trainer = None
    trainer_id = request.GET.get('trainer_id')
    if trainer_id:
        try:
            trainer_id = int(trainer_id)
            selected_trainer = User.objects.filter(pk=trainer_id, role='trainer').first()
        except (ValueError, TypeError):
            selected_trainer = None

    if selected_trainer and not TrainerPoolAssignment.objects.filter(trainer=selected_trainer, pool=class_session.pool, is_active=True).exists():
        messages.error(request, 'The selected trainer is not assigned to the pool for this class session.')
        return redirect('select_trainer_for_edit_class_session', class_id=class_id)

    if selected_trainer == class_session.trainer:
        messages.info(request, 'The selected trainer is already assigned to this class session.')
        return redirect('select_trainer_for_edit_class_session', class_id=class_id)

    if request.method == 'POST':
        try:
            class_name = request.POST.get('class_name')
            seats = int(request.POST.get('seats'))
            start_date = datetime.strptime(request.POST.get('start_date'), '%Y-%m-%d').date()
            
            start_time = datetime.strptime(request.POST.get('start_time'), '%H:%M').time()
            end_time = datetime.strptime(request.POST.get('end_time'), '%H:%M').time()

            trainer_id = request.POST.get('trainer_id') or class_session.trainer_id
            trainer = get_object_or_404(User, pk=int(trainer_id), role='trainer')

            if seats <= 0:
                messages.error(request, 'Seats must be greater than zero.')
                return redirect('edit_class', class_id=class_id)

            if start_date.weekday() >= 5:
                messages.error(request, 'Start date cannot be on a weekend. Please select a weekday.')
                return redirect('edit_class', class_id=class_id)

            end_date = calculate_weekday_end_date(start_date, class_type.duration_days)

            if seats < class_session.total_bookings:
                messages.error(
                    request,
                    f'Seats cannot be less than the current total bookings ({class_session.total_bookings}).'
                )
                return redirect('edit_class', class_id=class_id)

            if seats > class_session.pool.capacity:
                messages.error(
                    request,
                    f'Seats cannot exceed the pool capacity of {class_session.pool.capacity}.'
                )
                return redirect('edit_class', class_id=class_id)

            if start_date > end_date:
                messages.error(request, 'Start date cannot be after end date.')
                return redirect('edit_class', class_id=class_id)

            if start_time >= end_time:
                messages.error(request, 'Start time must be before end time. Overnight sessions are not allowed.')
                return redirect('edit_class', class_id=class_id)

            if start_time < datetime.strptime('06:00', '%H:%M').time() or end_time > datetime.strptime('19:00', '%H:%M').time():
                messages.error(request, 'Class time must be between 06:00 and 19:00.')
                return redirect('edit_class', class_id=class_id)

            duration = (datetime.combine(datetime.today(), end_time) - datetime.combine(datetime.today(), start_time))
            if duration > timedelta(hours=3):
                messages.error(request, 'Class session duration cannot exceed 3 hours.')
                return redirect('edit_class', class_id=class_id)

            assignment = TrainerPoolAssignment.objects.filter(
                trainer=trainer,
                pool=class_session.pool,
                is_active=True,
                start_date__lte=start_date,
            ).filter(
                Q(end_date__isnull=True) | Q(end_date__gte=end_date)
            ).first()
            if not assignment:
                messages.error(
                    request,
                    'Selected trainer is not actively assigned to this pool for the full class session period.'
                )
                return redirect('edit_class', class_id=class_id)

            busy_slots = get_pool_busy_slots(class_session.pool, start_date, end_date)
            for slot in busy_slots:
                dates_overlap = slot[0] <= end_date and slot[1] >= start_date
                times_overlap = slot[2] < end_time and slot[3] > start_time
                is_same_class = (
                    slot[0] == class_session.start_date and
                    slot[1] == class_session.end_date and
                    slot[2] == class_session.start_time and
                    slot[3] == class_session.end_time and
                    slot[4] == 'Group Class'
                )

                if is_same_class:
                    continue

                if dates_overlap and times_overlap:
                    messages.error(request, f'The selected time slot overlaps with an existing {slot[4]} from {slot[0]} to {slot[1]} between {slot[2]} and {slot[3]}. Please choose a different time or date.')
                    return redirect('edit_class', class_id=class_id)

            class_session.class_name = class_name
            class_session.seats = seats
            class_session.start_date = start_date
            class_session.end_date = end_date
            class_session.start_time = start_time
            class_session.end_time = end_time
            class_session.trainer = trainer

            class_session.save()
            messages.success(request, 'Class session updated successfully.')
            return redirect('manage_classes')
        except (ValueError, TypeError) as e:
            print(e)
            messages.error(request, 'Invalid input. Please check your data and try again.')
            return redirect('edit_class', class_id=class_id)

    busy_slots = []
    if busy_from and busy_to:
        try:
            busy_from_date = datetime.strptime(busy_from, '%Y-%m-%d').date()
            busy_to_date = datetime.strptime(busy_to, '%Y-%m-%d').date()
            if busy_from_date > busy_to_date:
                messages.error(request, 'Invalid date range for checking pool availability.')
                return redirect('edit_class', class_id=class_id)
            busy_slots = get_pool_busy_slots(class_session.pool, busy_from_date, busy_to_date)
        except ValueError:
            messages.error(request, 'Invalid date format for checking pool availability.')
            return redirect('edit_class', class_id=class_id)

    return render(
        request,
        'dashboards/admin/class_management/class_session_management/edit_class_session.html',
        {
            'class_session': class_session,
            'selected_trainer': selected_trainer,
            'busy_slots': busy_slots,
        }
    )


@login_required
def select_trainer_for_edit_class_session(request, class_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    class_session = get_object_or_404(ClassSession, pk=class_id)
    pool = class_session.pool
    trainers = User.objects.filter(
        role='trainer',
        trainerpoolassignment__pool=pool,
        trainerpoolassignment__is_active=True
    ).distinct().order_by('full_name', 'username')
    q = (request.GET.get('q') or '').strip()

    if q:
        trainers = trainers.filter(
            Q(username__icontains=q) |
            Q(full_name__icontains=q) |
            Q(email__icontains=q) |
            Q(specialization__icontains=q)
        )
    if not trainers.exists():
        messages.error(request, 'No trainers are currently assigned to the pool for this class session. Please assign a trainer to the pool before selecting a trainer for this class session.')
        return redirect('edit_class_session', class_id=class_id)

    return render(
        request,
        'dashboards/admin/class_management/class_session_management/select_trainer_for_edit_class_session.html',
        {
            'class_session': class_session,
            'trainers': trainers,
        }
    )
