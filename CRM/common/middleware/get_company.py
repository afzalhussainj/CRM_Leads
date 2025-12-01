import jwt
from django.conf import settings
from django.core.exceptions import PermissionDenied

from common.models import Profile

def get_actual_value(request):
    if request.user is None:
        return None

    return request.user #here should have value, so any code using request.user will work

class GetProfile(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        self.process_request(request)
        return self.get_response(request)

    def process_request(self, request):
        try:
            # Skip middleware for static/media files to avoid unnecessary queries
            if request.path.startswith(('/static/', '/media/', '/favicon.ico')):
                return None
            
            # Handle session authentication (for UI requests)
            if request.user.is_authenticated and not hasattr(request.user, 'profile'):
                try:
                    # Optimize: Use select_related and cache the profile
                    # Check if profile was already loaded by Django's authentication
                    if hasattr(request.user, '_profile_cache'):
                        request.user.profile = request.user._profile_cache
                    else:
                        profile = Profile.objects.select_related('user').filter(
                            user=request.user, 
                            is_active=True
                        ).first()
                        if profile:
                            request.user.profile = profile
                            request.user._profile_cache = profile  # Cache for this request
                except Exception as e:
                    print(f"Session authentication failed: {e}")
                    
        except Exception as e:
            print(f'Middleware error: {e}')
            # Don't raise PermissionDenied for UI requests, let Django handle it
            if request.path.startswith('/api/'):
             raise PermissionDenied()
