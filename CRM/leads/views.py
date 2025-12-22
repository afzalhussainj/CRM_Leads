from django.db.models import Q
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.models import Leads, Profile
from .models import Lead
from leads.serializer import (
    LeadCreateSerializer,
    LeadSerializer,
)
from utils.roles_enum import UserRole


class LeadListView(APIView, LimitOffsetPagination):
    model = Lead
    permission_classes = (IsAuthenticated,)

    def get_context_data(self, **kwargs):
        params = self.request.query_params
        request = self.request
        
        # Base queryset with optimizations
        queryset = (
            self.model.objects.select_related(
                'status',
                'assigned_to',
                'assigned_to__user'
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
            # DEV_LEAD can also see all leads
        
        # Apply search filters
        request_post = params
        if request_post:
            if request_post.get("name"):
                queryset = queryset.filter(
                    Q(company_name__icontains=request_post.get("name"))
                    | Q(contact_first_name__icontains=request_post.get("name"))
                    | Q(contact_last_name__icontains=request_post.get("name"))
                )
            if request_post.get("city"):
                queryset = queryset.filter(
                    Q(company_name__icontains=request_post.get("city"))
                )
            if request_post.get("email"):
                queryset = queryset.filter(
                    contact_email__icontains=request_post.get("email")
                )
            if request_post.get("status"):
                queryset = queryset.filter(status=request_post.get("status"))
            if request_post.get("source"):
                queryset = queryset.filter(source=request_post.get("source"))
            if request_post.get("assigned_to"):
                queryset = queryset.filter(assigned_to=request_post.get("assigned_to"))

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
        Managers can assign leads to any employee.
        Employees can only create leads assigned to themselves.
        """
        params = request.data
        data = {}
        for key, value in params.items():
            if key not in ["csrfmiddlewaretoken", "tags", "contacts"]:
                data[key] = value

        # Get user profile and role
        user_profile = request.user.profile
        user_role = int(user_profile.role) if user_profile.role is not None else None
        
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
                # DEV_LEAD can also assign to any employee
                data["assigned_to"] = assigned_to.id
            except Profile.DoesNotExist:
                return Response(
                    {"error": True, "message": "Invalid assigned_to profile ID."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            # If no assignment, employees are auto-assigned to themselves
            if user_role == UserRole.EMPLOYEE.value:
                data["assigned_to"] = user_profile.id

        # Set is_active to True by default for new leads
        if "is_active" not in data:
            data["is_active"] = True

        serializer = LeadCreateSerializer(data=data)
        if serializer.is_valid():
            lead_obj = serializer.save(
                created_by=request.user.profile.user,
            )

            # Handle assignment - optimize with select_related
            if data.get("assigned_to"):
                assigned_to = Profile.objects.select_related('user').get(id=data.get("assigned_to"))
                lead_obj.assigned_to = assigned_to
                lead_obj.save()

            # Return the created lead with full details
            lead_serializer = LeadSerializer(lead_obj)
            return Response(
                {
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
        lead_obj = self.get_object(pk)
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
                assigned_to = Profile.objects.select_related('user').get(id=data.get("assigned_to"))
                lead_obj.assigned_to = assigned_to
                lead_obj.save()

            return Response(
                {"error": False, "message": "Lead Updated Successfully"},
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


class CreateLeadFromSite(APIView):
    permission_classes = ()

    def post(self, request, *args, **kwargs):
        params = request.data
        # Optimize with select_related
        api_setting = Leads.objects.select_related('created_by', 'created_by__user').filter(
            website=request.META.get("HTTP_REFERER")
        ).first()
        if not api_setting:
            return Response(
                {"error": True, "message": "Invalid request"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = {
            "company_name": params.get("company_name"),
            "contact_first_name": params.get("first_name"),
            "contact_last_name": params.get("last_name"),
            "contact_email": params.get("email"),
            "contact_phone": params.get("phone"),
            "title": params.get("title"),
            "description": params.get("description"),
            "source": params.get("source"),
            "status": "new",
        }

        serializer = LeadCreateSerializer(data=data)
        if serializer.is_valid():
            lead_obj = serializer.save(
                created_by=api_setting.created_by.user,
            )
            return Response(
                {"error": False, "message": "Lead Created Successfully"},
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {"error": True, "message": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )