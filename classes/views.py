from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.db.models import Q
from .models import ClassSession, ClassType
from pool.models import Pool
from accounts.models import User
from datetime import datetime

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
            total_sessions = int(request.POST.get('total_sessions'))
            seats = int(request.POST.get('seats'))
            is_cancelled = request.POST.get('is_cancelled') == 'on'

            start_date = datetime.strptime(request.POST.get('start_date'), '%Y-%m-%d').date()
            end_date = datetime.strptime(request.POST.get('end_date'), '%Y-%m-%d').date()
            start_time = datetime.strptime(request.POST.get('start_time'), '%H:%M').time()
            end_time = datetime.strptime(request.POST.get('end_time'), '%H:%M').time()


            if total_sessions <= 0:
                messages.error(request, 'Total sessions must be greater than zero.')
                return redirect('manage_classes')
            
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
            class_session.total_sessions = total_sessions
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
                total_sessions=total_sessions,
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