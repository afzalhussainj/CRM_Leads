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
from common.models import LeadStatus, LeadSource, LeadStatus, LeadSource
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


class StatusCreateView(LoginRequiredMixin, View):
    """View for creating new lead statuses"""
    
    def dispatch(self, request, *args, **kwargs):
        # Check if user is a manager
        if not hasattr(request.user, 'profile') or int(request.user.profile.role) != UserRole.MANAGER.value:
            return JsonResponse({"success": False, "error": "unauthorized"}, status=403)
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request):
        status_name = request.POST.get('name', '').strip()
        sort_order = request.POST.get('sort_order', 0)
        
        if not status_name:
            return JsonResponse({"success": False, "error": "name_required"}, status=400)
        
        try:
            sort_order = int(sort_order)
        except ValueError:
            sort_order = 0
        
        # Check if status already exists
        if LeadStatus.objects.filter(name=status_name).exists():
            return JsonResponse({"success": False, "error": "status_exists"}, status=400)
        
        status = LeadStatus.objects.create(
            name=status_name,
            sort_order=sort_order
        )
                
        return JsonResponse({
            "success": True,
            "status": {
                "id": status.id,
                "name": status.name,
                "sort_order": status.sort_order
            }
        })




class StatusDeleteView(LoginRequiredMixin, View):
    """View for deleting lead statuses"""
    
    def dispatch(self, request, *args, **kwargs):
        # Check if user is a manager
        if not hasattr(request.user, 'profile') or int(request.user.profile.role) != UserRole.MANAGER.value:
            return JsonResponse({"success": False, "error": "unauthorized"}, status=403)
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, pk):
        try:
            status = LeadStatus.objects.get(pk=pk)
        except LeadStatus.DoesNotExist:
            return JsonResponse({"success": False, "error": "status_not_found"}, status=404)
        
        # Check if status is being used by any leads
        from leads.models import Lead
        if Lead.objects.filter(status=status).exists():
            return JsonResponse({"success": False, "error": "status_in_use"}, status=400)
        
        status.delete()
        return JsonResponse({"success": True})


class SourceCreateView(LoginRequiredMixin, View):
    """View for creating new lead sources"""
    
    def dispatch(self, request, *args, **kwargs):
        # Check if user is a manager
        if not hasattr(request.user, 'profile') or int(request.user.profile.role) != UserRole.MANAGER.value:
            return JsonResponse({"success": False, "error": "unauthorized"}, status=403)
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request):
        source_name = request.POST.get('name', '').strip()
        
        if not source_name:
            return JsonResponse({"success": False, "error": "name_required"}, status=400)
        
        # Check if source already exists
        if LeadSource.objects.filter(source=source_name).exists():
            return JsonResponse({"success": False, "error": "source_exists"}, status=400)
        
        source = LeadSource.objects.create(source=source_name)
                
        return JsonResponse({
            "success": True,
            "source": {
                "id": source.id,
                "source": source.source
            }
        })


class SourceDeleteView(LoginRequiredMixin, View):
    """View for deleting lead sources"""
    
    def dispatch(self, request, *args, **kwargs):
        # Check if user is a manager
        if not hasattr(request.user, 'profile') or int(request.user.profile.role) != UserRole.MANAGER.value:
            return JsonResponse({"success": False, "error": "unauthorized"}, status=403)
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, pk):
        try:
            # No need for select_related on LeadSource (no foreign keys)
            source = LeadSource.objects.get(pk=pk)
        except LeadSource.DoesNotExist:
            return JsonResponse({"success": False, "error": "source_not_found"}, status=404)
        
        # Check if source is being used by any leads
        from leads.models import Lead
        if Lead.objects.filter(source=source.source).exists():
            return JsonResponse({"success": False, "error": "source_in_use"}, status=400)
        
        source.delete()
        return JsonResponse({"success": True})

class LeadStatusListView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        statuses = LeadStatus.objects.all().order_by('sort_order', 'name')
        print("Fetched statuses:", statuses)
        data = [
            {
                'id': s.id,
                'name': s.name,
            }
            for s in statuses
        ]
        return Response({'statuses': data}, status=status.HTTP_200_OK)


class LeadSourceListView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        sources = LeadSource.objects.all().order_by('source')
        data = [
            {
                'id': src.id,
                'name': src.source,
            }
            for src in sources
        ]
        return Response({'sources': data}, status=status.HTTP_200_OK)
