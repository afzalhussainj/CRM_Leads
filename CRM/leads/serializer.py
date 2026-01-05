from rest_framework import serializers
from datetime import datetime
import re

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
    # Override follow_up_status to accept any case variant
    follow_up_status = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True
    )
    
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

    def validate_status(self, value):
        """
        Validate status field. Accepts either:
        - LeadStatus ID (integer)
        - LeadStatus instance
        - None (to clear status)
        """
        if value is None:
            return None
        
        # If already a LeadStatus instance, return as-is
        from common.models import LeadStatus
        if isinstance(value, LeadStatus):
            return value
        
        # If it's an integer/string that looks like an ID, try to get by ID
        if isinstance(value, (int, str)) and str(value).isdigit():
            try:
                return LeadStatus.objects.get(pk=int(value))
            except LeadStatus.DoesNotExist:
                raise serializers.ValidationError(f"LeadStatus with ID {value} does not exist.")
        
        # If it's a string (name), try to get by name
        if isinstance(value, str):
            try:
                return LeadStatus.objects.get(name=value)
            except LeadStatus.DoesNotExist:
                raise serializers.ValidationError(f"LeadStatus with name '{value}' does not exist.")
            except LeadStatus.MultipleObjectsReturned:
                raise serializers.ValidationError(f"Multiple LeadStatus objects found with name '{value}'.")
        
        # If we get here, value is not a valid format
        raise serializers.ValidationError("Status must be a LeadStatus ID (integer) or name (string).")

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

    def validate_follow_up_at(self, value):
        """
        Handle date-only strings and convert to datetime.
        Accepts '2025-12-23' and converts to datetime.
        """
        if value is None or value == '':
            return None
        
        # If already a datetime, return as-is
        if isinstance(value, datetime):
            return value
        
        # If string, try to parse as date-only first, then datetime
        if isinstance(value, str):
            value = value.strip()
            # Try date-only format (YYYY-MM-DD)
            try:
                dt = datetime.strptime(value, '%Y-%m-%d')
                return dt
            except ValueError:
                pass
            # Try ISO datetime format
            try:
                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                return dt
            except ValueError:
                pass
            raise serializers.ValidationError(
                "Invalid date format. Use YYYY-MM-DD or ISO 8601 datetime format."
            )
        
        return value

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

    def validate(self, data):
        """
        Cross-field validation: If one of follow_up_at or follow_up_status is provided,
        the other must also be provided.
        """
        follow_up_at = data.get('follow_up_at')
        follow_up_status = data.get('follow_up_status')
        
        # Check if follow_up_status is provided (not None and not empty string)
        has_follow_up_status = follow_up_status is not None and follow_up_status != ''
        # Check if follow_up_at is provided (not None)
        has_follow_up_at = follow_up_at is not None
        
        # If one is provided but the other is not, raise validation error
        if has_follow_up_at and not has_follow_up_status:
            raise serializers.ValidationError({
                'follow_up_status': 'follow_up_status is required when follow_up_at is provided.'
            })
        
        if has_follow_up_status and not has_follow_up_at:
            raise serializers.ValidationError({
                'follow_up_at': 'follow_up_at is required when follow_up_status is provided.'
            })
        
        return data

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

    def validate_contact_phone(self, value):
        """
        Clean phone number by removing dashes, spaces, and other formatting characters.
        Accepts any format and just removes formatting.
        """
        if not value or value == '':
            return None
        
        # Convert to string and trim whitespace
        phone_str = str(value).strip()
        
        # Remove common formatting characters: dashes, spaces, parentheses, dots
        phone_clean = re.sub(r'[-\s()\.]', '', phone_str)
        
        # If empty after cleaning, return None
        if not phone_clean:
            return None
        
        return phone_clean

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
    # Override follow_up_status to accept any case variant
    follow_up_status = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True
    )

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

    def validate_follow_up_at(self, value):
        """
        Handle date-only strings and convert to datetime.
        Accepts '2025-12-23' and converts to datetime.
        """
        if value is None or value == '':
            return None
        
        # If already a datetime, return as-is
        if isinstance(value, datetime):
            return value
        
        # If string, try to parse as date-only first, then datetime
        if isinstance(value, str):
            value = value.strip()
            # Try date-only format (YYYY-MM-DD)
            try:
                dt = datetime.strptime(value, '%Y-%m-%d')
                return dt
            except ValueError:
                pass
            # Try ISO datetime format
            try:
                dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
                return dt
            except ValueError:
                pass
            raise serializers.ValidationError(
                "Invalid date format. Use YYYY-MM-DD or ISO 8601 datetime format."
            )
        
        return value

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

    def validate(self, data):
        """
        Cross-field validation: If one of follow_up_at or follow_up_status is provided,
        the other must also be provided.
        """
        follow_up_at = data.get('follow_up_at')
        follow_up_status = data.get('follow_up_status')
        
        # Check if follow_up_status is provided (not None and not empty string)
        has_follow_up_status = follow_up_status is not None and follow_up_status != ''
        # Check if follow_up_at is provided (not None)
        has_follow_up_at = follow_up_at is not None
        
        # If one is provided but the other is not, raise validation error
        if has_follow_up_at and not has_follow_up_status:
            raise serializers.ValidationError({
                'follow_up_status': 'follow_up_status is required when follow_up_at is provided.'
            })
        
        if has_follow_up_status and not has_follow_up_at:
            raise serializers.ValidationError({
                'follow_up_at': 'follow_up_at is required when follow_up_status is provided.'
            })
        
        return data

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

    def validate_contact_phone(self, value):
        """
        Clean phone number by removing dashes, spaces, and other formatting characters.
        Accepts any format and just removes formatting.
        """
        if not value or value == '':
            return None
        
        # Convert to string and trim whitespace
        phone_str = str(value).strip()
        
        # Remove common formatting characters: dashes, spaces, parentheses, dots
        phone_clean = re.sub(r'[-\s()\.]', '', phone_str)
        
        # If empty after cleaning, return None
        if not phone_clean:
            return None
        
        return phone_clean

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
