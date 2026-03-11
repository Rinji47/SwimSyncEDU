from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.db.models import Q
from .models import ClassSession, ClassType, ClassBooking, PrivateClass, PrivateClassDetails
from pool.models import Pool, TrainerPoolAssignment
from accounts.models import User
from datetime import date, datetime, timedelta, timezone
from django.contrib.auth.decorators import login_required
from decimal import Decimal, ROUND_HALF_UP

# Create your views here.
def _parse_busy_range(raw_from, raw_to):
    busy_from = None
    busy_to = None

    if raw_from:
        try:
            busy_from = datetime.strptime(raw_from, '%Y-%m-%d').date()
        except ValueError:
            busy_from = None

    if raw_to:
        try:
            busy_to = datetime.strptime(raw_to, '%Y-%m-%d').date()
        except ValueError:
            busy_to = None

    if busy_from and busy_to and busy_from > busy_to:
        busy_from, busy_to = busy_to, busy_from

    return busy_from, busy_to


def _build_trainer_unavailability(trainers, busy_from=None, busy_to=None, max_items=None):
    trainer_ids = [trainer.pk for trainer in trainers]
    if not trainer_ids:
        return {}

    today = date.today()
    busy = {}

    group_sessions = ClassSession.objects.filter(
        Q(trainer_id__in=trainer_ids) | Q(substitute_trainer_id__in=trainer_ids),
        end_date__gte=today,
        is_cancelled=False,
    ).order_by('start_date', 'start_time')

    private_sessions = PrivateClass.objects.filter(
        Q(trainer_id__in=trainer_ids) | Q(substitute_trainer_id__in=trainer_ids),
        end_date__gte=today,
        is_cancelled=False,
    ).order_by('start_date', 'start_time')

    if busy_from:
        group_sessions = group_sessions.filter(end_date__gte=busy_from)
        private_sessions = private_sessions.filter(end_date__gte=busy_from)
    if busy_to:
        group_sessions = group_sessions.filter(start_date__lte=busy_to)
        private_sessions = private_sessions.filter(start_date__lte=busy_to)

    for session in group_sessions:
        label = f"{session.start_date:%b %d}-{session.end_date:%b %d} | {session.start_time:%H:%M}-{session.end_time:%H:%M} | Group"
        if session.trainer_id in trainer_ids:
            busy.setdefault(session.trainer_id, []).append(label)
        if session.substitute_trainer_id in trainer_ids:
            busy.setdefault(session.substitute_trainer_id, []).append(label)

    for private in private_sessions:
        label = f"{private.start_date:%b %d}-{private.end_date:%b %d} | {private.start_time:%H:%M}-{private.end_time:%H:%M} | Private"
        if private.trainer_id in trainer_ids:
            busy.setdefault(private.trainer_id, []).append(label)
        if private.substitute_trainer_id in trainer_ids:
            busy.setdefault(private.substitute_trainer_id, []).append(label)

    totals = {}
    visible = {}
    for trainer_id in list(busy.keys()):
        deduped = list(dict.fromkeys(busy[trainer_id]))
        totals[trainer_id] = len(deduped)
        visible[trainer_id] = deduped[:max_items] if max_items else deduped

    return visible, totals


def manage_class_types(request, class_type_id=None):
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

    if class_type_id:
        class_type = get_object_or_404(ClassType, pk=class_type_id)
    else:
        class_type = None

    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        cost = request.POST.get('cost')
        if class_type is not None:
            if class_types.filter(name=name).exclude(class_type_id=class_type_id).exists():
                messages.error(request, 'A class type with this name already exists.')
                return redirect('manage_class_types')
        else:
            if class_types.filter(name=name).exists():
                messages.error(request, 'A class type with this name already exists.')
                return redirect('manage_class_types')
        
        if class_type:
            class_type.name = name
            class_type.description = description
            class_type.cost = cost
            class_type.save()
            messages.success(request, 'Class type updated successfully.')
        else:
            ClassType.objects.create(
                name=name,
                description=description,
                cost=cost
            )
            messages.success(request, 'New class type added successfully.')

        return redirect('manage_class_types')
    
    return render(request, 'dashboards/admin/class_management/admin_manage_class_types.html', {'class_types': class_types})

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
    trainers = User.objects.filter(role='trainer', trainerpoolassignment__pool=pool, trainerpoolassignment__is_active=True).distinct()
    busy_from, busy_to = _parse_busy_range(request.GET.get('busy_from'), request.GET.get('busy_to'))
    unavailability_map, total_map = _build_trainer_unavailability(
        trainers,
        busy_from=busy_from,
        busy_to=busy_to,
    )
    trainer_cards = [
        {
            'trainer': trainer,
            'unavailable_slots': unavailability_map.get(trainer.pk, []),
            'unavailable_total': total_map.get(trainer.pk, 0),
            'unavailable_more': max(total_map.get(trainer.pk, 0) - len(unavailability_map.get(trainer.pk, [])), 0),
        }
        for trainer in trainers
    ]
    return render(request, 'dashboards/admin/class_management/class_session_management/select_trainer_for_class_session.html', {
        'pool': pool,
        'trainer_cards': trainer_cards,
        'busy_from': busy_from,
        'busy_to': busy_to,
    })

