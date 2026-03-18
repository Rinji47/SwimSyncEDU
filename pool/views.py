from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q
from classes.models import ClassSession, ClassType, PrivateClass
from .models import Pool, PoolImage, PoolQuality, TrainerPoolAssignment
from django.utils import timezone
from accounts.models import User
from datetime import timedelta, datetime, date
from math import radians, sin, cos, sqrt, atan2

try:
    from geopy.distance import geodesic
except ImportError:
    geodesic = None

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


def nearby_pools(request):
    pools = Pool.objects.filter(is_closed=False).prefetch_related('images').all().order_by('name')
    lat = request.GET.get('lat')
    lng = request.GET.get('lng')
    raw_radius = request.GET.get('radius', '10')

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

    def fallback_haversine_km(lat1, lon1, lat2, lon2):
        r = 6371
        d_lat = radians(lat2 - lat1)
        d_lon = radians(lon2 - lon1)
        a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return r * c

    try:
        radius_km = float(raw_radius)
    except (TypeError, ValueError):
        radius_km = 10.0
    radius_km = min(max(radius_km, 1.0), 100.0)

    status_message = f"Enable location to see pools within {radius_km:g} km."
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
                distance = geodesic((user_lat, user_lng), coords).km if geodesic else fallback_haversine_km(
                    user_lat,
                    user_lng,
                    coords[0],
                    coords[1],
                )
                if distance <= radius_km:
                    pool.distance_km = round(distance, 1)
                    nearby.append((distance, pool))

            if nearby:
                nearby.sort(key=lambda item: item[0])
                pools = [item[1] for item in nearby]
                status_message = f"Showing {len(pools)} pool{'s' if len(pools) != 1 else ''} within {radius_km:g} km."
            else:
                status_message = f"No pools within {radius_km:g} km. Showing all pools instead."
        else:
            status_message = "We could not read your location. Showing all pools."
    else:
        status_message = f"Enable location to see pools within {radius_km:g} km. Showing all pools for now."

    context = {
        'pools': pools,
        'status_message': status_message,
        'radius_km': int(radius_km) if radius_km.is_integer() else radius_km,
        'is_geopy_installed': geodesic is not None,
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


def pool_quality_today_list(request):
    pools = Pool.objects.all().order_by('name')
    q = (request.GET.get('q') or '').strip()
    status = request.GET.get('status')
    lat = request.GET.get('lat')
    lng = request.GET.get('lng')
    raw_radius = request.GET.get('radius', '10')
    today = timezone.localdate()

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

    def fallback_haversine_km(lat1, lon1, lat2, lon2):
        r = 6371
        d_lat = radians(lat2 - lat1)
        d_lon = radians(lon2 - lon1)
        a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return r * c

    try:
        radius_km = float(raw_radius)
    except (TypeError, ValueError):
        radius_km = 10.0
    radius_km = min(max(radius_km, 1.0), 100.0)

    if q:
        pools = pools.filter(Q(name__icontains=q) | Q(address__icontains=q))
    if status == 'open':
        pools = pools.filter(is_closed=False)
    elif status == 'closed':
        pools = pools.filter(is_closed=True)

    pools = list(pools)
    status_message = f"Enable location to see pools within {radius_km:g} km. Showing all pools for now."

    if lat and lng:
        try:
            user_lat = float(lat)
            user_lng = float(lng)
        except ValueError:
            user_lat = None
            user_lng = None

        if user_lat is not None and user_lng is not None:
            nearby = []
            for pool in pools:
                coords = parse_coordinates(pool.coordinates)
                if not coords:
                    continue
                distance = geodesic((user_lat, user_lng), coords).km if geodesic else fallback_haversine_km(
                    user_lat,
                    user_lng,
                    coords[0],
                    coords[1],
                )
                if distance <= radius_km:
                    pool.distance_km = round(distance, 1)
                    nearby.append((distance, pool))
            if nearby:
                nearby.sort(key=lambda item: item[0])
                pools = [item[1] for item in nearby]
                status_message = f"Showing {len(pools)} pool{'s' if len(pools) != 1 else ''} within {radius_km:g} km."
            else:
                status_message = f"No pools within {radius_km:g} km. Showing all pools instead."
        else:
            status_message = "We could not read your location. Showing all pools."

    today_qualities = PoolQuality.objects.filter(
        pool__in=pools,
        date=today,
    ).select_related('pool')
    quality_by_pool_id = {quality.pool_id: quality for quality in today_qualities}

    pool_cards = [
        {
            'pool': pool,
            'today_quality': quality_by_pool_id.get(pool.pool_id),
        }
        for pool in pools
    ]

    context = {
        'pool_cards': pool_cards,
        'today': today,
        'radius_km': int(radius_km) if radius_km.is_integer() else radius_km,
        'status_message': status_message,
    }
    return render(request, 'pools/pool_quality_today_list.html', context)


def pool_quality_today_detail(request, pool_id):
    pool = get_object_or_404(Pool, pk=pool_id)
    today = timezone.localdate()
    today_quality = PoolQuality.objects.filter(pool=pool, date=today).order_by('-updated_at').first()

    context = {
        'pool': pool,
        'today': today,
        'today_quality': today_quality,
    }
    return render(request, 'pools/pool_quality_today_detail.html', context)


def manage_pools(request, pool_id=None):
    pools = Pool.objects.prefetch_related('images').all()

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
        pool = get_object_or_404(Pool.objects.prefetch_related('images'), pk=pool_id)
    else:
        pool = None

    if request.method == 'POST':
        name = request.POST.get('name')
        address = request.POST.get('address')
        capacity_raw = request.POST.get('capacity')
        coordinates = request.POST.get('coordinates')
        uploaded_images = request.FILES.getlist('images')
        deleted_image_ids = request.POST.getlist('delete_image_ids')

        try:
            capacity = int(capacity_raw)
            if capacity <= 0:
                raise ValueError
        except (TypeError, ValueError):
            messages.error(request, 'Capacity must be a positive whole number.')
            return redirect('manage_pools')

        if pool_id and not pool:
            messages.error(request, 'Pool not found.')
            return redirect('manage_pools')
        
        if pool:
            has_new_images = bool(uploaded_images)
            has_deleted_images = bool(deleted_image_ids)
            if (
                pool.name == name
                and pool.address == address
                and pool.capacity == capacity
                and pool.coordinates == coordinates
                and not has_new_images
                and not has_deleted_images
            ):
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
            pool.save()

            if deleted_image_ids:
                PoolImage.objects.filter(pool=pool, image_id__in=deleted_image_ids).delete()

            current_max = pool.images.order_by('-sort_order').values_list('sort_order', flat=True).first() or 0
            for index, uploaded in enumerate(uploaded_images, start=1):
                PoolImage.objects.create(
                    pool=pool,
                    image=uploaded,
                    sort_order=current_max + index,
                )
            messages.success(request, 'Pool updated successfully.')
        else:
            created_pool = Pool.objects.create(
                name=name,
                address=address,
                capacity=capacity,
                coordinates=coordinates,
            )
            for index, uploaded in enumerate(uploaded_images, start=1):
                PoolImage.objects.create(
                    pool=created_pool,
                    image=uploaded,
                    sort_order=index,
                )
            messages.success(request, 'New pool added successfully.')
        
        return redirect('manage_pools')
    
    return render(
        request,
        'dashboards/admin/admin_manage_pools.html',
        {
            'pools': pools,
            'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY,
        },
    )

def close_pool(request, pool_id):
    pool = Pool.objects.get(pk=pool_id)
    if pool.is_closed:
        messages.error(request, 'Pool is already closed.')
        return redirect('manage_pools')
    pool.is_closed = True
    pool.save()
    messages.success(request, 'Pool has been closed successfully.')
    return redirect('manage_pools')

def manage_quality_history(request):
    pools = Pool.objects.all()
    pool_filter = request.GET.get('pool')
    rating_filter = request.GET.get('rating')
    q = (request.GET.get('q') or '').strip()
    today = timezone.localdate()

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
        'qualities': qualities,
        'today': today,
    }
    return render(request, 'dashboards/admin/pool_quality/admin_manage_quality_history.html', context)


