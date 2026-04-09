from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q
from django.contrib.auth.decorators import login_required
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

def nearby_pools(request):
    pools = Pool.objects.filter(is_closed=False).all().order_by('name')
    lat = request.GET.get('lat')
    lng = request.GET.get('lng')
    raw_radius = request.GET.get('radius', '10')

    q = (request.GET.get('q') or '').strip()

    if q:
        pools = pools.filter(
            Q(name__icontains=q) |
            Q(address__icontains=q)
        )

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
    radius_km = max(radius_km, 1.00)

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
    class_types_from_pool = ClassSession.objects.filter(pool=pool, 
                    is_cancelled=False, 
                    start_date__gte=timezone.now().date()).values('class_type').distinct()
    q = (request.GET.get('q') or '').strip()

    class_types = []
    for types in class_types_from_pool:
        for type in ClassType.objects.filter(pk=types['class_type'], is_closed=False):
            if q and q.lower() not in type.name.lower() and q.lower() not in type.description.lower():
                continue
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
    
    q = (request.GET.get('q') or '').strip()
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    total_price_min = request.GET.get('total_price_min')
    total_price_max = request.GET.get('total_price_max')
    total_bookings_min = request.GET.get('total_bookings_min')
    total_bookings_max = request.GET.get('total_bookings_max')
    seats_min = request.GET.get('seats_min')
    seats_max = request.GET.get('seats_max')
    start_time_from = request.GET.get('start_time_from')
    start_time_to = request.GET.get('start_time_to')
    
    if q:
        classes = classes.filter(
            Q(class_name__icontains=q) |
            Q(trainer__full_name__icontains=q) |
            Q(trainer__username__icontains=q)
        )
    if date_from:
        try:
            date_from_parsed = datetime.strptime(date_from, '%Y-%m-%d').date()
            classes = classes.filter(end_date__gte=date_from_parsed)
        except ValueError:
            pass
    if date_to:
        try:
            date_to_parsed = datetime.strptime(date_to, '%Y-%m-%d').date()
            classes = classes.filter(start_date__lte=date_to_parsed)
        except ValueError:
            pass
    if total_price_min:
        try:
            classes = classes.filter(total_price__gte=float(total_price_min))
        except ValueError:
            pass
    if total_price_max:
        try:
            classes = classes.filter(total_price__lte=float(total_price_max))
        except ValueError:
            pass
    if total_bookings_min:
        try:
            classes = classes.filter(total_bookings__gte=int(total_bookings_min))
        except ValueError:
            pass
    if total_bookings_max:
        try:
            classes = classes.filter(total_bookings__lte=int(total_bookings_max))
        except ValueError:
            pass
    if seats_min:
        try:
            classes = classes.filter(seats__gte=int(seats_min))
        except ValueError:
            pass
    if seats_max:
        try:
            classes = classes.filter(seats__lte=int(seats_max))
        except ValueError:
            pass

    if start_time_from:
        try:
            start_time_from_parsed = datetime.strptime(start_time_from, '%H:%M').time()
            classes = classes.filter(start_time__gte=start_time_from_parsed)
        except ValueError:
            pass
    if start_time_to:
        try:
            start_time_to_parsed = datetime.strptime(start_time_to, '%H:%M').time()
            classes = classes.filter(start_time__lte=start_time_to_parsed)
        except ValueError:
            pass

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
    radius_km = max(radius_km, 1.0)

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


@login_required
def add_pool(request):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    if request.method == 'POST':
        pools = Pool.objects.all()
        name = request.POST.get('name')
        address = request.POST.get('address')
        capacity_raw = request.POST.get('capacity')
        coordinates = request.POST.get('coordinates')
        uploaded_images = request.FILES.getlist('images')
        MAX_IMAGES = 5

        if len(uploaded_images) > MAX_IMAGES:
            messages.error(request, f'You can only have up to {MAX_IMAGES} images per pool.')
            return render(request, 'dashboards/admin/pool_management/add_pool.html', {
                'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY,
                'form_data': request.POST,
            })

        try:
            capacity = int(capacity_raw)
            if capacity <= 0:
                raise ValueError
        except (TypeError, ValueError):
            messages.error(request, 'Capacity must be a positive whole number.')
            return render(request, 'dashboards/admin/pool_management/add_pool.html', {
                'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY,
                'form_data': request.POST,
            })

        if pools.filter(name=name).exists() or pools.filter(coordinates=coordinates).exists():
            messages.error(request, 'A pool with this name, or coordinates already exists.')
            return render(request, 'dashboards/admin/pool_management/add_pool.html', {
                'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY,
                'form_data': request.POST,
            })

        if coordinates == "" or coordinates is None:
            messages.error(request, 'Please select a coordinate')
            return render(request, 'dashboards/admin/pool_management/add_pool.html', {
                'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY,
                'form_data': request.POST,
            })

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

    return render(request, 'dashboards/admin/pool_management/add_pool.html', {
        'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY,
    })