def create_class_session_for_pool(request, pool_id, trainer_id):
    if not request.user.is_authenticated or request.user.is_superuser == False:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')
    pool = get_object_or_404(Pool, pk=pool_id, is_closed=False)
    trainer = get_object_or_404(User, pk=trainer_id, role='trainer')
    
    
    if request.method == 'POST':
        try:
            trainer = trainer
            class_type_id = int(request.POST.get('class_type_id'))
            class_name = request.POST.get('class_name')
            seats = int(request.POST.get('seats'))


            class_type = get_object_or_404(ClassType, pk=class_type_id, is_closed=False)
            start_date = datetime.strptime(request.POST.get('start_date'), '%Y-%m-%d').date()
            end_date = start_date + timedelta(days=class_type.duration_days)
            start_time = datetime.strptime(request.POST.get('start_time'), '%H:%M').time()
            end_time = datetime.strptime(request.POST.get('end_time'), '%H:%M').time()

            if seats <= 0:
                messages.error(request, 'Seats must be greater than zero.')
                return redirect('create_class_session_for_pool', pool_id=pool_id, trainer_id=trainer_id)

            if start_date > end_date:
                messages.error(request, 'Start date cannot be after end date.')
                return redirect('create_class_session_for_pool', pool_id=pool_id, trainer_id=trainer_id)
            
            if start_time >= end_time:
                messages.error(request, 'Start time must be before end time. Overnight sessions are not allowed.')
                return redirect('create_class_session_for_pool', pool_id=pool_id, trainer_id=trainer_id)

            today = datetime.now().date()
            max_start_date = today + timedelta(days=31)
            if start_date > max_start_date:
                messages.error(request, 'Start date cannot be more than 1 month from today.')
                return redirect('create_class_session_for_pool', pool_id=pool_id, trainer_id=trainer_id)

            if start_time < datetime.strptime('06:00', '%H:%M').time() or end_time > datetime.strptime('19:00', '%H:%M').time():
                messages.error(request, 'Class time must be between 06:00 and 19:00.')
                return redirect('create_class_session_for_pool', pool_id=pool_id, trainer_id=trainer_id)

            duration = (datetime.combine(datetime.today(), end_time) - datetime.combine(datetime.today(), start_time))
            if duration > timedelta(hours=3):
                messages.error(request, 'Class session duration cannot exceed 3 hours.')
                return redirect('create_class_session_for_pool', pool_id=pool_id, trainer_id=trainer_id)

            if TrainerPoolAssignment.objects.filter(trainer=trainer, pool_id=pool_id, is_active=True).exists() == False:
                messages.error(request, 'Selected trainer is not assigned to the selected pool. Please choose a different trainer or pool.')
                return redirect('create_class_session_for_pool', pool_id=pool_id, trainer_id=trainer_id)
            
            overlapping_classes = ClassSession.objects.filter(
                    pool=pool,
                    is_cancelled=False,
                    start_date__lte=end_date,
                    end_date__gte=start_date,
                    start_time__lt=end_time,
                    end_time__gt=start_time
                )
            if overlapping_classes.exists():
                messages.error(request, 'The selected time overlaps with an existing class session in the same pool. Please choose a different time or pool.')
                return redirect('create_class_session_for_pool', pool_id=pool_id, trainer_id=trainer_id)
                    
            if TrainerPoolAssignment.objects.filter(trainer=trainer, pool_id=pool_id, is_active=True).exists():
                overlapping_private_classes = PrivateClass.objects.filter(
                    trainer=trainer,
                    pool_id=pool_id,
                    start_date__lte=end_date,
                    end_date__gte=start_date, 
                    start_time__lt=end_time,
                    end_time__gt=start_time,
                    is_cancelled=False
                )
            else:
                overlapping_private_classes = PrivateClass.objects.none()
            if overlapping_private_classes.exists():
                messages.error(request, 'The selected trainer has another private class during this time. Please choose a different time or trainer.')
                return redirect('create_class_session_for_pool', pool_id=pool_id, trainer_id=trainer_id)
            
            assignment = TrainerPoolAssignment.objects.filter(trainer=trainer, pool_id=pool_id, is_active=True).first()
            if not assignment or (assignment.end_date is not None and assignment.end_date < end_date):
                end_date_str = assignment.end_date.strftime('%Y-%m-%d') if assignment and assignment.end_date else 'N/A'
                messages.error(
                    request,
                    f'Trainer assignment to this pool ends on {end_date_str}, before the private class ends. Please choose a different trainer, pool, or date.'
                )
                return redirect('create_class_session_for_pool', pool_id=pool_id, trainer_id=trainer_id)
            
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
            return redirect('create_class_session_for_pool', pool_id=pool_id, trainer_id=trainer_id)

    # For GET requests, just render the form
    class_types = ClassType.objects.filter(is_closed=False).all()
    busy_from, busy_to = _parse_busy_range(request.GET.get('busy_from'), request.GET.get('busy_to'))
    unavailability_map, total_map = _build_trainer_unavailability(
        [trainer],
        busy_from=busy_from,
        busy_to=busy_to,
        max_items=6,
    )
    shown_slots = unavailability_map.get(trainer.pk, [])
    total_slots = total_map.get(trainer.pk, 0)
    return render(request, 'dashboards/admin/class_management/class_session_management/create_class_session_for_pool.html', {
        'pool': pool,
        'trainer': trainer,
        'class_types': class_types,
        'today': date.today(),
        'max_start_date': date.today() + timedelta(days=31),
        'trainer_unavailable_slots': shown_slots,
        'trainer_unavailable_total': total_slots,
        'trainer_unavailable_more': max(total_slots - len(shown_slots), 0),
        'busy_from': busy_from,
        'busy_to': busy_to,
    })


