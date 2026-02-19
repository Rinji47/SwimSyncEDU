from django.shortcuts import render, redirect, get_object_or_404
from math import radians, sin, cos, sqrt, atan2
from django.contrib import messages
from django.db.models import Q
from classes.models import ClassSession, ClassType
from .models import Pool, PoolQuality, TrainerPoolAssignment
from django.utils import timezone
from accounts.models import User
from datetime import timedelta, datetime

# Create your views here.
def nearby_pools(request):
    pools = Pool.objects.all().order_by('name')
    lat = request.GET.get('lat')
    lng = request.GET.get('lng')

    def parse_coordinates(raw):
        if not raw:
            return None
        parts = raw.replace(' ', '').split(',')
        if len(parts) != 2:
            return None
        try:
            return float(parts[0]), float(parts[1])
        except ValueError:
            return None

    def haversine_km(lat1, lon1, lat2, lon2):
        r = 6371
        d_lat = radians(lat2 - lat1)
        d_lon = radians(lon2 - lon1)
        a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return r * c

    status_message = "Enable location to see pools within 10 km."
    nearby = []

    if lat and lng:
        try:
            user_lat = float(lat)
            user_lng = float(lng)
        except ValueError:
            user_lat = None
            user_lng = None

        if user_lat is not None and user_lng is not None:
            for pool in pools:
                coords = parse_coordinates(pool.coordinates)
                if not coords:
                    continue
                distance = haversine_km(user_lat, user_lng, coords[0], coords[1])
                if distance <= 10:
                    nearby.append((distance, pool))

            if nearby:
                nearby.sort(key=lambda item: item[0])
                pools = [item[1] for item in nearby]
                status_message = f"Showing {len(pools)} pool{'s' if len(pools) != 1 else ''} within 10 km."
            else:
                status_message = "No pools within 10 km. Showing all pools instead."
        else:
            status_message = "We could not read your location. Showing all pools."
    else:
        status_message = "Enable location to see pools within 10 km. Showing all pools for now."

    context = {
        'pools': pools,
        'status_message': status_message,
    }
    return render(request, 'pools/nearby_pools.html', context)

def pool_class_types(request, pool_id):
    pool = get_object_or_404(Pool, pk=pool_id)

    class_types = []
    for types in ClassSession.objects.filter(pool=pool, 
                                             is_cancelled=False, 
                                             start_date__gte=timezone.now().date()
                                             ).values('class_type').distinct():
        for type in ClassType.objects.filter(pk=types['class_type'], is_closed=False):
            class_types.append(type)

    context = {
        'pool': pool,
        'class_types': class_types,
    }
    return render(request, 'pools/pool_classtypes.html', context)

def pool_classes(request, class_type_id, pool_id):
    pool = get_object_or_404(Pool, pk=pool_id)
    class_type = get_object_or_404(ClassType, pk=class_type_id)

    classes = ClassSession.objects.filter(pool=pool, 
                                          class_type=class_type,
                                          is_cancelled=False, 
                                          start_date__gte=timezone.now().date()
                                          ).order_by('start_date', 'start_time')

    context = {
        'pool': pool,
        'class_type': class_type,
        'classes': classes,
    }
    return render(request, 'pools/pool_classes.html', context)


def manage_pools(request, pool_id=None):
    pools = Pool.objects.all()

    q = (request.GET.get('q') or '').strip()
    status = request.GET.get('status')
    capacity_min = request.GET.get('capacity_min')
    capacity_max = request.GET.get('capacity_max')

    if q:
        pools = pools.filter(Q(name__icontains=q) | Q(address__icontains=q))

    if status == 'open':
        pools = pools.filter(is_closed=False)
    elif status == 'closed':
        pools = pools.filter(is_closed=True)

    if capacity_min:
        try:
            pools = pools.filter(capacity__gte=int(capacity_min))
        except ValueError:
            pass
    if capacity_max:
        try:
            pools = pools.filter(capacity__lte=int(capacity_max))
        except ValueError:
            pass

    if pool_id:
        pool = Pool.objects.get(pk=pool_id)
    else:
        pool = None

    if request.method == 'POST':
        name = request.POST.get('name')
        address = request.POST.get('address')
        capacity = int(request.POST.get('capacity'))
        coordinates = request.POST.get('coordinates')
        image = request.FILES.get('image')

        if pool_id and not pool:
            messages.error(request, 'Pool not found.')
            return redirect('manage_pools')
        
        if pool: 
            if pool.name == name and pool.address == address and pool.capacity == capacity and pool.coordinates == coordinates and (not image or pool.image_url == image.name):
                messages.info(request, 'No changes detected.')
                return redirect('manage_pools')
        
        if pool is not None:
            if (pools.filter(name=name).exclude(pk=pool_id).exists() or
                pools.filter(address=address).exclude(pk=pool_id).exists() or
                pools.filter(coordinates=coordinates).exclude(pk=pool_id).exists()):
                messages.error(request, 'A pool with this name, address, or coordinates already exists.')
                return redirect('manage_pools')
        else:
            if (pools.filter(name=name).exists() or
                pools.filter(address=address).exists() or
                pools.filter(coordinates=coordinates).exists()):
                messages.error(request, 'A pool with this name, address, or coordinates already exists.')
                return redirect('manage_pools')
        
        if coordinates == "" or coordinates is None:
            messages.error(request, 'Please select a coordinate')
            return redirect('manage_pools')
        
        if pool:
            pool.name = name
            pool.address = address
            pool.capacity = capacity
            pool.coordinates = coordinates
            if image:
                pool.image_url = image
            pool.save()
            messages.success(request, 'Pool updated successfully.')
        else:
            Pool.objects.create(
                name=name,
                address=address,
                capacity=capacity,
                coordinates=coordinates,
                image_url = image if image else None
            )
            messages.success(request, 'New pool added successfully.')
        
        return redirect('manage_pools')
    
    return render(request, 'dashboards/admin/admin_manage_pools.html', {'pools': pools})

def close_pool(request, pool_id):
    pool = Pool.objects.get(pk=pool_id)
    if pool.is_closed:
        messages.error(request, 'Pool is already closed.')
        return redirect('manage_pools')
    pool.is_closed = True
    pool.save()
    messages.success(request, 'Pool has been closed successfully.')
    return redirect('manage_pools')

def manage_quality(request):
    pools = Pool.objects.all()
    pool_filter = request.GET.get('pool')
    rating_filter = request.GET.get('rating')
    q = (request.GET.get('q') or '').strip()

    qualities = PoolQuality.objects.all()

    if q:
        qualities = qualities.filter(pool__name__icontains=q)
    if pool_filter:
        qualities = qualities.filter(pool_id=pool_filter)
    if rating_filter:
        qualities = qualities.filter(cleanliness_rating=rating_filter)

    qualities = qualities.order_by('-date')

    context = {
        'pools': pools,
        'qualities': qualities
    }
    return render(request, 'dashboards/admin/admin_manage_quality.html', context)

def add_quality(request):
    if request.method == 'POST':
        pool_id = request.POST.get('pool_id')
        date = request.POST.get('date')
        cleanliness_rating = request.POST.get('cleanliness_rating')
        pH_level = request.POST.get('pH_level') or None
        water_temperature = request.POST.get('water_temperature') or None
        chlorine_level = request.POST.get('chlorine_level') or None

        # Check for existing record for the same pool & date
        if PoolQuality.objects.filter(pool_id=pool_id, date=date).exists():
            messages.error(request, 'A quality record for this pool on this date already exists.')
            return redirect('manage_quality')
        
        PoolQuality.objects.create(
            pool_id=pool_id,
            date=date,
            cleanliness_rating=cleanliness_rating,
            pH_level=pH_level,
            water_temperature=water_temperature,
            chlorine_level=chlorine_level
        )
        messages.success(request, 'Quality record added successfully.')
        return redirect('manage_quality')

    messages.error(request, 'Invalid request.')
    return redirect('manage_quality')

def edit_quality(request, quality_id):
    quality = get_object_or_404(PoolQuality, pk=quality_id)

    if request.method == 'POST':
        pool_id = request.POST.get('pool_id')
        date = request.POST.get('date')
        cleanliness_rating = request.POST.get('cleanliness_rating')
        pH_level = request.POST.get('pH_level') or None
        water_temperature = request.POST.get('water_temperature') or None
        chlorine_level = request.POST.get('chlorine_level') or None

        if PoolQuality.objects.filter(pool_id=pool_id, date=date).exclude(pk=quality_id).exists():
            messages.error(request, 'A quality record for this pool on this date already exists.')
            return redirect('manage_quality')

        quality.pool_id = pool_id
        quality.date = date
        quality.cleanliness_rating = cleanliness_rating
        quality.pH_level = pH_level
        quality.water_temperature = water_temperature
        quality.chlorine_level = chlorine_level
        quality.save()

        messages.success(request, 'Quality record updated successfully.')
        return redirect('manage_quality')

    messages.error(request, 'Invalid request.')
    return redirect('manage_quality')

