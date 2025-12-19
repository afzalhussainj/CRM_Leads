from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from common.models import Profile,User

from common.utils.authentication import verify_jwt_token

class CustomDualAuthentication(BaseAuthentication):

    def authenticate(self, request):
        jwt_user = None
        profile = None

        # Check JWT authentication from HTTP-only cookie first (preferred method)
        jwt_token = None
        if hasattr(settings, 'JWT_COOKIE_NAME'):
            jwt_token = request.COOKIES.get(settings.JWT_COOKIE_NAME)
        
        # Fallback to Authorization header if cookie not found (for backward compatibility)
        if not jwt_token:
            auth_header = request.headers.get('Authorization', '')
            if auth_header.startswith('Bearer '):
                jwt_token = auth_header.split(' ')[1]
            elif 'Authorization' in request.headers:
                # Handle case where header might not have 'Bearer ' prefix
                jwt_token = request.headers.get('Authorization', '').split(' ')[-1] if ' ' in request.headers.get('Authorization', '') else None
        
        if jwt_token:
            is_valid, jwt_payload = verify_jwt_token(jwt_token)
            if is_valid:
                # Optimize: Use select_related
                jwt_user = (User.objects.get(id=jwt_payload['user_id']), True)
                if jwt_payload['user_id'] is not None:
                    profile = Profile.objects.select_related('user').get(
                        user_id=jwt_payload['user_id'], is_active=True
                    )
                    if profile:
                        request.user.profile = profile

        return jwt_user or profile
