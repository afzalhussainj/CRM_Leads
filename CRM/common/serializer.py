import re

from rest_framework import serializers

from common.models import (
    Profile,
    User,
)


class CreateUserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = (
            "email",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].required = True

    def validate_email(self, email):
        if self.instance:
            if self.instance.email != email:
                # Optimize: Use exists() with select_related is not needed for exists()
                if not Profile.objects.filter(user__email=email, user__is_deleted=False).exists():
                    return email
                raise serializers.ValidationError("Email already exists")
            return email
        # Optimize: Use exists() with filter
        if not Profile.objects.filter(user__email=email.lower(), user__is_deleted=False).exists():
            return email
        raise serializers.ValidationError("Given Email id already exists")


class CreateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profile
        fields = (
            "role",
            "phone",
            "alternate_phone"
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["alternate_phone"].required = False
        self.fields["role"].required = True
        self.fields["phone"].required = True


class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ["id","email"]


class ProfileSerializer(serializers.ModelSerializer):
    user_details = serializers.ReadOnlyField()  # Property from Profile model

    class Meta:
        model = Profile
        fields = (
            "id",
            "user_details",
            "role",
            "phone",
            "alternate_phone",
            "is_active",
            "created_at",
            "updated_at",
        )


class EmployeeSerializer(serializers.ModelSerializer):
    """Serializer for employee list with flat structure including User fields"""
    user_id = serializers.UUIDField(source='user.id', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    user_is_active = serializers.BooleanField(source='user.is_active', read_only=True)

    class Meta:
        model = Profile
        fields = (
            "id",
            "user_id",
            "email",
            "first_name",
            "last_name",
            "role",
            "phone",
            "alternate_phone",
            "is_active",
            "user_is_active",
            "created_at",
            "updated_at",
        )



def find_urls(string):
    # website_regex = "^((http|https)://)?([A-Za-z0-9.-]+\.[A-Za-z]{2,63})?$"  # (http(s)://)google.com or google.com
    # website_regex = "^https?://([A-Za-z0-9.-]+\.[A-Za-z]{2,63})?$"  # (http(s)://)google.com
    # http(s)://google.com
    website_regex = "^https?://[A-Za-z0-9.-]+\.[A-Za-z]{2,63}$"
    # http(s)://google.com:8000
    website_regex_port = "^https?://[A-Za-z0-9.-]+\.[A-Za-z]{2,63}:[0-9]{2,4}$"
    url = re.findall(website_regex, string)
    url_port = re.findall(website_regex_port, string)
    if url and url[0] != "":
        return url
    return url_port






