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
from leads.tasks import (
    send_email_to_assigned_user,
    send_lead_assigned_emails,
)
from utils.roles_enum import UserRole


class LeadListView(APIView, LimitOffsetPagination):
    model = Lead
    permission_classes = (IsAuthenticated,)

    def get_context_data(self, **kwargs):
        params = self.request.query_params
        queryset = (
            self.model.objects.all()
            .exclude(status="development phase")
            .order_by("-created_at")
        )
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
        context["UserRole"] = UserRole
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

        queryset = queryset.filter(is_active=True)
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

        # Get close leads
        close_leads = self.model.objects.filter(
            status="closed"
        ).order_by("-created_at")
        close_leads = close_leads[:5]
        context["close_leads"] = {
            "leads_count": self.count,
            "close_leads": close_leads,
            "offset": offset,
        }
        
        # Contacts and companies are now embedded in leads
        # Tags functionality removed as part of simplification
        users = Profile.objects.filter(is_active=True).values(
            "id", "user__email"
        )
        context["users"] = users

        return context

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        context["UserRole"] = UserRole
        return Response(context)

    def post(self, request, *args, **kwargs):
        params = request.data
        data = {}
        for key, value in params.items():
            if key not in ["csrfmiddlewaretoken", "tags", "contacts"]:
                data[key] = value

        serializer = LeadCreateSerializer(data=data)
        if serializer.is_valid():
            lead_obj = serializer.save(
                created_by=request.profile.user,
            )

            # Handle assignment
            if data.get("assigned_to"):
                assigned_to = Profile.objects.get(id=data.get("assigned_to"))
                lead_obj.assigned_to = assigned_to
                lead_obj.save()

            return Response(
                {"error": False, "message": "Lead Created Successfully"},
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
        return get_object_or_404(Lead, pk=pk)

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

            # Handle assignment
            if data.get("assigned_to"):
                assigned_to = Profile.objects.get(id=data.get("assigned_to"))
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
        api_setting = Leads.objects.filter(website=request.META.get("HTTP_REFERER")).first()
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