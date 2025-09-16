from django.conf import settings
import jwt

def verify_jwt_token(token):
    try:
        payload = jwt.decode(token, (settings.SECRET_KEY), algorithms=[settings.JWT_ALGO])
        return True, payload
    except jwt.ExpiredSignatureError:
        return False, "Token is expired"
    except jwt.InvalidTokenError:
        return False, "Invalid token"
