from django.contrib import admin
from .models import (
    User, Profile, Leads, LeadSource, LeadStatus
)


@admin.register(LeadSource)
class LeadSourceAdmin(admin.ModelAdmin):
    list_display = ['source']
    search_fields = ['source']
    ordering = ['source']

    def get_queryset(self, request):
        return super().get_queryset(request).order_by('sort_order')


@admin.register(LeadStatus)
class LeadStatusAdmin(admin.ModelAdmin):
    list_display = ['name', 'sort_order']
    list_editable = ['sort_order']
    search_fields = ['name']
    ordering = ['sort_order']
        
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


@admin.register(Leads)
class Leads(admin.ModelAdmin):
    list_display = ['title', 'status', 'source', 'created_by', 'contact_name', 'linkdein', 'phone', 'company']
    list_filter = ['title']
    search_fields = ['title']
