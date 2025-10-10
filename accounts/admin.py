from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('username', 'phone', 'profile_picture')}),
        ('Roles & Status', {'fields': ('role', 'status')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {'classes': ('wide',),
                'fields': ('email', 'username', 'password1', 'password2', 'role', 'status', 'phone')}),
    )
    list_display = ('email', 'username', 'role', 'status', 'is_active')
    search_fields = ('email', 'username', 'role')
    ordering = ('email',)
