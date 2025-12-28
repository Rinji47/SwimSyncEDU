from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Pool

# Create your views here.
def manage_pools(request, pool_id=None):
    pools = Pool.objects.all()

    if pool_id:
        pool = Pool.objects.get(pk=pool_id)  # for editing the existing pool
    else:
        pool = None  # for new pool creation

    if request.method == 'POST':
        name = request.POST.get('name')
        address = request.POST.get('address')
        capacity = request.POST.get('capacity')
        coordinates = request.POST.get('coordinates')
        image = request.FILES.get('image')

        if pool_id and not pool:
            messages.error(request, 'Pool not found.')
            return redirect('manage_pools')
        
        if pool.name == name and pool.address == address and pool.capacity == capacity and pool.coordinates == coordinates and (not image or pool.image_url == image.name):
            messages.info(request, 'No changes detected.')
            return redirect('manage_pools')
        
        if pool != None:
            if pools.filter(name=name).exclude(pk=pool_id).exists() or pools.filter(address=address).exclude(pk=pool_id).exists():
                messages.error(request, 'A pool with this name or address already exists.')
                return redirect('manage_pools')
            
        if pool == None:
            if pools.filter(name=name).exists() or pools.filter(address=address).exists():
                messages.error(request, 'A pool with this name or address already exists.')
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