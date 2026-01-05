from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta

from rest_framework import status
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.models import Profile
from .models import Lead
from leads.serializer import (
    LeadCreateSerializer,
    LeadSerializer,
)
from utils.roles_enum import UserRole


class LeadListView(APIView, LimitOffsetPagination):
    """
    API View for listing and creating leads.
    
    GET: Returns all leads with role-based filtering
        - Employees: Only see leads assigned to them
        - Managers: See all leads
    
    POST: Creates a new lead
        - Anyone can create leads
        - Employees can only assign to themselves
        - Managers can assign to any employee
    """
    model = Lead
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        """
        Get queryset with role-based filtering.
        Employees see only assigned leads, Managers see all leads.
        """
        request = self.request
        
        # Base queryset with optimizations
        queryset = (
            self.model.objects.select_related(
                'status',
                'assigned_to',
                'assigned_to__user',
                'created_by'
            )
            .filter(is_active=True, is_project=False)  # Only active leads, exclude projects
            .order_by("-created_at")
        )
        
        # Role-based filtering
        if request.user.is_authenticated and hasattr(request.user, 'profile'):
            user_profile = request.user.profile
            user_role = int(user_profile.role) if user_profile.role is not None else None
            
            # Employees can only see leads assigned to them
            if user_role == UserRole.EMPLOYEE.value:
                queryset = queryset.filter(assigned_to=user_profile)
            # Managers can see all leads (no additional filter needed)
        
        return queryset

    def get_context_data(self, **kwargs):
        params = self.request.query_params
        request = self.request
        
        # Get base queryset with role-based filtering
        queryset = self.get_queryset()
        
        # Apply search filters
        if params:
            if params.get("name"):
                queryset = queryset.filter(
                    Q(company_name__icontains=params.get("name"))
                    | Q(contact_first_name__icontains=params.get("name"))
                    | Q(contact_last_name__icontains=params.get("name"))
                )
            if params.get("city"):
                queryset = queryset.filter(
                    Q(company_name__icontains=params.get("city"))
                )
            if params.get("email"):
                queryset = queryset.filter(
                    contact_email__icontains=params.get("email")
                )
            if params.get("status"):
                queryset = queryset.filter(status=params.get("status"))
            if params.get("source"):
                queryset = queryset.filter(source=params.get("source"))
            if params.get("assigned_to"):
                queryset = queryset.filter(assigned_to=params.get("assigned_to"))

        context = {}
        search = False
        if (
            params.get("name")
            or params.get("city")
            or params.get("email")
            or params.get("status")
            or params.get("source")
            or params.get("assigned_to")
        ):
            search = True
        count = queryset.count()

        if params.get("limit") and params.get("offset"):
            page_size = int(params.get("limit"))
            offset = int(params.get("offset"))
            queryset = queryset[offset:offset + page_size]
        else:
            page_size = 10
            offset = 0
            queryset = queryset[:page_size]

        context["leads"] = LeadSerializer(queryset, many=True).data
        context["count"] = count
        context["offset"] = offset
        context["limit"] = page_size
        context["search"] = search
        
        # Get users list for assignment
        users = Profile.objects.select_related('user').filter(
            is_active=True,
            user__is_deleted=False
        ).values(
            "id", "user__email"
        )
        context["users"] = users

        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        return Response(context)

    def post(self, request, *args, **kwargs):
        """
        Create a new lead.
        - Anyone (authenticated user) can create leads
        - Employees can only assign leads to themselves
        - Managers can assign leads to any employee
        """
        # Validate user has profile
        if not hasattr(request.user, 'profile') or request.user.profile is None:
            return Response(
                {"error": True, "message": "User profile not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        user_profile = request.user.profile
        user_role = int(user_profile.role) if user_profile.role is not None else None
        
        # Prepare data (exclude CSRF token and other non-model fields)
        data = {}
        for key, value in request.data.items():
            if key not in ["csrfmiddlewaretoken", "tags", "contacts"]:
                data[key] = value
        
        # Role-based assignment validation
        if data.get("assigned_to"):
            try:
                assigned_to = Profile.objects.select_related('user').get(id=data.get("assigned_to"))
                
                # Employees can only assign to themselves
                if user_role == UserRole.EMPLOYEE.value:
                    if assigned_to.id != user_profile.id:
                        return Response(
                            {"error": True, "message": "You can only assign leads to yourself."},
                            status=status.HTTP_403_FORBIDDEN,
                        )
                
                # Managers can assign to any employee
                data["assigned_to"] = assigned_to.id
            except Profile.DoesNotExist:
                return Response(
                    {"error": True, "message": "Invalid assigned_to profile ID."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            # If no assignment specified, employees are auto-assigned to themselves
            if user_role == UserRole.EMPLOYEE.value:
                data["assigned_to"] = user_profile.id

        # Set defaults for new leads
        if "is_active" not in data:
            data["is_active"] = True

        # Validate and create lead
        serializer = LeadCreateSerializer(data=data)
        if serializer.is_valid():
            lead_obj = serializer.save(
                created_by=request.user,
            )

            # Handle assignment
            if data.get("assigned_to"):
                assigned_to = Profile.objects.select_related('user').get(id=data.get("assigned_to"))
                lead_obj.assigned_to = assigned_to
                lead_obj.save()

            # Return the created lead with full details
            lead_serializer = LeadSerializer(lead_obj)
            return Response(
                {
                    "success": True,
                    "message": "Lead created successfully",
                    "lead": lead_serializer.data
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {"error": True, "message": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class LeadDetailView(APIView):
    model = Lead
    permission_classes = (IsAuthenticated,)

    def get_object(self, pk):
        # Optimize: Use select_related
        return get_object_or_404(
            Lead.objects.select_related('status', 'assigned_to', 'assigned_to__user'),
            pk=pk
        )

    def get(self, request, pk, **kwargs):
        lead_obj = self.get_object(pk)
        context = {}
        context["UserRole"] = UserRole
        context["lead_obj"] = LeadSerializer(lead_obj).data
        return Response(context)

    def put(self, request, pk, **kwargs):
        """
        Update a lead.
        - Employees can only update leads assigned to them
        - Managers can update any lead
        """
        lead_obj = self.get_object(pk)
        
        # Validate user has profile
        if not hasattr(request.user, 'profile') or request.user.profile is None:
            return Response(
                {"error": True, "message": "User profile not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        user_profile = request.user.profile
        user_role = int(user_profile.role) if user_profile.role is not None else None
        
        # Role-based permission check
        if user_role == UserRole.EMPLOYEE.value:
            # Employees can only update leads assigned to them
            if lead_obj.assigned_to != user_profile:
                return Response(
                    {"error": True, "message": "You can only update leads assigned to you."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        
        params = request.data
        data = {}
        for key, value in params.items():
            if key not in ["csrfmiddlewaretoken", "tags", "contacts"]:
                data[key] = value

        serializer = LeadCreateSerializer(lead_obj, data=data)
        if serializer.is_valid():
            lead_obj = serializer.save()

            # Handle assignment - optimize with select_related
            if data.get("assigned_to"):
                try:
                    assigned_to = Profile.objects.select_related('user').get(id=data.get("assigned_to"))
                    lead_obj.assigned_to = assigned_to
                    lead_obj.save()
                except Profile.DoesNotExist:
                    return Response(
                        {"error": True, "message": "Invalid assigned_to profile ID."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # Return updated lead data
            lead_serializer = LeadSerializer(lead_obj)
            return Response(
                {
                    "error": False,
                    "message": "Lead Updated Successfully",
                    "lead": lead_serializer.data
                },
                status=status.HTTP_200_OK,
            )
        return Response(
            {"error": True, "message": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def delete(self, request, pk, **kwargs):
        lead_obj = self.get_object(pk)
        lead_obj.delete()
        return Response(
            {"error": False, "message": "Lead Deleted Successfully"},
            status=status.HTTP_200_OK,
        )


class LeadFollowUpStatusUpdateView(APIView):
    """
    API View for updating follow-up status of a lead.
    
    PATCH: Updates the follow_up_status field
        - Employees can only update leads assigned to them
        - Managers can update any lead
    
    Accepts: 'pending' or 'done' (case-insensitive)
    """
    permission_classes = (IsAuthenticated,)

    def get_object(self, pk):
        """Get lead object with optimizations"""
        return get_object_or_404(
            Lead.objects.select_related('status', 'assigned_to', 'assigned_to__user'),
            pk=pk
        )

    def patch(self, request, pk, **kwargs):
        """
        Update follow-up status of a lead.
        """
        lead_obj = self.get_object(pk)
        
        # Validate user has profile
        if not hasattr(request.user, 'profile') or request.user.profile is None:
            return Response(
                {"error": True, "message": "User profile not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        user_profile = request.user.profile
        user_role = int(user_profile.role) if user_profile.role is not None else None
        
        # Role-based permission check
        if user_role == UserRole.EMPLOYEE.value:
            # Employees can only update leads assigned to them
            if lead_obj.assigned_to != user_profile:
                return Response(
                    {"error": True, "message": "You can only update follow-up status for leads assigned to you."},
                    status=status.HTTP_403_FORBIDDEN,
                )
        
        # Get follow_up_status from request data
        follow_up_status = request.data.get("follow_up_status")
        
        if follow_up_status is None:
            return Response(
                {"error": True, "message": "follow_up_status is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Validate and normalize follow_up_status (case-insensitive)
        follow_up_status = str(follow_up_status).lower().strip()
        valid_choices = ['pending', 'done']
        
        if follow_up_status not in valid_choices:
            return Response(
                {"error": True, "message": f"follow_up_status must be one of: {', '.join(valid_choices)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Update the follow-up status
        lead_obj.follow_up_status = follow_up_status
        lead_obj.save(update_fields=["follow_up_status"])
        
        # Return updated lead data
        lead_serializer = LeadSerializer(lead_obj)
        return Response(
            {
                "error": False,
                "message": "Follow-up status updated successfully",
                "follow_up_status": follow_up_status,
                "lead": lead_serializer.data
            },
            status=status.HTTP_200_OK,
        )

