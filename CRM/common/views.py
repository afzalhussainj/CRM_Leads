from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth import get_user_model
from django.db.models import Count, Case, When, Value, CharField, OuterRef, Exists, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from datetime import timedelta

from common.models import Profile, User
from common.serializer import *
from common.tasks import send_email_user_delete
from common.utils.choices import ROLES
from leads.serializer import LeadNoteSerializer, LeadSerializer
from leads.models import Lead, LeadNote, LeadNoteRead
from utils.roles_enum import UserRole

User = get_user_model()


def set_jwt_cookies(response, refresh_token):
    """
    Helper function to set HTTP-only cookies for JWT tokens.
    
    Args:
        response: Django Response object
        refresh_token: RefreshToken instance
    """
    access_token = refresh_token.access_token
    access_lifetime = settings.SIMPLE_JWT.get('ACCESS_TOKEN_LIFETIME', timedelta(days=1))
    refresh_lifetime = settings.SIMPLE_JWT.get('REFRESH_TOKEN_LIFETIME', timedelta(days=365))
    
    # Set access token cookie
    cookie_kwargs = {
        'key': settings.JWT_COOKIE_NAME,
        'value': str(access_token),
        'max_age': int(access_lifetime.total_seconds()),
        'httponly': settings.JWT_COOKIE_HTTPONLY,
        'secure': settings.JWT_COOKIE_SECURE,
        'samesite': settings.JWT_COOKIE_SAMESITE,
        'path': '/',
    }
    # Only set domain if it's explicitly configured (None for cross-origin)
    if settings.JWT_COOKIE_DOMAIN:
        cookie_kwargs['domain'] = settings.JWT_COOKIE_DOMAIN
    response.set_cookie(**cookie_kwargs)
    
    # Set refresh token cookie
    refresh_cookie_kwargs = {
        'key': settings.JWT_REFRESH_COOKIE_NAME,
        'value': str(refresh_token),
        'max_age': int(refresh_lifetime.total_seconds()),
        'httponly': settings.JWT_COOKIE_HTTPONLY,
        'secure': settings.JWT_COOKIE_SECURE,
        'samesite': settings.JWT_COOKIE_SAMESITE,
        'path': '/',
    }
    # Only set domain if it's explicitly configured (None for cross-origin)
    if settings.JWT_COOKIE_DOMAIN:
        refresh_cookie_kwargs['domain'] = settings.JWT_COOKIE_DOMAIN
    response.set_cookie(**refresh_cookie_kwargs)
    
    return response


def clear_jwt_cookies(response):
    """
    Helper function to clear HTTP-only JWT cookies.
    
    Args:
        response: Django Response object
    """
    delete_kwargs = {
        'key': settings.JWT_COOKIE_NAME,
        'path': '/',
        'samesite': settings.JWT_COOKIE_SAMESITE,
    }
    if settings.JWT_COOKIE_DOMAIN:
        delete_kwargs['domain'] = settings.JWT_COOKIE_DOMAIN
    response.delete_cookie(**delete_kwargs)
    
    refresh_delete_kwargs = {
        'key': settings.JWT_REFRESH_COOKIE_NAME,
        'path': '/',
        'samesite': settings.JWT_COOKIE_SAMESITE,
    }
    if settings.JWT_COOKIE_DOMAIN:
        refresh_delete_kwargs['domain'] = settings.JWT_COOKIE_DOMAIN
    response.delete_cookie(**refresh_delete_kwargs)
    
    return response

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def login_view(request):
    """Login view that sets JWT tokens in HTTP-only cookies"""
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
            
            # Create response with user data (no tokens in body)
            response = Response({
                'message': 'Login successful',
                'user': {
                    'email': user.email,
                    'role': profile.role,
                    'id': user.id,
                    'name': user.first_name + ' ' + user.last_name
                }
            }, status=status.HTTP_200_OK)
            
            # Set HTTP-only cookies
            set_jwt_cookies(response, refresh)
            
            return response
        except Profile.DoesNotExist:
            return Response({
                'error': 'User profile not found or inactive'
            }, status=status.HTTP_401_UNAUTHORIZED)
    else:
        return Response({
            'error': 'Invalid credentials'
        }, status=status.HTTP_401_UNAUTHORIZED)

@csrf_exempt
@api_view(['POST'])
def logout_view(request):
    """Logout view that clears JWT cookies"""
    logout(request)
    
    response = Response({'message': 'Logged out successfully'})
    clear_jwt_cookies(response)
    
    return response

