from rest_framework import serializers

from common.serializer import (
    ProfileSerializer,
    UserSerializer,
)
from leads.models import Lead


class LeadSerializer(serializers.ModelSerializer):
    assigned_to = ProfileSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)

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
        # Only title is required
        self.fields["title"].required = True
        
        # Make all optional fields not required (they can be missing from frontend)
        # These fields have blank=True, null=True, or have defaults in the model
        optional_fields = [
            "source", "description", "company_name",
            "contact_first_name", "contact_last_name", "contact_email",
            "contact_phone", "contact_position_title", "contact_linkedin_url",
            "assigned_to", "follow_up_at", "follow_up_status", "is_active"
        ]
        for field_name in optional_fields:
            if field_name in self.fields:
                self.fields[field_name].required = False
                # Set allow_null and allow_blank based on field type
                if hasattr(self.fields[field_name], 'allow_null'):
                    self.fields[field_name].allow_null = True
                if hasattr(self.fields[field_name], 'allow_blank'):
                    self.fields[field_name].allow_blank = True
        
        # Status is ForeignKey, make it optional for updates but handle gracefully
        if "status" in self.fields:
            self.fields["status"].required = False
            if hasattr(self.fields["status"], 'allow_null'):
                self.fields["status"].allow_null = True

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

    def validate_follow_up_status(self, value):
        """
        Automatically convert follow_up_status to lowercase.
        Accepts 'Pending', 'PENDING', 'pending', etc. and converts to 'pending'.
        Also accepts None, empty string, or null values.
        """
        if value is None or value == '':
            return None  # Allow empty/null values, will use model default
        value = str(value).lower().strip()
        # Validate against allowed choices
        valid_choices = ['pending', 'done']
        if value not in valid_choices:
            raise serializers.ValidationError(
                f"follow_up_status must be one of: {', '.join(valid_choices)}"
            )
        return value

    def validate_source(self, value):
        """Trim whitespace from source field."""
        if value:
            return value.strip()
        return value

    def validate_company_name(self, value):
        """Trim whitespace from company_name field."""
        if value:
            return value.strip()
        return value

    def validate_contact_first_name(self, value):
        """Trim whitespace from contact_first_name field."""
        if value:
            return value.strip()
        return value

    def validate_contact_last_name(self, value):
        """Trim whitespace from contact_last_name field."""
        if value:
            return value.strip()
        return value

    def validate_contact_email(self, value):
        """Convert email to lowercase and trim whitespace."""
        if value:
            return value.lower().strip()
        return value

    def validate_contact_position_title(self, value):
        """Trim whitespace from contact_position_title field."""
        if value:
            return value.strip()
        return value

    def validate_description(self, value):
        """Trim whitespace from description field."""
        if value:
            return value.strip()
        return value

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
    created_by = UserSerializer(read_only=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make all optional fields not required (they can be missing from frontend)
        # These fields have blank=True, null=True, or have defaults in the model
        optional_fields = [
            "title", "source", "description", "company_name",
            "contact_first_name", "contact_last_name", "contact_email",
            "contact_phone", "contact_position_title", "contact_linkedin_url",
            "assigned_to", "follow_up_at", "follow_up_status", "is_active"
        ]
        for field_name in optional_fields:
            if field_name in self.fields:
                self.fields[field_name].required = False
                # Set allow_null and allow_blank based on field type
                if hasattr(self.fields[field_name], 'allow_null'):
                    self.fields[field_name].allow_null = True
                if hasattr(self.fields[field_name], 'allow_blank'):
                    self.fields[field_name].allow_blank = True
        
        # Status is ForeignKey, make it optional for updates but handle gracefully
        if "status" in self.fields:
            self.fields["status"].required = False
            if hasattr(self.fields["status"], 'allow_null'):
                self.fields["status"].allow_null = True

    def validate_follow_up_status(self, value):
        """
        Automatically convert follow_up_status to lowercase.
        Accepts 'Pending', 'PENDING', 'pending', etc. and converts to 'pending'.
        Also accepts None, empty string, or null values.
        """
        if value is None or value == '':
            return None  # Allow empty/null values
        value = str(value).lower().strip()
        # Validate against allowed choices
        valid_choices = ['pending', 'done']
        if value not in valid_choices:
            raise serializers.ValidationError(
                f"follow_up_status must be one of: {', '.join(valid_choices)}"
            )
        return value

    def validate_source(self, value):
        """Trim whitespace from source field."""
        if value:
            return value.strip()
        return value

    def validate_company_name(self, value):
        """Trim whitespace from company_name field."""
        if value:
            return value.strip()
        return value

    def validate_contact_first_name(self, value):
        """Trim whitespace from contact_first_name field."""
        if value:
            return value.strip()
        return value

    def validate_contact_last_name(self, value):
        """Trim whitespace from contact_last_name field."""
        if value:
            return value.strip()
        return value

    def validate_contact_email(self, value):
        """Convert email to lowercase and trim whitespace."""
        if value:
            return value.lower().strip()
        return value

    def validate_contact_position_title(self, value):
        """Trim whitespace from contact_position_title field."""
        if value:
            return value.strip()
        return value

    def validate_description(self, value):
        """Trim whitespace from description field."""
        if value:
            return value.strip()
        return value

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
