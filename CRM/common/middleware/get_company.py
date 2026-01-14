from rest_framework.exceptions import AuthenticationFailed
from common.models import Profile


class GetProfile:
    """
    Middleware to attach user profile to request object
    for easy access in views.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Attach profile to request if user is authenticated
        if request.user.is_authenticated:
            try:
                request.profile = Profile.objects.get(user=request.user, is_active=True)
            except Profile.DoesNotExist:
                request.profile = None
        else:
            request.profile = None

        response = self.get_response(request)
        return response
