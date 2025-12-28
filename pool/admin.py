from django.contrib import admin
from .models import Pool

# Register your models here.
@admin.register(Pool)
class PoolAdmin(admin.ModelAdmin):
    list_display = ('pool_id', 'name', 'address', 'capacity', 'created_at')
    search_fields = ('name', 'address')
    ordering = ('pool_id',)