@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def refresh_token_view(request):
    """
    Refresh token view that reads refresh token from HTTP-only cookie
    and returns new access token in HTTP-only cookie.
    """
    # Get refresh token from cookie
    refresh_token_str = request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)
    
    if not refresh_token_str:
        return Response({
            'error': 'Refresh token not found. Please login again.'
        }, status=status.HTTP_401_UNAUTHORIZED)
    
    try:
        # Create RefreshToken instance from string
        refresh = RefreshToken(refresh_token_str)
        
        # Generate new access token
        access_token = refresh.access_token
        
        # Create response
        response = Response({
            'message': 'Token refreshed successfully'
        }, status=status.HTTP_200_OK)
        
        # Set new access token cookie
        access_lifetime = settings.SIMPLE_JWT.get('ACCESS_TOKEN_LIFETIME', timedelta(days=1))
        response.set_cookie(
            key=settings.JWT_COOKIE_NAME,
            value=str(access_token),
            max_age=int(access_lifetime.total_seconds()),
            httponly=settings.JWT_COOKIE_HTTPONLY,
            secure=settings.JWT_COOKIE_SECURE,
            samesite=settings.JWT_COOKIE_SAMESITE,
            domain=settings.JWT_COOKIE_DOMAIN,
            path='/',
        )
        
        return response
        
    except Exception as e:
        # Token is invalid or expired
        response = Response({
            'error': 'Invalid or expired refresh token. Please login again.'
        }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Clear cookies on error
        clear_jwt_cookies(response)
        
        return response

@csrf_exempt
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
    
    # Send password reset email (synchronous helper)
    from common.tasks import send_email_to_reset_password
    send_email_to_reset_password(user.email)
    
    return Response({
        'message': 'If an account with this email exists, a password reset link has been sent.'
    }, status=status.HTTP_200_OK)

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
    phone = request.data.get('phone')
    alternate_phone = request.data.get('alternate_phone')
    
    # Validate required fields
    if not email:
        return Response({
            'error': 'Email is required'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Check if user already exists
    if User.objects.filter(email=email, is_deleted=False).exists():
        return Response({
            'error': 'A user with this email already exists.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    if User.objects.filter(email=email, is_deleted=True).exists():
        user = User.objects.get(email=email, is_deleted=True)
        user.is_deleted = False
        user.save()
        return Response({
            'message': f'Employee {first_name or email} {last_name or ""} restored successfully.',
        }, status=status.HTTP_200_OK)

    try:
        # Create user
        user = User.objects.create_user(
            email=email,
            first_name=first_name,
            last_name=last_name,
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
        
        # Send password set email to new employee
        try:
            from common.tasks import send_password_set_email_to_new_employee
            send_password_set_email_to_new_employee(user.id)
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

@csrf_exempt
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
        
        # Create response with user data (no tokens in body)
        response = Response({
            'message': 'Password reset successfully. You are now logged in.',
            'user': {
                'email': user.email,
                'role': role,
                'id': user.id,
                'name': user.first_name + ' ' + user.last_name
            }
        }, status=status.HTTP_200_OK)
        
        # Set HTTP-only cookies
        set_jwt_cookies(response, refresh)
        
        return response
        
    except Exception as e:
        return Response({
            'error': 'An error occurred while resetting your password. Please try again.'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UsersListView(APIView, LimitOffsetPagination):

    permission_classes = (IsAuthenticated,)
    def post(self, request, format=None):
        if int(self.request.user.profile.role) != UserRole.MANAGER.value and not self.request.user.is_superuser:
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
        if int(self.request.user.profile.role) != UserRole.MANAGER.value and not self.request.user.is_superuser:
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
            int(self.request.user.profile.role) != UserRole.MANAGER.value
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
            int(self.request.user.profile.role) != UserRole.MANAGER.value
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
        if int(self.request.user.profile.role) != UserRole.MANAGER.value and not self.request.user.profile.is_admin:
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
        send_email_user_delete(
            self.object.user.email,
            deleted_by=deleted_by,
        )
        self.object.delete()
        return Response({"status": "success"}, status=status.HTTP_200_OK)


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
        if int(self.request.user.profile.role) != UserRole.MANAGER.value and not self.request.user.is_superuser:
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

        context = {}
        context["ROLE_EMPLOYEE_VALUE"] = UserRole.EMPLOYEE.value
        active_profiles = profiles.filter(is_active=True)
        inactive_profiles = profiles.filter(is_active=False)
        context["active_profiles"] = ProfileSerializer(active_profiles, many=True).data
        context["inactive_profiles"] = ProfileSerializer(
            inactive_profiles, many=True
        ).data
        return Response(context)

class DashboardUnreadNotes(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, **kwargs):
        user = request.user
        profile = getattr(user, 'profile', None)

        if not profile:
            return Response(
                {"error": True, "message": "User profile not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_role = int(profile.role) if profile.role is not None else None

        # Base unread notes query
        unread_notes = LeadNote.objects.filter(
            lead__is_active=True
        ).exclude(
            author__user=user
        )

        # Role-based filtering
        if user_role == UserRole.EMPLOYEE.value:
            unread_notes = unread_notes.filter(
                lead__assigned_to=profile
            )

        # Efficient "not read by user" check via LeadNoteRead
        read_subquery = LeadNoteRead.objects.filter(
            note_id=OuterRef('pk'),
            user_id=user.id,
        )

        unread_notes = unread_notes.annotate(
            is_read=Exists(read_subquery)
        ).filter(
            is_read=False
        )

        # Ordering + limiting
        unread_notes = unread_notes.select_related(
            'lead', 'lead__status', 'author', 'author__user'
        ).order_by('-created_at')

        # Count (cheap query)
        unread_count = unread_notes.count()

        serializer = LeadNoteSerializer(unread_notes, many=True)

        return Response(
            {
                "success": True,
                "unread_count": unread_count,
                "notes": serializer.data,
            },
            status=status.HTTP_200_OK,
        )

class DashboardReminders(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, **kwargs):
        user = request.user
        profile = getattr(user, 'profile', None)

        if not profile:
            return Response(
                {"error": True, "message": "User profile not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_role = int(profile.role) if profile.role is not None else None

        # Base queryset (lean & indexed)
        leads = Lead.objects.filter(is_active=True)

        if user_role == UserRole.EMPLOYEE.value:
            leads = leads.filter(assigned_to=profile)

        # Time windows
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        # ---------- COUNTS (single DB hit) ----------
        counts = leads.aggregate(
            overdue=Count(
                'id',
                filter=Q(
                    follow_up_status='pending',
                    follow_up_at__lt=today_start
                ),
            ),
            due_today=Count(
                'id',
                filter=Q(
                    follow_up_status='pending',
                    follow_up_at__gte=today_start,
                    follow_up_at__lt=today_end
                ),
            ),
            upcoming=Count(
                'id',
                filter=Q(
                    follow_up_status='pending',
                    follow_up_at__gte=today_end
                ),
            ),
            done=Count(
                'id',
                filter=Q(follow_up_status='done'),
            ),
        )

        # ---------- FETCH LIMITED LEADS ----------
        base_fields = (
            'id', 'name', 'follow_up_at',
            'status', 'assigned_to'
        )

        overdue_qs = leads.filter(
            follow_up_status='pending',
            follow_up_at__lt=today_start
        ).only(*base_fields).order_by('follow_up_at')

        due_today_qs = leads.filter(
            follow_up_status='pending',
            follow_up_at__gte=today_start,
            follow_up_at__lt=today_end
        ).only(*base_fields).order_by('follow_up_at')

        upcoming_qs = leads.filter(
            follow_up_status='pending',
            follow_up_at__gte=today_end
        ).only(*base_fields).order_by('follow_up_at')[:self.LIMIT]

        return Response(
            {
                "success": True,
                "reminders": {
                    "overdue": {
                        "count": counts["overdue"],
                        "leads": LeadSerializer(overdue_qs, many=True).data,
                    },
                    "due_today": {
                        "count": counts["due_today"],
                        "leads": LeadSerializer(due_today_qs, many=True).data,
                    },
                    "upcoming": {
                        "count": counts["upcoming"],
                        "leads": LeadSerializer(upcoming_qs, many=True).data,
                    },
                    "done": {
                        "count": counts["done"],
                        "leads": [],
                    },
                },
            },
            status=status.HTTP_200_OK,
        )

class DashboardLeadStatusesAndEmployees(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, **kwargs):
        user = request.user
        profile = getattr(user, 'profile', None)

        if not profile:
            return Response(
                {"error": True, "message": "User profile not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_role = int(profile.role) if profile.role is not None else None

        leads = Lead.objects.filter(is_active=True)

        if user_role == UserRole.EMPLOYEE.value:
            leads = leads.filter(assigned_to_id=profile.id)

        status_counts = (
            leads
            .values('status_id', 'status__name')
            .annotate(count=Count('id'))
            .order_by('status__name')
        )

        # ---- EMPLOYEE COUNT (cached) ----
        employee_count = 0
        if user_role == UserRole.MANAGER.value:

            employee_count = Profile.objects.filter(
                role=UserRole.EMPLOYEE.value,
                is_active=True,
                user__is_deleted=False,
            ).count()

        return Response(
            {
                "success": True,
                "lead_statuses": list(status_counts),
                "employee_count": employee_count,
            },
            status=status.HTTP_200_OK,
        )

class Dashboard(APIView):
    permission_classes = (IsAuthenticated,)

    def get(self, request, **kwargs):
        # Validate user profile
        user = request.user
        profile = getattr(user, 'profile', None)
        if not profile:
            return Response(
                {"error": True, "message": "User profile not found."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_role = int(profile.role) if profile.role is not None else None

        # Base lead queryset (role-based) with optimizations
        leads_base = Lead.objects.select_related(
            'status', 'lifecycle', 'assigned_to', 'assigned_to__user'
        ).filter(is_active=True)
        
        if user_role == UserRole.EMPLOYEE.value:
            leads_queryset = leads_base.filter(assigned_to=profile)
        else:
            leads_queryset = leads_base

        # Lead counts by status - optimized
        status_counts = (
            leads_queryset
            .values('status__id', 'status__name')
            .annotate(count=Count('id'))
            .order_by('status__name')
        )

        # Unread notes - optimized with prefetch
        unread_notes_qs = (
            LeadNote.objects.filter(
                lead__in=leads_queryset
            )
            .exclude(author__user=user)
            .exclude(read_by__user=user)
            .select_related('lead', 'author', 'author__user', 'lead__status')
            .order_by('-created_at')
        )

        unread_notes_count = unread_notes_qs.count()
        unread_notes_serializer = LeadNoteSerializer(unread_notes_qs, many=True)

        # Reminders - optimized with aggregation instead of loops
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)

        # Get counts only for summary
        overdue_count = leads_queryset.filter(
            follow_up_status='pending',
            follow_up_at__lt=today_start
        ).count()
        
        due_today_count = leads_queryset.filter(
            follow_up_status='pending',
            follow_up_at__gte=today_start,
            follow_up_at__lt=today_end
        ).count()
        
        upcoming_count = leads_queryset.filter(
            follow_up_status='pending',
            follow_up_at__gte=today_end
        ).count()
        
        done_count = leads_queryset.filter(
            follow_up_status='done'
        ).count()

        # Fetch actual leads only if needed (limit results)
        overdue_leads = list(leads_queryset.filter(
            follow_up_status='pending',
            follow_up_at__lt=today_start
        ))
        
        due_today_leads = list(leads_queryset.filter(
            follow_up_status='pending',
            follow_up_at__gte=today_start,
            follow_up_at__lt=today_end
        ))
        
        upcoming_leads = list(leads_queryset.filter(
            follow_up_status='pending',
            follow_up_at__gte=today_end
        ))

        # Employee count - cached
        employee_count = 0
        if user_role == UserRole.MANAGER.value:
            employee_count = Profile.objects.filter(
                role=UserRole.EMPLOYEE.value,
                is_active=True,
                user__is_deleted=False
            ).count()

        response_data = {
            "unread_notes": {
                "success": True,
                "unread_count": unread_notes_count,
                "notes": unread_notes_serializer.data,
            },
            "lead_statuses": list(status_counts),
            "reminders": {
                "overdue": {
                    "count": overdue_count,
                    "leads": LeadSerializer(overdue_leads, many=True).data,
                },
                "due_today": {
                    "count": due_today_count,
                    "leads": LeadSerializer(due_today_leads, many=True).data,
                },
                "upcoming": {
                    "count": upcoming_count,
                    "leads": LeadSerializer(upcoming_leads, many=True).data,
                },
                "done": {
                    "count": done_count,
                    "leads": [],  # Don't return done leads to reduce payload
                },
            },
            "employee_count": employee_count,
        }

        return Response(response_data, status=status.HTTP_200_OK)
