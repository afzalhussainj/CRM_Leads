from django import forms
from leads.models import Lead, LeadNote
from CRM.utils.roles_enum import UserRole

email_regex = r"^[_a-zA-Z0-9-]+(\.[_a-zA-Z0-9-]+)*@[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)*(\.[a-zA-Z]{2,4})$"

class LeadCreateForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = [
            "title",
            "status",
            "source",
            "description",
            "follow_up_at",
            "follow_up_status",
            "assigned_to",
            "company_name",
            "contact_first_name",
            "contact_last_name",
            "contact_email",
            "contact_phone",
            "contact_position_title",
            "contact_linkedin_url",
        ]

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Set dynamic choices for status and source
        from common.utils import get_lead_status_choices, get_lead_source_choices
        
        # Set choices and widget type for status and source fields
        status_choices = [('', '---------')] + get_lead_status_choices()
        # Add "Add New" option for managers
        if request and hasattr(request, 'profile') and request.profile.role == UserRole.MANAGER.value:
            status_choices.append(('__add_new__', '+ Add New Status'))
        self.fields['status'].choices = status_choices
        self.fields['status'].widget = forms.Select(choices=status_choices, attrs={"class": "form-input"})
        
        source_choices = [('', '---------')] + get_lead_source_choices()
        # Add "Add New" option for managers
        if request and hasattr(request, 'profile') and request.profile.role == UserRole.MANAGER.value:
            source_choices.append(('__add_new__', '+ Add New Source'))
        self.fields['source'].choices = source_choices
        self.fields['source'].widget = forms.Select(choices=source_choices, attrs={"class": "form-input"})
        
        # Set up assigned_to field based on role and context
        if request and hasattr(request, 'profile'):
            from common.models import Profile
            
            # Check if this is an edit form (instance exists)
            is_edit = kwargs.get('instance') is not None
            
            if request.profile.role == UserRole.MANAGER.value:
                # Manager can assign to any employee OR to themselves during creation and editing
                employee_choices = Profile.objects.filter(
                    role='EMPLOYEE',
                    is_active=True
                ).values_list('id', 'user__first_name', 'user__email')
                
                # Create choices with name (or email if no name)
                choices = [('', '---------')]
                
                # Add manager's own profile as an option
                manager_profile = request.profile
                manager_display = manager_profile.user.first_name or manager_profile.user.email
                choices.append((manager_profile.id, f"{manager_display} (Me)"))
                
                # Add all employees
                for profile_id, first_name, email in employee_choices:
                    choices.append((profile_id))
                
                # If no employees exist, add a message
                if len(choices) == 2:  # Only has empty choice and manager
                    choices.append(('', 'No employees available'))
                
                self.fields['assigned_to'].choices = choices
                # Ensure the field is editable for managers
                self.fields['assigned_to'].widget = forms.Select(choices=choices, attrs={"class": "form-input"})
                # Ensure the field is not disabled
                self.fields['assigned_to'].disabled = False
                self.fields['assigned_to'].required = False
                # Hide assigned_developer field for managers
                self.fields['assigned_developer'].widget = forms.HiddenInput()
                self.fields['assigned_developer'].required = False
            elif request.profile.role == UserRole.EMPLOYEE.value:
                if is_edit:
                    # Employee can only reassign to manager during editing
                    manager_choices = Profile.objects.filter(
                        role='MANAGER',
                        is_active=True
                    ).values_list('id', 'user__first_name', 'user__email')
                    # Create choices with name (or email if no name)
                    choices = [('', '---------')]
                    for profile_id in manager_choices:
                        choices.append((profile_id))
                    self.fields['assigned_to'].choices = choices
                    self.fields['assigned_to'].widget = forms.Select(choices=self.fields['assigned_to'].choices, attrs={"class": "form-input"})
                else:
                    # Employee cannot assign during creation - will be auto-assigned
                    self.fields['assigned_to'].widget = forms.HiddenInput()
                    self.fields['assigned_to'].required = False
            else:
                # Other roles (DEVELOPMENT_LEAD) cannot assign
                self.fields['assigned_to'].widget = forms.HiddenInput()
                self.fields['assigned_to'].required = False
        
        for name, field in self.fields.items():
            placeholder_map = {
                "title": "Lead title",
                "company_name": "Company name",
                "contact_first_name": "First name",
                "contact_last_name": "Last name",
                "contact_email": "name@company.com",
                "contact_phone": "e.g. +1 555 123 4567",
                "contact_position_title": "Position title",
                "contact_linkedin_url": "https://www.linkedin.com/in/username",
                "description": "Notes about the lead, context, next steps...",
                "follow_up_at": "Select date & time",
                "assigned_developer": "Developer name (optional)",
            }
            attrs = {"class": "form-input"}
            if name in placeholder_map:
                attrs["placeholder"] = placeholder_map[name]
            if name == "follow_up_at":
                # Use text input and enhance with Flatpickr for a modern calendar/time picker
                self.fields[name].widget = forms.TextInput(
                    attrs={"type": "text", "class": "form-input", "placeholder": "YYYY-MM-DD HH:MM"},
                )
                # Accept common formats including flatpickr's default (12-hour with AM/PM)
                self.fields[name].input_formats = [
                    "%Y-%m-%d %I:%M %p",   # e.g., 2025-08-27 01:30 PM
                    "%Y-%m-%d %H:%M",      # 24-hour fallback
                    "%Y-%m-%dT%H:%M",
                    "%Y/%m/%d %H:%M",
                ]
                continue
            field.widget.attrs.update(attrs)


class LeadNoteForm(forms.ModelForm):
    """Form for creating lead notes/chat messages"""
    
    class Meta:
        model = LeadNote
        fields = ['message']
        widgets = {
            'message': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 4,
                'placeholder': 'Add your note or message here...'
            })
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
