from django.contrib import admin
from .models import ClassSession, ClassType

# Register your models here.
@admin.register(ClassType)
class ClassTypeAdmin(admin.ModelAdmin):
    list_display = ('class_type_id', 'name', 'cost', 'created_at')
    search_fields = ('name',)
    ordering = ('class_type_id',)

@admin.register(ClassSession)
class ClassSessionAdmin(admin.ModelAdmin):
    list_display = ('class_name', 'user', 'pool', 'class_type', 'start_date', 'end_date', 'seats', 'created_at')
    search_fields = ('class_name', 'user__username', 'pool__name', 'class_type__name')
    list_filter = ('start_date', 'end_date', 'pool')
    ordering = ('-created_at',)