def close_class_session(request, class_id):
    class_session = get_object_or_404(ClassSession, pk=class_id)
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
    today = datetime.now().date()
    return render(request, 'dashboards/user/my_classes_bookings.html', {'bookings': bookings, 'today': today})



###########################
# Private Class Management#
###########################

def manage_private_class_prices(request):
    private_class_details = PrivateClassDetails.objects.order_by('-created_at').first()
    price_history = PrivateClassDetails.objects.order_by('-created_at')

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
                last_details.end_date = datetime.now(timezone.utc)
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

# def edit_private_class_price(request, class_id):
#     class_session = get_object_or_404(ClassSession, pk=class_id, class_type__duration_days=0)
    
#     if request.method == 'POST':
#         try:
#             new_price = request.POST.get('total_price')
#             if not new_price:
#                 messages.error(request, 'Price is required.')
#                 return redirect('manage_private_classes')
            
#             class_session.total_price = float(new_price)
#             class_session.save(update_fields=['total_price'])
#             messages.success(request, 'Private class price updated successfully.')
#         except (ValueError, TypeError):
#             messages.error(request, 'Invalid price value.')
    
#     return redirect('manage_private_classes')

def select_trainer_for_private_class(request, pool_id):
    if not request.user.is_authenticated:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')
    
    pool = get_object_or_404(Pool, pk=pool_id, is_closed=False)
    trainers = User.objects.filter(role='trainer', trainerpoolassignment__pool=pool, trainerpoolassignment__is_active=True).distinct()
    busy_from, busy_to = _parse_busy_range(request.GET.get('busy_from'), request.GET.get('busy_to'))
    unavailability_map, total_map = _build_trainer_unavailability(
        trainers,
        busy_from=busy_from,
        busy_to=busy_to,
    )
    trainer_cards = [
        {
            'trainer': trainer,
            'unavailable_slots': unavailability_map.get(trainer.pk, []),
            'unavailable_total': total_map.get(trainer.pk, 0),
            'unavailable_more': max(total_map.get(trainer.pk, 0) - len(unavailability_map.get(trainer.pk, [])), 0),
        }
        for trainer in trainers
    ]
    return render(request, 'classes/select_trainer_for_private_class.html', {
        'pool': pool,
        'trainer_cards': trainer_cards,
        'busy_from': busy_from,
        'busy_to': busy_to,
    })


