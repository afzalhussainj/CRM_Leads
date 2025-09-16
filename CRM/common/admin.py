from django.contrib import admin
from .models import (
    User, Profile, APISettings, LeadSource, LeadStatus
)


@admin.register(LeadSource)
class LeadSourceAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'sort_order', 'created_at']
    list_editable = ['is_active', 'sort_order']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name']
    ordering = ['sort_order']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ['name']
        }),
        ('Settings', {
            'fields': ('is_active', 'sort_order')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).order_by('sort_order')


@admin.register(LeadStatus)
class LeadStatusAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'sort_order', 'created_at']
    list_editable = ['is_active', 'sort_order']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name']
    ordering = ['sort_order']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ['name']
        }),
        ('Settings', {
            'fields': ('is_active', 'sort_order')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).order_by('sort_order')


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['email', 'is_active', 'is_staff']
    list_filter = ['is_active', 'is_staff']
    search_fields = ['email']
    ordering = ['-id']


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'is_active']
    list_filter = ['role', 'is_active']
    search_fields = ['user__email']


@admin.register(APISettings)
class APISettingsAdmin(admin.ModelAdmin):
    list_display = ['title', 'apikey', 'created_by', 'created_at']
    list_filter = ['created_at']
    search_fields = ['title']
    readonly_fields = ['apikey']
