from rest_framework import serializers

from common.serializer import (
    ProfileSerializer,
    UserSerializer,
)
from leads.models import Lead


class LeadSerializer(serializers.ModelSerializer):
    assigned_to = ProfileSerializer(read_only=True)
    created_by = UserSerializer()

    class Meta:
        model = Lead
        fields = (
            "id",
            "title",
            "status",
            "source",
            "description",
            "company_name",
            "contact_first_name",
            "contact_last_name",
            "contact_email",
            "contact_phone",
            "contact_position_title",
            "contact_linkedin_url",
            "assigned_to",
            "follow_up_at",
            "follow_up_status",
            "created_by",
            "created_at",
            "is_active",
        )


class LeadCreateSerializer(serializers.ModelSerializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].required = True

    def validate_title(self, title):
        if self.instance:
            if (
                Lead.objects.filter(title__iexact=title)
                .exclude(id=self.instance.id)
                .exists()
            ):
                raise serializers.ValidationError(
                    "Lead already exists with this title"
                )
        else:
            if Lead.objects.filter(title__iexact=title).exists():
                raise serializers.ValidationError(
                    "Lead already exists with this title"
                )
        return title

    class Meta:
        model = Lead
        fields = (
            "id",
            "title",
            "status",
            "source",
            "description",
            "company_name",
            "contact_first_name",
            "contact_last_name",
            "contact_email",
            "contact_phone",
            "contact_position_title",
            "contact_linkedin_url",
            "assigned_to",
            "follow_up_at",
            "follow_up_status",
            "created_at",
            "is_active",
        )


class LeadDetailEditSerializer(serializers.ModelSerializer):
    assigned_to = ProfileSerializer(read_only=True)
    created_by = UserSerializer()

    class Meta:
        model = Lead
        fields = (
            "id",
            "title",
            "status",
            "source",
            "description",
            "company_name",
            "contact_first_name",
            "contact_last_name",
            "contact_email",
            "contact_phone",
            "contact_position_title",
            "contact_linkedin_url",
            "assigned_to",
            "follow_up_at",
            "follow_up_status",
            "created_by",
            "created_at",
            "is_active",
        )

class CreateLeadFromSiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = (
            "title",
            "status",
            "source",
            "description",
            "company_name",
            "contact_first_name",
            "contact_last_name",
            "contact_email",
            "contact_phone",
            "contact_position_title",
            "contact_linkedin_url",
        )
