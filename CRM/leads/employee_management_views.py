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
        # Already has select_related('user') which is good
        return Profile.objects.filter(
            ~Q(user=self.request.user),
            user__is_deleted=False
        ).select_related('user').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Optimize: Use single aggregation query instead of multiple count queries
        from django.db.models import Count, Q
        base_queryset = Profile.objects.exclude(user=self.request.user)
        
        counts = base_queryset.aggregate(
            active=Count('id', filter=Q(is_active=True, user__is_deleted=False)),
            inactive=Count('id', filter=Q(is_active=False)),
            total=Count('id', filter=Q(user__is_deleted=False))
        )
        
        context['active_employees'] = counts['active'] or 0
        context['inactive_employees'] = counts['inactive'] or 0
        context['total_employees'] = counts['total'] or 0
        
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
    """Soft delete employee with password confirmation"""
    
    def dispatch(self, request, *args, **kwargs):
        # Check if user is a manager
        if not hasattr(request.user, 'profile') or int(request.user.profile.role) != UserRole.MANAGER.value:
            raise PermissionDenied("Only managers can manage employees")
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, pk):
        try:
            profile = get_object_or_404(Profile, pk=pk)
            
            # Get password from request
            password = request.POST.get('password')
            if not password:
                return JsonResponse({
                    "success": False, 
                    "error": "Password confirmation is required to delete employee"
                }, status=400)
            
            # Verify manager's password
            from django.contrib.auth import authenticate
            user = authenticate(request, email=request.user.email, password=password)
            if not user:
                return JsonResponse({
                    "success": False, 
                    "error": "Invalid password. Please try again."
                }, status=400)
            
            # Don't allow managers to delete themselves
            if profile.user == request.user:
                return JsonResponse({"success": False, "error": "cannot_delete_self"}, status=400)
            
            # Check if employee has any leads assigned - optimize to get count in single query
            lead_count = Lead.objects.filter(assigned_to=profile).count()
            if lead_count > 0:
                return JsonResponse({
                    "success": False, 
                    "error": f"Employee has {lead_count} leads assigned. Please reassign leads before deleting."
                }, status=400)
            
            # Soft delete the user
            user_to_delete = profile.user
            user_to_delete.is_deleted = True
            user_to_delete.is_active = False
            user_to_delete.save(update_fields=['is_deleted', 'is_active'])
            
            # Also deactivate the profile
            profile.is_active = False
            profile.save(update_fields=['is_active'])
            
            return JsonResponse({
                "success": True,
                "message": "Employee deleted successfully"
            })
            
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)}, status=500)