def delete_quality(request, quality_id):
    quality = get_object_or_404(PoolQuality, pk=quality_id)
    quality.delete()
    messages.success(request, 'Quality record deleted successfully.')
    return redirect('manage_quality')

def assign_trainer_manager(request):
    assigned_trainers = TrainerPoolAssignment.objects.select_related('trainer', 'pool').all()
    pools = Pool.objects.all()
    pool_filter = request.GET.get('pool')
    trainer_filter = (request.GET.get('trainer') or '').strip()
    date_filter = request.GET.get('date')

    if pool_filter:
        assigned_trainers = assigned_trainers.filter(pool_id=pool_filter)
    if trainer_filter:
        assigned_trainers = assigned_trainers.filter(
            Q(trainer__full_name__icontains=trainer_filter) |
            Q(trainer__email__icontains=trainer_filter)
        )
    if date_filter:
        assigned_trainers = assigned_trainers.filter(start_date__lte=date_filter).filter(Q(end_date__gte=date_filter) | Q(end_date__isnull=True))

    context = {
        'assigned_trainers': assigned_trainers,
        'pools': pools
    }
    return render(request, 'dashboards/admin/trainer_assignment/assign_trainer_manager.html', context)

def list_pools(request):
    pools = Pool.objects.all().order_by('name')
    q = (request.GET.get('q') or '').strip()
    status = request.GET.get('status')
    if q:
        pools = pools.filter(Q(name__icontains=q) | Q(address__icontains=q))
    if status == 'open':
        pools = pools.filter(is_closed=False)
    elif status == 'closed':
        pools = pools.filter(is_closed=True)
    context = {
        'pools': pools
    }
    return render(request, 'dashboards/admin/trainer_assignment/list_pools.html', context)

def list_trainers(request, pool_id):
    pool = get_object_or_404(Pool, pk=pool_id)
    trainers = User.objects.filter(role='trainer')
    q = (request.GET.get('q') or '').strip()
    assignment = request.GET.get('assignment')
    trainers_assigned_id = TrainerPoolAssignment.objects.filter(is_active=True).values_list('trainer_id', flat=True).distinct()

    if q:
        trainers = trainers.filter(Q(full_name__icontains=q) | Q(email__icontains=q))
    if assignment == 'assigned':
        trainers = trainers.filter(user_id__in=trainers_assigned_id)
    elif assignment == 'not_assigned':
        trainers = trainers.exclude(user_id__in=trainers_assigned_id)

    context = {
        'pool': pool,
        'trainers': trainers,
        'trainers_assigned_id': trainers_assigned_id
    }
    return render(request, 'dashboards/admin/trainer_assignment/list_trainers.html', context)

def assign_trainer(request, pool_id, trainer_id):
    pool = get_object_or_404(Pool, pk=pool_id)
    trainer = get_object_or_404(User, pk=trainer_id, role='trainer')

    if request.method == 'POST':
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date') or None

        if not start_date:
            messages.error(request, 'Start date is required.')
            return redirect('assign_trainer', pool_id=pool_id, trainer_id=trainer_id)
        
        trainer_assigned = TrainerPoolAssignment.objects.filter(trainer=trainer)
    
        if end_date:
            overlapping_assignments = trainer_assigned.filter(
                is_active=True
            ).filter(
                Q(end_date__isnull=True) | Q(start_date__lte=end_date, end_date__gte=start_date)
            )
        else:
            overlapping_assignments = trainer_assigned.filter(
                is_active=True
            ).filter(
                Q(end_date__isnull=True) | Q(end_date__gte=start_date)
            )

        if overlapping_assignments.exists():
            messages.error(request, 'This trainer is already assigned to another pool during the selected period.')
            return redirect('assign_trainer', pool_id=pool_id, trainer_id=trainer_id)

        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        if end_date:
            end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
            
        TrainerPoolAssignment.objects.create(
            trainer=trainer,
            pool=pool,
            start_date=start_date,
            end_date=end_date,
            is_active=True
        )
        messages.success(request, 'Trainer assigned successfully.')
        return redirect('assign_trainer_manager')

    context = {
        'pool': pool,
        'trainer': trainer
    }
    return render(request, 'dashboards/admin/trainer_assignment/assign_trainer.html', context)

def unassign_trainer(request, assignment_id):
    assignment = get_object_or_404(TrainerPoolAssignment, pk=assignment_id)
    assignment.end_date = timezone.now().date()
    assignment.is_active = False
    assignment.save(update_fields=['end_date', 'is_active'])
    messages.success(request, 'Trainer unassigned successfully.')
    return redirect('assign_trainer_manager')