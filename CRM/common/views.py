import json
from multiprocessing import context
import secrets

import requests
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.hashers import make_password
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.utils import json
from django.conf import settings
from django.contrib.auth import authenticate, login
from django.contrib.auth.hashers import make_password
from django.db.models import Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin

#from common.external_auth import CustomDualAuthentication
from rest_framework import status
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

"""API views retained only for users/documents/settings; accounts/contacts removed."""

##from common.custom_auth import JSONWebTokenAuthentication
from common.models import Leads, Profile, User
from utils.roles_enum import UserRole
from common.serializer import *
from common.tasks import (
    send_email_user_delete,
)

from leads.models import Lead
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views import View
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from .models import Profile

User = get_user_model()

@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """Login view that returns JWT tokens"""
    email = request.data.get('email')
    password = request.data.get('password')
    
    if not email or not password:
        return Response({
            'error': 'Email and password are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    user = authenticate(request, email=email, password=password)
    
    if user is not None:
        try:
            profile = Profile.objects.get(user=user, is_active=True)
            login(request, user)
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'access_token': str(refresh.access_token),
                'refresh_token': str(refresh),
                'user': {
                    'email': user.email,
                    'role': profile.role
                }
            })
        except Profile.DoesNotExist:
            return Response({
                'error': 'User profile not found or inactive'
            }, status=status.HTTP_401_UNAUTHORIZED)
    else:
        return Response({
            'error': 'Invalid credentials'
        }, status=status.HTTP_401_UNAUTHORIZED)

@api_view(['POST'])
def logout_view(request):
    """Logout view"""
    logout(request)
    return Response({'message': 'Logged out successfully'})

class LoginUIView(View):
    """UI Login view"""
    template_name = 'ui/login.html'
    
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('/ui/leads/')
        return render(request, self.template_name)
    
    def post(self, request):
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        if not email or not password:
            messages.error(request, 'Email and password are required')
            return render(request, self.template_name)
        
        user = authenticate(request, email=email, password=password)
        
        if user is not None:
            try:
                profile = Profile.objects.get(user=user, is_active=True)
                login(request, user)
                request.user.profile = profile  # Set profile for middleware compatibility
                messages.success(request, f'Welcome back, {user.first_name or user.email}!')
                return redirect('/')
            except Profile.DoesNotExist:
                messages.error(request, 'User profile not found or inactive')
        else:
            messages.error(request, 'Invalid credentials')
        
        return render(request, self.template_name)

@login_required
def logout_ui_view(request):
    """UI Logout view"""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('/login/')


class AddEmployeeView(View):
    """View for managers to add new employees"""
    template_name = 'ui/add_employee.html'
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/login/')
        
        if not hasattr(request.user, 'profile') or request.user.profile is None:
            messages.error(request, "User profile not found. Please contact administrator.")
            return redirect('/login/')
        
        # Only managers can add employees
        if int(request.user.profile.role) != int(UserRole.MANAGER.value):
            raise PermissionError("Only managers can add employees.")
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request):
        return render(request, self.template_name)
    
    def post(self, request):
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        password = request.POST.get('password')
        
        if not all([email, first_name, last_name, password]):
            messages.error(request, 'All fields are required.')
            return render(request, self.template_name)
        
        try:
            # Check if user already exists
            if User.objects.filter(email=email).exists():
                messages.error(request, 'A user with this email already exists.')
                return render(request, self.template_name)
            
            # Create user
            user = User.objects.create_user(
                email=email,
                first_name=first_name,
                last_name=last_name
            )
            user.set_password(password)
            user.save()
            
            # Create profile
            Profile.objects.create(
                user=user,
                role=UserRole.EMPLOYEE.value,
                is_active=True,
            )
            
            messages.success(request, f'Employee {first_name if first_name else email} {last_name if last_name else ""} added successfully!')
            return redirect('add-employee')

            
        except Exception as e:
            messages.error(request, f'Error creating employee: {str(e)}')
            return render(request, self.template_name)


 


class GetTeamsAndUsersView(APIView):
    permission_classes = (IsAuthenticated,)
    def get(self, request, *args, **kwargs):
        profiles = Profile.objects.filter(is_active=True).order_by(
            "user__email"
        )
        profiles_data = ProfileSerializer(profiles, many=True).data
        return Response({"profiles": profiles_data})


