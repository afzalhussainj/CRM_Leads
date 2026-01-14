from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse_lazy
from django.http import JsonResponse
from django.views import View
from rest_framework.views import APIView
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.core.exceptions import PermissionDenied
from rest_framework.response import Response
from common.models import LeadStatus, LeadSource
from utils.roles_enum import UserRole


class CombinedManagementView(LoginRequiredMixin, ListView):
    """Combined view for managing lead statuses and sources - managers only"""
    template_name = "ui/combined_management.html"
    model = LeadStatus  # Required for ListView
    context_object_name = "statuses"
    
    def dispatch(self, request, *args, **kwargs):
        # Check if user is a manager
        if not hasattr(request.user, 'profile') or int(request.user.profile.role) != UserRole.MANAGER.value:
            raise PermissionDenied("Only managers can access management")
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        return LeadStatus.objects.all().order_by('sort_order', 'name')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['sources'] = LeadSource.objects.all().order_by('source')
        return context



class StatusCreateView(APIView):
    """API View for creating new lead statuses - JWT authenticated"""
    permission_classes = (IsAuthenticated,)
    
    def post(self, request):
        # Check if user is a manager
        if not hasattr(request.user, 'profile') or int(request.user.profile.role) != UserRole.MANAGER.value:
            return Response({"success": False, "error": "unauthorized"}, status=status.HTTP_403_FORBIDDEN)
        
        # Support both JSON and form data
        if request.content_type == 'application/json':
            status_name = request.data.get('name', '').strip()
            sort_order = request.data.get('sort_order', 0)
        else:
            status_name = request.POST.get('name', '').strip()
            sort_order = request.POST.get('sort_order', 0)
        
        if not status_name:
            return Response({"success": False, "error": "name_required"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            sort_order = int(sort_order)
        except (ValueError, TypeError):
            sort_order = 0
        
        # Check if status already exists
        if LeadStatus.objects.filter(name=status_name).exists():
            return Response({"success": False, "error": "status_exists"}, status=status.HTTP_400_BAD_REQUEST)
        
        status_obj = LeadStatus.objects.create(
            name=status_name,
            sort_order=sort_order
        )
                
        return Response({
            "success": True,
            "status": {
                "id": status_obj.id,
                "name": status_obj.name,
                "sort_order": status_obj.sort_order
            }
        }, status=status.HTTP_201_CREATED)




class StatusDeleteView(APIView):
    """API View for deleting lead statuses - JWT authenticated"""
    permission_classes = (IsAuthenticated,)
    

    def delete(self, request, pk):
        # Check if user is a manager
        if not hasattr(request.user, 'profile') or int(request.user.profile.role) != UserRole.MANAGER.value:
            return Response({"success": False, "error": "unauthorized"}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            status_obj = LeadStatus.objects.get(pk=pk)
        except LeadStatus.DoesNotExist:
            return Response({"success": False, "error": "status_not_found"}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if status is being used by any leads
        from leads.models import Lead
        if Lead.objects.filter(status=status_obj).exists():
            return Response({"success": False, "error": "status_in_use"}, status=status.HTTP_400_BAD_REQUEST)
        
        status_obj.delete()
        return Response({"success": True}, status=status.HTTP_200_OK)
    
    def post(self, request, pk):
        # Support POST for backward compatibility (curl uses POST)
        return self.delete(request, pk)


class SourceCreateView(APIView):
    """API View for creating new lead sources - JWT authenticated"""
    permission_classes = (IsAuthenticated,)
    
    def post(self, request):
        # Check if user is a manager
        if not hasattr(request.user, 'profile') or int(request.user.profile.role) != UserRole.MANAGER.value:
            return Response({"success": False, "error": "unauthorized"}, status=status.HTTP_403_FORBIDDEN)
        
        # Support both JSON and form data
        if request.content_type == 'application/json':
            source_name = request.data.get('name', '').strip()
        else:
            source_name = request.POST.get('name', '').strip()
        
        if not source_name:
            return Response({"success": False, "error": "name_required"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if source already exists
        if LeadSource.objects.filter(source=source_name).exists():
            return Response({"success": False, "error": "source_exists"}, status=status.HTTP_400_BAD_REQUEST)
        
        source = LeadSource.objects.create(source=source_name)
                
        return Response({
            "success": True,
            "source": {
                "id": source.id,
                "source": source.source
            }
        }, status=status.HTTP_201_CREATED)


class SourceDeleteView(APIView):
    """API View for deleting lead sources - JWT authenticated"""
    permission_classes = (IsAuthenticated,)
    

    def delete(self, request, pk):
        # Check if user is a manager
        if not hasattr(request.user, 'profile') or int(request.user.profile.role) != UserRole.MANAGER.value:
            return Response({"success": False, "error": "unauthorized"}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            # No need for select_related on LeadSource (no foreign keys)
            source = LeadSource.objects.get(pk=pk)
        except LeadSource.DoesNotExist:
            return Response({"success": False, "error": "source_not_found"}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if source is being used by any leads
        from leads.models import Lead
        if Lead.objects.filter(source=source.source).exists():
            return Response({"success": False, "error": "source_in_use"}, status=status.HTTP_400_BAD_REQUEST)
        
        source.delete()
        return Response({"success": True}, status=status.HTTP_200_OK)
    
    def post(self, request, pk):
        # Support POST for backward compatibility (curl uses POST)
        return self.delete(request, pk)

class LeadoptionsListView(APIView):
    permission_classes = (IsAuthenticated,)


    def get(self, request):
        statuses = LeadStatus.objects.all().order_by('sort_order', 'name')
        statuses_data = [
            {
                'id': s.id,
                'name': s.name,
            }
            for s in statuses
        ]

        sources = LeadSource.objects.all().order_by('source')
        sources_data = [
            {
                'id': src.id,
                'name': src.source,
            }
            for src in sources
        ]
        return Response({'statuses': statuses_data, 'sources': sources_data}, status=status.HTTP_200_OK)