def book_private_class(request, pool_id, trainer_id):

    if not request.user.is_authenticated:
        messages.error(request, 'You need to log in to book a private class.')
        return redirect('login')

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
            return redirect('select_trainer_for_private_class', pool_id=pool_id)

        if start_time >= end_time:
            messages.error(request, 'Start time must be before end time.')
            return redirect('select_trainer_for_private_class', pool_id=pool_id)

        today = datetime.now().date()
        max_start_date = today + timedelta(days=31)
        if start_date > max_start_date:
            messages.error(request, 'Start date cannot be more than 1 month from today.')
            return redirect('select_trainer_for_private_class', pool_id=pool_id)

        if start_time < datetime.strptime('06:00', '%H:%M').time() or end_time > datetime.strptime('19:00', '%H:%M').time():
            messages.error(request, 'Class time must be between 06:00 and 19:00.')
            return redirect('select_trainer_for_private_class', pool_id=pool_id)

        duration = (
            datetime.combine(datetime.today(), end_time) -
            datetime.combine(datetime.today(), start_time)
        )

        if duration > timedelta(hours=3):
            messages.error(request, 'Class session duration cannot exceed 3 hours.')
            return redirect('select_trainer_for_private_class', pool_id=pool_id)

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

        overlapping_sessions = ClassSession.objects.filter(
            pool=pool,
            is_cancelled=False,
            start_date__lte=end_date,
            end_date__gte=start_date,
            start_time__lt=end_time,
            end_time__gt=start_time
        )

        if overlapping_sessions.exists():
            messages.error(
                request,
                'The selected time overlaps with an existing class session in this pool.'
            )
            return redirect('select_trainer_for_private_class', pool_id=pool_id)

        overlapping_private = PrivateClass.objects.filter(
            trainer=trainer,
            pool=pool,
            is_cancelled=False,
            start_date__lte=end_date,
            end_date__gte=start_date,
            start_time__lt=end_time,
            end_time__gt=start_time
        )

        if overlapping_private.exists():
            messages.error(
                request,
                'The trainer already has a private class during this time.'
            )
            return redirect('select_trainer_for_private_class', pool_id=pool_id)

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
    busy_from, busy_to = _parse_busy_range(request.GET.get('busy_from'), request.GET.get('busy_to'))
    unavailability_map, total_map = _build_trainer_unavailability(
        [trainer],
        busy_from=busy_from,
        busy_to=busy_to,
        max_items=6,
    )
    shown_slots = unavailability_map.get(trainer.pk, [])
    total_slots = total_map.get(trainer.pk, 0)
    return render(request, 'classes/book_private_class.html', {
        'pool_id': pool_id,
        'trainer_id': trainer_id,
        'pool': pool,
        'trainer': trainer,
        'today': date.today(),
        'max_start_date': date.today() + timedelta(days=31),
        'trainer_unavailable_slots': shown_slots,
        'trainer_unavailable_total': total_slots,
        'trainer_unavailable_more': max(total_slots - len(shown_slots), 0),
        'busy_from': busy_from,
        'busy_to': busy_to,
    })

def my_private_classes(request):
    if not request.user.is_authenticated:
        messages.error(request, 'You need to log in to view your private classes.')
        return redirect('login')
    
    private_classes = PrivateClass.objects.filter(user=request.user).select_related('trainer', 'pool').order_by('-created_at')

    today = datetime.now().date()
    now_time = datetime.now().time()  # For checking ongoing status
    return render(request, 'dashboards/user/my_private_classes.html', {
        'private_classes': private_classes,
        'today': today,
        'now_time': now_time,
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
    
    class_sessions = ClassSession.objects.filter(trainer=request.user).select_related('pool', 'class_type').order_by('-start_date')
    return render(request, 'dashboards/trainer/attendance/manage_class_sessions.html', {'class_sessions': class_sessions})

def manage_trainer_private_classes(request):
    if request.user.role != 'trainer':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')
    
    private_classes = PrivateClass.objects.filter(trainer=request.user).select_related('pool').order_by('-created_at')
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
    return render(request, 'dashboards/trainer/attendance/substitute_class_sessions.html', {'substitute_sessions': substitute_sessions})

def trainer_susitute_private_classes_list(request):
    if request.user.role != 'trainer':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')
    
    substitute_private_classes = PrivateClass.objects.filter(substitute_trainer=request.user).select_related('pool', 'trainer').order_by('-created_at')
    return render(request, 'dashboards/trainer/attendance/substitute_private_classes.html', {'substitute_private_classes': substitute_private_classes})