class UsersListView(APIView, LimitOffsetPagination):

    permission_classes = (IsAuthenticated,)
    def post(self, request, format=None):
        if int(self.request.user.profile.role) != UserRole.DEV_LEAD.value and not self.request.user.is_superuser:
            return Response(
                {"error": True, "errors": "Permission Denied"},
                status=status.HTTP_403_FORBIDDEN,
            )
        else:
            params = request.data
            if params:
                user_serializer = CreateUserSerializer(data=params)
                # Address functionality removed
                profile_serializer = CreateProfileSerializer(data=params)
                data = {}
                if not user_serializer.is_valid():
                    data["user_errors"] = dict(user_serializer.errors)
                if not profile_serializer.is_valid():
                    data["profile_errors"] = profile_serializer.errors
                # Address validation removed
                if data:
                    return Response(
                        {"error": True, "errors": data},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                # Address creation removed
                user = user_serializer.save(
                    is_active=True,
                )
                user.email = user.email
                user.save()
                # if params.get("password"):
                #     user.set_password(params.get("password"))
                #     user.save()
                profile = Profile.objects.create(
                    user=user,
                    date_of_joining=timezone.now(),
                    role=params.get("role"),
                )

                # send_email_to_new_user.delay(
                #     profile.id,
                # )
                return Response(
                    {"error": False, "message": "User Created Successfully"},
                    status=status.HTTP_201_CREATED,
                )


    def get(self, request, format=None):
        if int(self.request.user.profile.role) != UserRole.DEV_LEAD.value and not self.request.user.is_superuser:
            return Response(
                {"error": True, "errors": "Permission Denied"},
                status=status.HTTP_403_FORBIDDEN,
            )

        context = {}
        queryset = Profile.objects.filter().order_by("user__email")
        queryset_active_users = queryset.filter(is_active=True)
        results_active_users = self.paginate_queryset(
            queryset_active_users.distinct(), self.request, view=self
        )
        active_users = ProfileSerializer(results_active_users, many=True).data
        if results_active_users:
            offset = queryset_active_users.filter(
                id__gte=results_active_users[-1].id
            ).count()
            if offset == queryset_active_users.count():
                offset = None
        else:
            offset = 0
        context["active_users"] = {
            "active_users_count": self.count,
            "active_users": active_users,
            "offset": offset,
        }

        queryset_inactive_users = queryset.filter(is_active=False)
        results_inactive_users = self.paginate_queryset(
            queryset_inactive_users.distinct(), self.request, view=self
        )
        inactive_users = ProfileSerializer(results_inactive_users, many=True).data
        if results_inactive_users:
            offset = queryset_inactive_users.filter(
                id__gte=results_inactive_users[-1].id
            ).count()
            if offset == queryset_inactive_users.count():
                offset = None
        else:
            offset = 0
        context["inactive_users"] = {
            "inactive_users_count": self.count,
            "inactive_users": inactive_users,
            "offset": offset,
        }

        context["admin_email"] = settings.ADMIN_EMAIL
        context["roles"] = ROLES
        context["status"] = [("True", "Active"), ("False", "In Active")]
        return Response(context)


class UserDetailView(APIView):
    permission_classes = (IsAuthenticated,)

    def get_object(self, pk):
        profile = get_object_or_404(Profile, pk=pk)
        return profile

    def get(self, request, pk, format=None):
        profile_obj = self.get_object(pk)
        if (
            int(self.request.user.profile.role) != UserRole.DEV_LEAD.value
            and not self.request.user.profile.is_admin
            and self.request.user.profile.id != profile_obj.id
        ):
            return Response(
                {"error": True, "errors": "Permission Denied"},
                status=status.HTTP_403_FORBIDDEN,
            )
        context = {}
        context["profile_obj"] = ProfileSerializer(profile_obj).data
        return Response(
            {"error": False, "data": context},
            status=status.HTTP_200_OK,
        )

    def put(self, request, pk, format=None):
        params = request.data
        profile = self.get_object(pk)
        address_obj = profile.address
        if (
            int(self.request.user.profile.role) != UserRole.DEV_LEAD.value
            and not self.request.user.is_superuser
            and self.request.user.profile.id != profile.id
        ):
            return Response(
                {"error": True, "errors": "Permission Denied"},
                status=status.HTTP_403_FORBIDDEN,
            )
        serializer = CreateUserSerializer(
            data=params, instance=profile.user
        )
        # Address functionality removed
        profile_serializer = CreateProfileSerializer(data=params, instance=profile)
        data = {}
        if not serializer.is_valid():
            data["contact_errors"] = serializer.errors
        # Address validation removed
        if not profile_serializer.is_valid():
            data["profile_errors"] = (profile_serializer.errors,)
        if data:
            data["error"] = True
            return Response(
                data,
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Address creation removed
        user = serializer.save()
        user.email = user.email
        user.save()
        if profile_serializer.is_valid():
            profile = profile_serializer.save()
            return Response(
                {"error": False, "message": "User Updated Successfully"},
                status=status.HTTP_200_OK,
            )
        return Response(
            {"error": True, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def delete(self, request, pk, format=None):
        if int(self.request.user.profile.role) != UserRole.DEV_LEAD.value and not self.request.user.profile.is_admin:
            return Response(
                {"error": True, "errors": "Permission Denied"},
                status=status.HTTP_403_FORBIDDEN,
            )
        self.object = self.get_object(pk)
        if self.object.id == request.user.profile.id:
            return Response(
                {"error": True, "errors": "Permission Denied"},
                status=status.HTTP_403_FORBIDDEN,
            )
        deleted_by = self.request.user.profile.user.email
        send_email_user_delete.delay(
            self.object.user.email,
            deleted_by=deleted_by,
        )
        self.object.delete()
        return Response({"status": "success"}, status=status.HTTP_200_OK)


# check_header not working
class ApiHomeView(APIView):

    permission_classes = (IsAuthenticated,)

    def get(self, request, format=None):
        # Accounts/Contacts removed
        

        if int(self.request.user.profile.role) != UserRole.DEV_LEAD.value and not self.request.user.is_superuser:
            leads = leads.filter(
                Q(assigned_to__id__in=self.request.user.profile)
                | Q(created_by=self.request.user.profile.user)
            ).exclude(status="closed")
            opportunities = opportunities
        context = {}
        context["leads_count"] = leads.count()
        context["opportunities_count"] = 0
        context["leads"] = LeadSerializer(leads, many=True).data
        context["opportunities"] = []
        return Response(context, status=status.HTTP_200_OK)


class ProfileView(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, format=None):
        # profile=Profile.objects.get(user=request.user)
        context = {}
        context["user_obj"] = ProfileSerializer(self.request.user.profile).data
        return Response(context, status=status.HTTP_200_OK)


class UserStatusView(APIView):
    permission_classes = (IsAuthenticated,)

    def post(self, request, pk, format=None):
        if int(self.request.user.profile.role) != UserRole.DEV_LEAD.value and not self.request.user.is_superuser:
            return Response(
                {
                    "error": True,
                    "errors": "You do not have permission to perform this action",
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        params = request.data
        profiles = Profile.objects.filter()
        profile = profiles.get(id=pk)

        if params.get("status"):
            user_status = params.get("status")
            if user_status == "Active":
                profile.is_active = True
            elif user_status == "Inactive":
                profile.is_active = False
            else:
                return Response(
                    {"error": True, "errors": "Please enter Valid Status for user"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            profile.save()

        context = {}
        context["ROLE_EMPLOYEE_VALUE"] = UserRole.EMPLOYEE.value
        context["ROLE_DEV_LEAD_VALUE"] = UserRole.DEV_LEAD.value
        active_profiles = profiles.filter(is_active=True)
        inactive_profiles = profiles.filter(is_active=False)
        context["active_profiles"] = ProfileSerializer(active_profiles, many=True).data
        context["inactive_profiles"] = ProfileSerializer(
            inactive_profiles, many=True
        ).data
        return Response(context)


class DomainList(APIView):
    model = Leads
    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        api_settings = Leads.objects.filter()
        users = Profile.objects.filter(is_active=Trueg).order_by(
            "user__email"
        )
        return Response(
            {
                "error": False,
                "api_settings": LeadsListSerializer(api_settings, many=True).data,
                "users": ProfileSerializer(users, many=True).data,
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request, *args, **kwargs):
        params = request.data
        assign_to_list = []
        if params.get("lead_assigned_to"):
            assign_to_list = params.get("lead_assigned_to")
        serializer = LeadsSerializer(data=params)
        if serializer.is_valid():
            settings_obj = serializer.save(created_by=request.user.profile.user)
            if assign_to_list:
                settings_obj.lead_assigned_to.add(*assign_to_list)
            return Response(
                {"error": False, "message": "API key added sucessfully"},
                status=status.HTTP_201_CREATED,
            )
        return Response(
            {"error": True, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )


class DomainDetailView(APIView):
    model = Leads
    #authentication_classes = (CustomDualAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get(self, request, pk, format=None):
        api_setting = self.get_object(pk)
        return Response(
            {"error": False, "domain": LeadsListSerializer(api_setting).data},
            status=status.HTTP_200_OK,
        )

    def put(self, request, pk, **kwargs):
        api_setting = self.get_object(pk)
        params = request.data
        assign_to_list = []
        if params.get("lead_assigned_to"):
            assign_to_list = params.get("lead_assigned_to")
        serializer = LeadsSerializer(data=params, instance=api_setting)
        if serializer.is_valid():
            api_setting = serializer.save()
            api_setting.tags.clear()
            api_setting.lead_assigned_to.clear()
            if assign_to_list:
                api_setting.lead_assigned_to.add(*assign_to_list)
            return Response(
                {"error": False, "message": "API setting Updated sucessfully"},
                status=status.HTTP_200_OK,
            )
        return Response(
            {"error": True, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    def delete(self, request, pk, **kwargs):
        api_setting = self.get_object(pk)
        if api_setting:
            api_setting.delete()
        return Response(
            {"error": False, "message": "API setting deleted sucessfully"},
            status=status.HTTP_200_OK,
        )

class GoogleLoginView(APIView):
    """
    Check for authentication with google
    post:
        Returns token of logged In user
    """


    def post(self, request):
        payload = {'access_token': request.data.get("token")}  # validate the token
        r = requests.get('https://www.googleapis.com/oauth2/v2/userinfo', params=payload)
        data = json.loads(r.text)
        if 'error' in data:
            content = {'message': 'wrong google token / this google token is already expired.'}
            return Response(content)
        # create user if not exist
        try:
            user = User.objects.get(email=data['email'])
        except User.DoesNotExist:
            user = User()
            user.email = data['email']
            user.profile_pic = data['picture']
            # provider random default password
            user.password = make_password(BaseUserManager().make_random_password())
            user.email = data['email']
            user.save()
        token = RefreshToken.for_user(user)  # generate token without username & password
        response = {}
        response['username'] = user.email
        response['access_token'] = str(token.access_token)
        response['refresh_token'] = str(token)
        response['user_id'] = user.id
        return Response(response)

class TestEmailView(LoginRequiredMixin, View):
    """View for testing email functionality"""
    
    def get(self, request):
        # Only managers can test emails
        if int(request.user.profile.role) != UserRole.MANAGER.value:
            messages.error(request, "Only managers can test email functionality.")
            return redirect('site-admin')
        
        from django.conf import settings
        context = {
            'email_backend': settings.EMAIL_BACKEND,
            'from_email': getattr(settings, 'DEFAULT_FROM_EMAIL', 'Not configured'),
            'UserRole': UserRole
        }
        
        return render(request, 'common/test_email.html', context)
    
    def post(self, request):
        # Only managers can test emails
        if int(request.user.profile.role) != UserRole.MANAGER.value:
            messages.error(request, "Only managers can test email functionality.")
            return redirect('site-admin')
        
        from .email_utils import send_test_email
        
        email = request.POST.get('email')
        if not email:
            messages.error(request, "Please provide an email address.")
            return redirect('common:test-email')
        
        try:
            success = send_test_email(email)
            if success:
                messages.success(request, f"Test email sent successfully to {email}")
            else:
                messages.error(request, f"Failed to send test email to {email}")
        except Exception as e:
            messages.error(request, f"Error sending test email: {str(e)}")
        
        return redirect('common:test-email')
