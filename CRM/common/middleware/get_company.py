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
            
            
            # Handle session authentication (for UI requests)
            if request.user.is_authenticated and not request.profile:
                try:
                    # Get the first active profile for the user
                    profile = Profile.objects.filter(user=request.user, is_active=True).first()
                    if profile:
                        request.profile = profile
                        print(f"Profile set for user {request.user.email}: {profile.role}")
                    else:
                        print(f"No active profile found for user {request.user.email}")
                        # For UI requests, if no profile is found, we'll let the view handle it
                        # The view should redirect to login
                except Exception as e:
                    print(f"Session authentication failed: {e}")
                    
        except Exception as e:
            print(f'Middleware error: {e}')
            # Don't raise PermissionDenied for UI requests, let Django handle it
            if request.path.startswith('/api/'):
             raise PermissionDenied()
