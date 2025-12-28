from django.contrib import admin
from .models import User

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'email', 'username', 'role', 'is_active', 'is_staff', 'created_at')
    search_fields = ('email', 'username', 'role')
    list_filter = ('role', 'is_active', 'is_staff')
    ordering = ('user_id',)