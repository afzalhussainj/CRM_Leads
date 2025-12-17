import json

import requests
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.hashers import make_password
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from common.models import Leads, Profile, User
from common.serializer import *
from common.tasks import send_email_user_delete
from leads.models import Lead
from utils.roles_enum import UserRole

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
            # Optimize: Use select_related
            profile = Profile.objects.select_related('user').get(user=user, is_active=True)
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

@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_request(request):
    """
    Request password reset link.
    Takes email and sends password reset link to user's email.
    """
    email = request.data.get('email')
    
    if not email:
        return Response({
            'error': 'Email is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Check if user exists (but don't reveal if account exists for security)
    user = User.objects.filter(email=email, is_deleted=False).first()
    
    if not user:
        # Return generic message for security (don't reveal if account exists)
        return Response({
            'message': 'If an account with this email exists, a password reset link has been sent.'
        }, status=status.HTTP_200_OK)
    
    # Check if user is active
    if not user.is_active:
        return Response({
            'error': 'Account not found. Please contact your manager for assistance.'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Send password reset email
    try:
        from common.tasks import send_email_to_reset_password
        send_email_to_reset_password.delay(user.email)
        
        return Response({
            'message': 'If an account with this email exists, a password reset link has been sent.'
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({
            'error': 'Failed to send password reset email. Please try again later.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_employee(request):
    """
    Create a new employee.
    Only managers can create employees.
    """
    # Check if user is a manager
    if not hasattr(request.user, 'profile') or request.user.profile is None:
        return Response({
            'error': 'User profile not found. Please contact administrator.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    user_role = int(request.user.profile.role) if request.user.profile.role is not None else None
    
    if user_role != UserRole.MANAGER.value:
        return Response({
            'error': 'Only managers can create employees.'
        }, status=status.HTTP_403_FORBIDDEN)
    
    # Get request data
    email = request.data.get('email')
    first_name = request.data.get('first_name', '')
    last_name = request.data.get('last_name', '')
    password = request.data.get('password')
    phone = request.data.get('phone')
    alternate_phone = request.data.get('alternate_phone')
    
    # Validate required fields
    if not email:
        return Response({
            'error': 'Email is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if not password:
        return Response({
            'error': 'Password is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Validate password length
    if len(password) < 8:
        return Response({
            'error': 'Password must be at least 8 characters long'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Check if user already exists
    if User.objects.filter(email=email, is_deleted=False).exists():
        return Response({
            'error': 'A user with this email already exists.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Create user
        user = User.objects.create_user(
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
            is_active=True
        )
        
        # Create profile with employee role
        profile = Profile.objects.create(
            user=user,
            role=UserRole.EMPLOYEE.value,
            is_active=True,
            phone=phone if phone else None,
            alternate_phone=alternate_phone if alternate_phone else None,
        )
        
        # Optionally send activation email
        send_activation_email = request.data.get('send_activation_email', False)
        if send_activation_email:
            try:
                from common.tasks import send_email_to_new_user
                send_email_to_new_user.delay(user.id)
            except Exception as e:
                # Don't fail the request if email fails
                pass
        
        # Return created employee data
        profile_serializer = ProfileSerializer(profile)
        return Response({
            'message': f'Employee {first_name or email} {last_name or ""} created successfully.',
            'employee': profile_serializer.data
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        return Response({
            'error': f'Error creating employee: {str(e)}'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([AllowAny])
def password_reset_confirm(request):
    """
    Confirm password reset with token.
    Takes uid, token, and new password.
    Returns JWT tokens to log the user in.
    """
    uidb64 = request.data.get('uid')
    token = request.data.get('token')
    new_password = request.data.get('password')
    
    if not uidb64 or not token or not new_password:
        return Response({
            'error': 'uid, token, and password are required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Validate password length
    if len(new_password) < 8:
        return Response({
            'error': 'Password must be at least 8 characters long'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        from django.utils.encoding import force_str
        from django.utils.http import urlsafe_base64_decode
        from django.contrib.auth.tokens import default_token_generator
        
        # Decode user ID
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = User.objects.get(pk=uid, is_deleted=False)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            user = None
        
        if user is None:
            return Response({
                'error': 'Invalid reset link. Please request a new password reset link.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Verify token
        if not default_token_generator.check_token(user, token):
            return Response({
                'error': 'Invalid or expired reset link. Please request a new password reset link.'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if user is active
        if not user.is_active:
            return Response({
                'error': 'Account is inactive. Please contact your manager for assistance.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Set new password
        user.set_password(new_password)
        user.save()
        
        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        
        # Get user profile
        try:
            profile = Profile.objects.select_related('user').get(user=user, is_active=True)
            role = profile.role
        except Profile.DoesNotExist:
            role = None
        
        return Response({
            'message': 'Password reset successfully. You are now logged in.',
            'access_token': str(refresh.access_token),
            'refresh_token': str(refresh),
            'user': {
                'email': user.email,
                'role': role
            }
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response({
            'error': 'An error occurred while resetting your password. Please try again.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class GetTeamsAndUsersView(APIView):
    permission_classes = (IsAuthenticated,)
    def get(self, request, *args, **kwargs):
        # Optimize: Use select_related
        profiles = Profile.objects.select_related('user').filter(
            is_active=True,
            user__is_deleted=False
        ).order_by("user__email")
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
        # Optimize: Use select_related
        queryset = Profile.objects.select_related('user').filter(
            user__is_deleted=False
        ).order_by("user__email")
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
        # Optimize: Use select_related
        profiles = Profile.objects.select_related('user').filter(
            user__is_deleted=False
        )
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
        # Optimize: Use select_related
        api_settings = Leads.objects.select_related('created_by', 'created_by__user').filter()
        # Optimize: Use select_related and fix typo
        users = Profile.objects.select_related('user').filter(
            is_active=True,
            user__is_deleted=False
        ).order_by("user__email")
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