@login_required
def edit_pool(request, pool_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    pool = get_object_or_404(Pool, pk=pool_id)
    if request.method == 'POST':
        pool_name = request.POST.get('name')
        pool_address = request.POST.get('address')
        capacity_raw = request.POST.get('capacity')
        coordinates = request.POST.get('coordinates')
        uploaded_images = request.FILES.getlist('images')
        deleted_image_ids = request.POST.getlist('delete_image_ids')
        MAX_IMAGES = 5
        existing_image_count = pool.images.count()
        deleted_count = len(deleted_image_ids)
        final_count = existing_image_count - deleted_count + len(uploaded_images)
        if final_count > MAX_IMAGES:
            messages.error(request, f'You can only have up to {MAX_IMAGES} images per pool. Please delete some images before uploading new ones.')
            return redirect('edit_pool', pool_id=pool_id)
        try:
            capacity = int(capacity_raw)
            if capacity <= 0:
                raise ValueError
        except (TypeError, ValueError):
            messages.error(request, 'Capacity must be a positive whole number.')
            return redirect('edit_pool', pool_id=pool_id)
        pools = Pool.objects.exclude(pk=pool_id)
        if pools.filter(name=pool_name).exists() or pools.filter(coordinates=coordinates).exists():
            messages.error(request, 'A pool with this name, or coordinates already exists.')
            return redirect('edit_pool', pool_id=pool_id)
        if coordinates == "" or coordinates is None:
            messages.error(request, 'Please select a coordinate')
            return redirect('edit_pool', pool_id=pool_id)
        
        pool.name = pool_name
        pool.address = pool_address
        pool.capacity = capacity
        pool.coordinates = coordinates
        pool.save()

        if deleted_image_ids:
            images_to_delete = PoolImage.objects.filter(pool=pool, image_id__in=deleted_image_ids)

            for image in images_to_delete:
                image.image.delete(save=False)
            images_to_delete.delete()

        current_max = pool.images.order_by('-sort_order').values_list('sort_order', flat=True).first() or 0

        for index, uploaded in enumerate(uploaded_images, start=1):
            PoolImage.objects.create(
                pool=pool,
                image=uploaded,
                sort_order=current_max + index,
            )

        messages.success(request, 'Pool updated successfully.')
        return redirect('manage_pools')

    return render(request, 'dashboards/admin/pool_management/edit_pool.html', {
        'pool': pool,
        'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY,
    })


@login_required
def view_pool(request, pool_id):
    if request.user.role != 'admin':
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('index')

    pool = get_object_or_404(Pool, pk=pool_id)
    return render(request, 'dashboards/admin/pool_management/view_pool.html', {
        'pool': pool,
    })


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
        pool = get_object_or_404(Pool, pk=pool_id)
    else:
        pool = None

    if request.method == 'POST':
        name = request.POST.get('name')
        address = request.POST.get('address')
        capacity_raw = request.POST.get('capacity')
        coordinates = request.POST.get('coordinates')
        uploaded_images = request.FILES.getlist('images')
        deleted_image_ids = request.POST.getlist('delete_image_ids')

        MAX_IMAGES = 5
        existing_image_count = 0;
        if pool:
            existing_image_count = pool.images.count()
        
        deleted_count = len(deleted_image_ids)
        if pool:
            deleted_count = len(deleted_image_ids)
        
        final_count = existing_image_count - deleted_count + len(uploaded_images)
        if final_count > MAX_IMAGES:
            messages.error(request, f'You can only have up to {MAX_IMAGES} images per pool. Please delete some images before uploading new ones.')
            return redirect('manage_pools')
        
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
                pools.filter(coordinates=coordinates).exclude(pk=pool_id).exists()):
                messages.error(request, 'A pool with this name, or coordinates already exists.')
                return redirect('manage_pools')
        else:
            if (pools.filter(name=name).exists() or
                pools.filter(coordinates=coordinates).exists()):
                messages.error(request, 'A pool with this name, or coordinates already exists.')
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
                images_to_delete = PoolImage.objects.filter(pool=pool, image_id__in=deleted_image_ids)

                for image in images_to_delete:
                    image.image.delete(save=False)
                
                images_to_delete.delete()

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
        'dashboards/admin/pool_management/admin_manage_pools.html',
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
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    q = (request.GET.get('q') or '').strip()
    today = timezone.localdate()

    qualities = PoolQuality.objects.all()
    if q:
        qualities = qualities.filter(pool__name__icontains=q)
    if pool_filter:
        qualities = qualities.filter(pool_id=pool_filter)
    if rating_filter:
        qualities = qualities.filter(cleanliness_rating=rating_filter)
    if date_from:
        qualities = qualities.filter(date__gte=date_from)
    if date_to:
        qualities = qualities.filter(date__lte=date_to)

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

    q = (request.GET.get('pool_name_or_address') or '').strip()
    not_rated_pools = request.GET.get('not_rated_pools')

    if not_rated_pools:
        not_rated_pools_id = PoolQuality.objects.filter(date=today).values_list('pool_id', flat=True)
        pools = pools.exclude(pool_id__in=not_rated_pools_id)
    
    if q:
        pools = pools.filter(Q(name__icontains=q) | Q(address__icontains=q))

    today_qualities = PoolQuality.objects.filter(date=today).select_related('pool')

    quality_by_pool_id = {}
    for quality in today_qualities:
        quality_by_pool_id[quality.pool_id] = quality

    pool_cards = []
    for pool in pools:
        pool_cards.append({
            'pool': pool,
            'today_quality': quality_by_pool_id.get(pool.pool_id),
        })

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
    trainer_and_pool_filter = (request.GET.get('trainer_and_pools') or '').strip()
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    if pool_filter:
        assigned_trainers = assigned_trainers.filter(pool_id=pool_filter)
    if trainer_and_pool_filter:
        assigned_trainers = assigned_trainers.filter(
            Q(trainer__full_name__icontains=trainer_and_pool_filter) |
            Q(trainer__email__icontains=trainer_and_pool_filter) |
            Q(pool__name__icontains=trainer_and_pool_filter)
        )
    if date_from:
        assigned_trainers = assigned_trainers.filter(
            Q(end_date__gte=date_from) | Q(end_date__isnull=True)
        )
    if date_to:
        assigned_trainers = assigned_trainers.filter(start_date__lte=date_to)

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
        'trainers_assigned_id': trainers_assigned_id,
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

    context = {
        'pool': pool,
        'trainer': trainer,
    }
    return render(request, 'dashboards/admin/trainer_assignment/assign_trainer.html', context)

def unassign_trainer(request, assignment_id):
    assignment = get_object_or_404(TrainerPoolAssignment, pk=assignment_id)
    today = timezone.now().date()

    ongoing_or_upcoming_group_classes = ClassSession.objects.filter(
        trainer=assignment.trainer,
        pool=assignment.pool,
        is_cancelled=False,
        end_date__gte=today,
    )

    ongoing_or_upcoming_private_classes = PrivateClass.objects.filter(
        trainer=assignment.trainer,
        pool=assignment.pool,
        is_cancelled=False,
        end_date__gte=today,
    )

    if ongoing_or_upcoming_group_classes.exists() or ongoing_or_upcoming_private_classes.exists():
        messages.error(
            request,
            'This trainer still has ongoing or upcoming classes in this pool. Unassign them after those classes are finished or cancelled.'
        )
        return redirect('assign_trainer_manager')

    assignment.end_date = timezone.now().date()
    assignment.is_active = False
    assignment.save(update_fields=['end_date', 'is_active'])
    messages.success(request, 'Trainer unassigned successfully.')
    return redirect('assign_trainer_manager')