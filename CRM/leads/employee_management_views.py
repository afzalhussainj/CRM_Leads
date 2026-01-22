from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.db.models import Count, Q
from common.models import Profile, User
from common.serializer import ProfileSerializer, EmployeeSerializer
from leads.models import Lead
from utils.roles_enum import UserRole



class EmployeeListView(APIView):
    """API View for listing employees - JWT authenticated, managers only"""
    permission_classes = (IsAuthenticated,)
    
    def get(self, request):
        # Check if user is a manager
        if not hasattr(request.user, 'profile') or request.user.profile is None:
            return Response({"success": False, "error": "unauthorized"}, status=status.HTTP_403_FORBIDDEN)
        
        user_role = int(request.user.profile.role) if request.user.profile.role is not None else None
        if user_role != UserRole.MANAGER.value:
            return Response({"success": False, "error": "unauthorized"}, status=status.HTTP_403_FORBIDDEN)
        
        # Employees (role = EMPLOYEE)
        employees = Profile.objects.filter(
            role=UserRole.EMPLOYEE.value,
            user__is_deleted=False
        ).select_related('user').order_by('-created_at')

        # Managers (role = MANAGER), exclude current user to avoid duplication
        managers = Profile.objects.filter(
            role=UserRole.MANAGER.value,
            user__is_deleted=False
        ).select_related('user').order_by('-created_at')
        
        employees_serializer = EmployeeSerializer(employees, many=True)
        managers_serializer = EmployeeSerializer(managers, many=True)
        
        # Counts for employees only
        base_queryset = Profile.objects.filter(role=UserRole.EMPLOYEE.value, user__is_deleted=False)
        counts = base_queryset.aggregate(
            active=Count('id', filter=Q(is_active=True)),
            inactive=Count('id', filter=Q(is_active=False)),
            total=Count('id')
        )
        
        return Response({
            "success": True,
            "employees": employees_serializer.data,
            "managers": managers_serializer.data,
            "counts": {
                "active": counts['active'] or 0,
                "inactive": counts['inactive'] or 0,
                "total": counts['total'] or 0
            }
        }, status=status.HTTP_200_OK)


class EmployeeToggleActiveView(APIView):
    """API View for toggling employee active status - JWT authenticated"""
    permission_classes = (IsAuthenticated,)
    
    def post(self, request, pk):
        # Check if user is a manager
        if not hasattr(request.user, 'profile') or request.user.profile is None:
            return Response({"success": False, "error": "unauthorized"}, status=status.HTTP_403_FORBIDDEN)
        
        user_role = int(request.user.profile.role) if request.user.profile.role is not None else None
        if user_role != UserRole.MANAGER.value:
            return Response({"success": False, "error": "unauthorized"}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            profile = get_object_or_404(Profile, pk=pk)
            
            # Don't allow managers to deactivate themselves
            if profile.user == request.user:
                return Response({"success": False, "error": "cannot_deactivate_self"}, status=status.HTTP_400_BAD_REQUEST)
            
            # Toggle active status
            profile.is_active = not profile.is_active
            profile.save(update_fields=['is_active'])
            
            # Send status change email
            try:
                from common.tasks import send_email_user_status
                send_email_user_status(
                    profile.user.id,
                    status_changed_user=request.user.email
                )
            except Exception:
                # Don't fail the request if email fails
                pass
            
            serializer = EmployeeSerializer(profile)
            return Response({
                "success": True,
                "is_active": profile.is_active,
                "message": f"Employee {'activated' if profile.is_active else 'deactivated'} successfully",
                "employee": serializer.data
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def patch(self, request, pk):
        # Support PATCH method as well
        return self.post(request, pk)


class EmployeeDeleteView(APIView):
    """API View for soft deleting employees - JWT authenticated"""
    permission_classes = (IsAuthenticated,)
    
    def delete(self, request, pk):
        # Check if user is a manager
        if not hasattr(request.user, 'profile') or request.user.profile is None:
            return Response({"success": False, "error": "unauthorized"}, status=status.HTTP_403_FORBIDDEN)
        
        user_role = int(request.user.profile.role) if request.user.profile.role is not None else None
        if user_role != UserRole.MANAGER.value:
            return Response({"success": False, "error": "unauthorized"}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            profile = get_object_or_404(Profile, pk=pk)
            
            # Don't allow managers to delete themselves
            if profile.user == request.user:
                return Response({"success": False, "error": "cannot_delete_self"}, status=status.HTTP_400_BAD_REQUEST)
            
            # Check if employee has any leads assigned
            lead_count = Lead.objects.filter(assigned_to=profile).count()
            if lead_count > 0:
                return Response({
                    "success": False,
                    "error": f"Employee has {lead_count} leads assigned. Please reassign leads before deleting."
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Soft delete the user
            user_to_delete = profile.user
            user_to_delete.is_deleted = True
            user_to_delete.is_active = False
            user_to_delete.save(update_fields=['is_deleted', 'is_active'])
            
            # Also deactivate the profile
            profile.is_active = False
            profile.save(update_fields=['is_active'])
            
            # Send deletion email
            try:
                from common.tasks import send_email_user_delete
                send_email_user_delete(
                    user_email=user_to_delete.email,
                    deleted_by=request.user.email
                )
            except Exception:
                # Don't fail the request if email fails
                pass
            
            return Response({
                "success": True,
                "message": "Employee deleted successfully"
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({"success": False, "error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def post(self, request, pk):
        # Support POST for backward compatibility
        return self.delete(request, pk)
