from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import Organization, User


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display   = ['name', 'slug', 'plan', 'is_active', 'total_usuarios', 'created_at']
    list_filter    = ['is_active', 'plan']
    search_fields  = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['created_at', 'updated_at']


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display  = ['username', 'email', 'get_full_name', 'organization', 'role', 'is_active']
    list_filter   = ['role', 'is_active', 'organization']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    fieldsets     = BaseUserAdmin.fieldsets + (
        ('SmartSales', {'fields': ('organization', 'role')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('SmartSales', {'fields': ('organization', 'role')}),
    )