def select_pool_quality(request):
    today = timezone.localdate()
    pools = Pool.objects.all().order_by('name')
    today_qualities = PoolQuality.objects.filter(date=today).select_related('pool')
    quality_by_pool_id = {quality.pool_id: quality for quality in today_qualities}
    pool_cards = [
        {
            'pool': pool,
            'today_quality': quality_by_pool_id.get(pool.pool_id),
        }
        for pool in pools
    ]

    context = {
        'today': today,
        'pool_cards': pool_cards,
    }
    return render(request, 'dashboards/admin/pool_quality/select_pool_quality.html', context)


def add_quality(request, pool_id=None):
    if pool_id is None:
        pool_id = request.GET.get('pool_id')
    pool = get_object_or_404(Pool, pk=pool_id)
    today = timezone.localdate()

    if request.method == 'POST':
        cleanliness_rating = request.POST.get('cleanliness_rating')
        pH_level = request.POST.get('pH_level') or None
        water_temperature = request.POST.get('water_temperature') or None
        chlorine_level = request.POST.get('chlorine_level') or None

        if PoolQuality.objects.filter(pool=pool, date=today).exists():
            messages.error(request, "Today's quality record for this pool already exists.")
            return redirect('select_pool_quality')

        PoolQuality.objects.create(
            pool=pool,
            date=today,
            cleanliness_rating=cleanliness_rating,
            pH_level=pH_level,
            water_temperature=water_temperature,
            chlorine_level=chlorine_level,
        )
        messages.success(request, "Today's quality record added successfully.")
        return redirect('select_pool_quality')

    context = {
        'pool': pool,
        'today': today,
        'is_edit': False,
        'quality': None,
    }
    return render(request, 'dashboards/admin/pool_quality/pool_quality_form.html', context)


