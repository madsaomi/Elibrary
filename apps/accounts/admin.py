from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from apps.accounts.models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = (
        (None, {'fields': ('login', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'school', 'role', 'subject', 'grade')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('login', 'password1', 'password2', 'role', 'school'),
        }),
    )
    list_display = ('login', 'first_name', 'last_name', 'role', 'school')
    search_fields = ('login', 'first_name', 'last_name')
    list_filter = ('role', 'school')
    ordering = ('login',)
