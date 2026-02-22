from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.db.models import Q
from .models import ClassSession, ClassType, ClassBooking, PrivateClass, PrivateClassAttendance, PrivateClassDetails
from pool.models import Pool, TrainerPoolAssignment
from accounts.models import User
from datetime import datetime, timedelta, timezone
from django.contrib.auth.decorators import login_required

# Create your views here.
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
    
    return render(request, 'dashboards/admin/admin_manage_class_types.html', {'class_types': class_types})

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

def manage_class_sessions(request, class_id=None):
    if class_id:
        class_session = get_object_or_404(ClassSession, pk=class_id)
    else:
        class_session = None
    
    if request.method == 'POST':
        try:
            user_id = int(request.POST.get('user_id'))
            pool_id = int(request.POST.get('pool_id'))
            class_type_id = int(request.POST.get('class_type_id'))
            class_name = request.POST.get('class_name')
            seats = int(request.POST.get('seats'))
            is_cancelled = request.POST.get('is_cancelled') == 'on'

            start_date = datetime.strptime(request.POST.get('start_date'), '%Y-%m-%d').date()
            end_date = datetime.strptime(request.POST.get('end_date'), '%Y-%m-%d').date()
            start_time = datetime.strptime(request.POST.get('start_time'), '%H:%M').time()
            end_time = datetime.strptime(request.POST.get('end_time'), '%H:%M').time()
            
            if seats <= 0:
                messages.error(request, 'Seats must be greater than zero.')
                return redirect('manage_classes')
            
            if start_date > end_date:
                messages.error(request, 'Start date cannot be after end date.')
                return redirect('manage_classes')
            
            if start_time >= end_time:
                messages.error(request, 'Start time must be before end time.')
                return redirect('manage_classes')
            

        except (ValueError, TypeError):
            messages.error(request, 'Invalid input. Please check your data and try again.')
            return redirect('manage_classes')

        pool = get_object_or_404(Pool, pk=pool_id)
        class_type = get_object_or_404(ClassType, pk=class_type_id, is_closed=False)
        trainer = get_object_or_404(User, pk=user_id, role='trainer')
        
        if seats > pool.capacity:
            messages.error(request, f'Seats cannot exceed pool capacity. The pool capacity is {pool.capacity}.')
            return redirect('manage_classes')
        
        today = datetime.now().date()
        upcoming_classes = ClassSession.objects.filter(
            pool=pool,
            is_cancelled=False,
            end_date__gte=today
        )
        
        if class_session:
            upcoming_classes = upcoming_classes.exclude(pk=class_session.id)

        for existing_class in upcoming_classes:
            if start_date <= existing_class.end_date and end_date >= existing_class.start_date:
                if start_time < existing_class.end_time and end_time > existing_class.start_time:
                    messages.error(request, 
                                    f"Class session overlaps with existing class '{existing_class.class_name}' "
                                    f"scheduled from {existing_class.start_date} to {existing_class.end_date} "
                                    f"between {existing_class.start_time} and {existing_class.end_time}. "
                                    "Please choose a different time or date range.")
                    return redirect('manage_classes')

        if class_session:
            class_session.user = trainer
            class_session.pool = pool
            class_session.class_type = class_type
            class_session.class_name = class_name
            class_session.seats = seats
            class_session.start_date = start_date
            class_session.end_date = end_date
            class_session.start_time = start_time
            class_session.end_time = end_time
            class_session.is_cancelled = is_cancelled
            class_session.save()
            
            messages.success(request, 'Class session updated successfully.')
            return redirect('manage_classes')
        else:
            ClassSession.objects.create(
                user=trainer,
                pool=pool,
                class_type=class_type,
                class_name=class_name,
                seats=seats,
                start_date=start_date,
                end_date=end_date,
                start_time=start_time,
                end_time=end_time,
                is_cancelled=is_cancelled
            )
            messages.success(request, 'Class session created successfully.')
            return redirect('manage_classes')
        
    class_sessions = ClassSession.objects.all()
    q = (request.GET.get('q') or '').strip()
    status = request.GET.get('status')
    pool_filter = request.GET.get('pool')
    trainer_filter = request.GET.get('trainer')
    start_filter = request.GET.get('start')
    end_filter = request.GET.get('end')

    if q:
        class_sessions = class_sessions.filter(
            Q(class_name__icontains=q) |
            Q(pool__name__icontains=q) |
            Q(user__full_name__icontains=q) |
            Q(user__username__icontains=q)
        )

    if status == 'open':
        class_sessions = class_sessions.filter(is_cancelled=False)
    elif status == 'cancelled':
        class_sessions = class_sessions.filter(is_cancelled=True)

    if pool_filter:
        class_sessions = class_sessions.filter(pool_id=pool_filter)
    if trainer_filter:
        class_sessions = class_sessions.filter(user_id=trainer_filter)

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

    return render(request, 'dashboards/admin/admin_manage_classes.html', {
        'classes': class_sessions,
        'pools': pools,
        'class_types': class_types,
        'trainers': trainers
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


def manage_private_classes(request):
    # Filter only private class sessions (where duration_days == 0)
    private_classes = ClassSession.objects.filter(class_type__duration_days=0).select_related('pool', 'user', 'class_type').order_by('-start_date')
    
    q = (request.GET.get('q') or '').strip()
    status = request.GET.get('status')
    pool_filter = request.GET.get('pool')
    trainer_filter = request.GET.get('trainer')

    if q:
        private_classes = private_classes.filter(
            Q(class_name__icontains=q) |
            Q(pool__name__icontains=q) |
            Q(user__full_name__icontains=q) |
            Q(user__username__icontains=q)
        )

    if status == 'active':
        private_classes = private_classes.filter(is_cancelled=False)
    elif status == 'cancelled':
        private_classes = private_classes.filter(is_cancelled=True)

    if pool_filter:
        private_classes = private_classes.filter(pool_id=pool_filter)
    if trainer_filter:
        private_classes = private_classes.filter(user_id=trainer_filter)

    pools = Pool.objects.filter(is_closed=False).all()
    trainers = User.objects.filter(role='trainer')

    return render(request, 'dashboards/admin/admin_manage_private_classes.html', {
        'private_classes': private_classes,
        'pools': pools,
        'trainers': trainers
    })

def edit_private_class_price(request, class_id):
    class_session = get_object_or_404(ClassSession, pk=class_id, class_type__duration_days=0)
    
    if request.method == 'POST':
        try:
            new_price = request.POST.get('total_price')
            if not new_price:
                messages.error(request, 'Price is required.')
                return redirect('manage_private_classes')
            
            class_session.total_price = float(new_price)
            class_session.save(update_fields=['total_price'])
            messages.success(request, 'Private class price updated successfully.')
        except (ValueError, TypeError):
            messages.error(request, 'Invalid price value.')
    
    return redirect('manage_private_classes')

@login_required
def book_class(request, class_id):
    class_session = get_object_or_404(ClassSession, pk=class_id)
    if class_session.is_cancelled:
        messages.error(request, 'Cannot book a cancelled class session.')
        return redirect('class_list')
    
    if ClassBooking.objects.filter(user=request.user, class_session=class_session, is_active=True).exists():
        messages.error(request, 'You have already booked this class session.')
    elif class_session.total_bookings >= class_session.seats:
        messages.error(request, 'No seats available for this class session.')
    else:
        ClassBooking.objects.create(user=request.user, class_session=class_session)
        class_session.total_bookings += 1
        class_session.save(update_fields=['total_bookings'])
        messages.success(request, 'Class session booked successfully.')
    return redirect('class_list')

def cancel_booked_class(request, booking_id):
    booking = get_object_or_404(ClassBooking, pk=booking_id, user=request.user, is_active=True)
    
    
    class_session = booking.class_session


    if class_session.end_date < datetime.now().date():
        messages.error(request, 'Cannot cancel booking for a past class session.')
        return redirect('my_bookings')

    if class_session.total_bookings > 0:
        class_session.total_bookings -= 1
        class_session.save(update_fields=['total_bookings'])

    booking.is_active = False
    booking.save(update_fields=['is_active'])
    
    messages.success(request, 'Class session booking cancelled successfully.')
    return redirect('my_bookings')

def manage_private_class_prices(request):
    private_class_details = PrivateClassDetails.objects.order_by('-created_at').first()
    
    context = {
        'private_class_price_per_day': private_class_details.private_class_price_per_day,
        'private_class_details': private_class_details
    }

    return render(request, 'dashboards/admin/admin_manage_private_class_prices.html', context)

def new_private_class_price(request):
    if not request.user.is_authenticated or request.user.role != 'admin':
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('home')
    
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

def book_private_class(request):
    if not request.user.is_authenticated:
        messages.error(request, 'You need to log in to book a private class.')
        return redirect('login')
    
    if request.method == 'POST':
        try:
            trainer_id = int(request.POST.get('trainer_id'))
            pool_id = int(request.POST.get('pool_id'))
            start_date = datetime.strptime(request.POST.get('start_date'), '%Y-%m-%d').date()
            end_date = datetime.strptime(request.POST.get('end_date'), '%Y-%m-%d').date()
            start_time = datetime.strptime(request.POST.get('start_time'), '%H:%M').time()
            end_time = datetime.strptime(request.POST.get('end_time'), '%H:%M').time()

            if start_date > end_date:
                messages.error(request, 'Start date cannot be after end date.')
                return redirect('private_class_register')
            
            if start_time >= end_time:
                messages.error(request, 'Start time must be before end time.')
                return redirect('private_class_register')
            
            if start_time - end_time >= timedelta(hours=4):
                messages.error(request, 'Private class duration cannot exceed 4 hours.')
                return redirect('private_class_register')
            
            if TrainerPoolAssignment.objects.filter(trainer_id=trainer_id, pool_id=pool_id, is_active=True).exists() == False:
                messages.error(request, 'Selected trainer is not assigned to the selected pool. Please choose a different trainer or pool.')
                return redirect('private_class_register')
            
            if TrainerPoolAssignment.objects.filter(trainer_id=trainer_id, pool_id=pool_id, is_active=True).exists():
                overlapping_classes = PrivateClass.objects.filter(
                    trainer_id=trainer_id,
                    pool_id=pool_id,
                    start_date__lte=end_date,
                    end_date__gte=start_date, 
                    start_time__lt=end_time,
                    end_time__gt=start_time,
                    is_cancelled=False
                )
                if overlapping_classes.exists():
                    messages.error(request, 'The selected trainer has another private class during this time. Please choose a different time or trainer.')
                    return redirect('private_class_register')



        except (ValueError, TypeError):
            messages.error(request, 'Invalid input. Please check your data and try again.')
            return redirect('private_class_register')

        trainer = get_object_or_404(User, pk=trainer_id, role='trainer')
        pool = get_object_or_404(Pool, pk=pool_id)

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
            return redirect('private_class_register')
        
        if TrainerPoolAssignment.objects.filter(trainer_id=trainer_id, pool_id=pool_id, is_active=True).exists() == False:
            messages.error(request, 'Selected trainer is not assigned to the selected pool. Please choose a different trainer or pool.')
            return redirect('private_class_register')

        overlapping_private_classes = PrivateClass.objects.filter(
            trainer=trainer,
            pool=pool,
            start_date__lte=end_date,
            end_date__gte=start_date,
            start_time__lt=end_time,
            end_time__gt=start_time,
            is_cancelled=False
        )

        if overlapping_private_classes.exists():
            messages.error(request, 'The selected trainer has another private class during this time. Please choose a different time or trainer.')
            return redirect('private_class_register')
        
        assignment = TrainerPoolAssignment.objects.filter(trainer_id=trainer_id, pool_id=pool_id, is_active=True).first()
        if not assignment or assignment.end_date < end_date:
            end_date_str = assignment.end_date.strftime('%Y-%m-%d') if assignment else 'N/A'
            messages.error(
                request,
                f'Trainer assignment to this pool ends on {end_date_str}, before the private class ends. Please choose a different trainer, pool, or date.'
            )
            return redirect('private_class_register')

        PrivateClass.objects.create(
            user=request.user,
            trainer=trainer,
            pool=pool,
            start_date=start_date,
            end_date=end_date, 
            start_time=start_time,
            end_time=end_time
        )
        messages.success(request, 'Private class booked successfully.')

    return render(request, 'classes/book_private_class.html')

def my_private_classes(request):
    if not request.user.is_authenticated:
        messages.error(request, 'You need to log in to view your private classes.')
        return redirect('login')
    
    private_classes = PrivateClass.objects.filter(user=request.user).select_related('trainer', 'pool').order_by('-created_at')

    return render(request, 'classes/my_private_classes.html', {'private_classes': private_classes})

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