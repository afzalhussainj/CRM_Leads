from rest_framework.authentication import BaseAuthentication
from common.models import Profile,User

from common.utils.authentication import verify_jwt_token

class CustomDualAuthentication(BaseAuthentication):

    def authenticate(self, request):
        jwt_user = None
        profile = None

        # Check JWT authentication
        jwt_token = request.headers.get('Authorization', '').split(' ')[1] if 'Authorization' in request.headers else None
        if jwt_token:
            is_valid, jwt_payload = verify_jwt_token(jwt_token)
            if is_valid:
                jwt_user = (User.objects.get(id=jwt_payload['user_id']), True)
                if jwt_payload['user_id'] is not None:
                    profile = Profile.objects.get(
                        user_id=jwt_payload['user_id'], is_active=True
                    )
                    if profile:
                        request.user.profile = profile

        return jwt_user or profile
