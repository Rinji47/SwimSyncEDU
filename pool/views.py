from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .models import Pool, PoolQuality

# Create your views here.
def manage_pools(request, pool_id=None):
    pools = Pool.objects.all()

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

    if pool_filter:
        qualities = PoolQuality.objects.filter(pool_id=pool_filter).order_by('-date')
    else:
        qualities = PoolQuality.objects.all().order_by('-date')

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
