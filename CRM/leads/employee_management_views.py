from django.views.generic import ListView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q

from common.models import Profile, User
from leads.models import Lead
from utils.roles_enum import UserRole


class EmployeeManagementView(LoginRequiredMixin, ListView):
    """Employee management view - managers only"""
    template_name = "ui/employee_management.html"
    model = Profile
    context_object_name = "employees"
    paginate_by = 20

    def dispatch(self, request, *args, **kwargs):
        # Check if user is a manager
        if not hasattr(request.user, 'profile') or int(request.user.profile.role) != UserRole.MANAGER.value:
            raise PermissionDenied("Only managers can access employee management")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        # Get all profiles except the current user (only non-deleted)
        return Profile.objects.filter(
            ~Q(user=self.request.user),
            user__is_deleted=False
        ).select_related('user').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add counts for different employee statuses
        context['active_employees'] = Profile.objects.filter(
            is_active=True,
            user__is_deleted=False
        ).exclude(user=self.request.user).count()
        
        context['inactive_employees'] = Profile.objects.filter(
            is_active=False
        ).exclude(user=self.request.user).count()
        
        return context


class EmployeeToggleActiveView(LoginRequiredMixin, View):
    """Toggle employee active status"""
    
    def dispatch(self, request, *args, **kwargs):
        # Check if user is a manager
        if not hasattr(request.user, 'profile') or int(request.user.profile.role) != UserRole.MANAGER.value:
            raise PermissionDenied("Only managers can manage employees")
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, pk):
        try:
            profile = get_object_or_404(Profile, pk=pk)
            
            # Don't allow managers to deactivate themselves
            if profile.user == request.user:
                return JsonResponse({"success": False, "error": "cannot_deactivate_self"}, status=400)
            
            # Toggle active status
            profile.is_active = not profile.is_active
            profile.save(update_fields=['is_active'])
            
            return JsonResponse({
                "success": True, 
                "is_active": profile.is_active,
                "message": f"Employee {'activated' if profile.is_active else 'deactivated'} successfully"
            })
            
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=500)


class EmployeeSoftDeleteView(LoginRequiredMixin, View):
    """Soft delete employee"""
    
    def dispatch(self, request, *args, **kwargs):
        # Check if user is a manager
        if not hasattr(request.user, 'profile') or int(request.user.profile.role) != UserRole.MANAGER.value:
            raise PermissionDenied("Only managers can manage employees")
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, pk):
        try:
            profile = get_object_or_404(Profile, pk=pk)
            
            # Don't allow managers to delete themselves
            if profile.user == request.user:
                return JsonResponse({"success": False, "error": "cannot_delete_self"}, status=400)
            
            # Check if employee has any leads assigned
            assigned_leads = Lead.objects.filter(lead_assigned_to=profile).count()
            if assigned_leads > 0:
                return JsonResponse({
                    "success": False, 
                    "error": f"Employee has {assigned_leads} leads assigned. Please reassign leads before deleting."
                }, status=400)
            
            # Soft delete the user
            user = profile.user
            user.is_deleted = True
            user.is_active = False
            user.save(update_fields=['is_deleted', 'is_active'])
            
            # Also deactivate the profile
            profile.is_active = False
            profile.save(update_fields=['is_active'])
            
            return JsonResponse({
                "success": True,
                "message": "Employee deleted successfully"
            })
            
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=500)