def edit_quality(request, quality_id):
    quality = get_object_or_404(PoolQuality, pk=quality_id)
    today = timezone.localdate()

    if quality.date != today:
        messages.error(request, 'You can only edit quality records for today.')
        return redirect('manage_quality_history')

    if request.method == 'POST':
        quality.cleanliness_rating = request.POST.get('cleanliness_rating')
        quality.pH_level = request.POST.get('pH_level') or None
        quality.water_temperature = request.POST.get('water_temperature') or None
        quality.chlorine_level = request.POST.get('chlorine_level') or None
        quality.save()

        messages.success(request, "Today's quality record updated successfully.")
        return redirect('select_pool_quality')

    context = {
        'pool': quality.pool,
        'today': today,
        'is_edit': True,
        'quality': quality,
    }
    return render(request, 'dashboards/admin/pool_quality/pool_quality_form.html', context)


def delete_quality(request, quality_id):
    quality = get_object_or_404(PoolQuality, pk=quality_id)
    if request.method != 'POST':
        messages.error(request, 'Invalid request.')
        return redirect('manage_quality_history')

    if quality.date != timezone.localdate():
        messages.error(request, 'You can only delete quality records for today.')
        return redirect('manage_quality_history')

    quality.delete()
    messages.success(request, "Today's quality record deleted successfully.")
    return redirect('manage_quality_history')

def assign_trainer_manager(request):
    assigned_trainers = TrainerPoolAssignment.objects.select_related('trainer', 'pool').all().order_by('-start_date')
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

    context = {
        'pool': pool,
        'trainer_cards': trainer_cards,
        'trainers_assigned_id': trainers_assigned_id,
        'busy_from': busy_from,
        'busy_to': busy_to,
    }
    return render(request, 'dashboards/admin/trainer_assignment/list_trainers.html', context)

def assign_trainer(request, pool_id, trainer_id):
    pool = get_object_or_404(Pool, pk=pool_id)
    trainer = get_object_or_404(User, pk=trainer_id, role='trainer')

    if request.method == 'POST':
        start_date = request.POST.get('start_date')
        if not start_date:
            messages.error(request, 'Start date is required.')
            return redirect('assign_trainer', pool_id=pool_id, trainer_id=trainer_id)
        
        trainer_assigned = TrainerPoolAssignment.objects.filter(trainer=trainer, is_active=True)
        overlapping_assignments = trainer_assigned.filter(Q(end_date__isnull=True) | Q(end_date__gte=start_date))
        if overlapping_assignments.exists():
            messages.error(request, 'This trainer is already assigned to another pool during the selected period.')
            return redirect('assign_trainer', pool_id=pool_id, trainer_id=trainer_id)
        start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        TrainerPoolAssignment.objects.create(
            trainer=trainer,
            pool=pool,
            start_date=start_date,
            end_date=None,
            is_active=True
        )
        messages.success(request, 'Trainer assigned successfully.')
        return redirect('assign_trainer_manager')

    busy_from, busy_to = _parse_busy_range(request.GET.get('busy_from'), request.GET.get('busy_to'))
    context = {
        'pool': pool,
        'trainer': trainer,
        'trainer_unavailable_slots': [],
        'trainer_unavailable_total': 0,
        'trainer_unavailable_more': 0,
        'busy_from': busy_from,
        'busy_to': busy_to,
    }
    slots_map, total_map = _build_trainer_unavailability(
        [trainer],
        busy_from=context['busy_from'],
        busy_to=context['busy_to'],
        max_items=6,
    )
    shown_slots = slots_map.get(trainer.pk, [])
    total_slots = total_map.get(trainer.pk, 0)
    context['trainer_unavailable_slots'] = shown_slots
    context['trainer_unavailable_total'] = total_slots
    context['trainer_unavailable_more'] = max(total_slots - len(shown_slots), 0)
    return render(request, 'dashboards/admin/trainer_assignment/assign_trainer.html', context)

def unassign_trainer(request, assignment_id):
    assignment = get_object_or_404(TrainerPoolAssignment, pk=assignment_id)
    assignment.end_date = timezone.now().date()
    assignment.is_active = False
    assignment.save(update_fields=['end_date', 'is_active'])
    messages.success(request, 'Trainer unassigned successfully.')
    return redirect('assign_trainer_manager')
