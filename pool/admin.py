from django.contrib import admin
from .models import Pool, PoolImage

# Register your models here.
class PoolImageInline(admin.TabularInline):
    model = PoolImage
    extra = 1


@admin.register(Pool)
class PoolAdmin(admin.ModelAdmin):
    list_display = ('pool_id', 'name', 'address', 'capacity', 'created_at')
    search_fields = ('name', 'address')
    ordering = ('pool_id',)
    inlines = [PoolImageInline]
