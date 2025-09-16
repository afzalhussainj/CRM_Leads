from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import render

from .models import Lead
from leads.utils.forms import LeadCreateForm, LeadNoteForm
from utils.roles_enum import UserRole

class LeadListUI(LoginRequiredMixin, ListView):
    model = Lead
    template_name = "ui/leads_list.html"
    context_object_name = "leads"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().order_by("-created_at")
        
        # Check if user is authenticated and has profile
        if not self.request.user.is_authenticated:
            return queryset.none()
        
        if not hasattr(self.request, 'profile') or self.request.profile is None:
            return queryset.none()
        
        # Role-based filtering
        if self.request.profile.role == UserRole.EMPLOYEE.value:
            # Employees can only see leads assigned to them
            queryset = queryset.filter(assigned_to=self.request.profile)
        elif self.request.profile.role == UserRole.DEV_LEAD.value:
            # Development leads can see all leads but only update status to 'closed'
            pass  # No filtering needed
        # Managers can see all leads
        
        # Search functionality
        q = self.request.GET.get("q")
        if q:
            queryset = queryset.filter(
                Q(title__icontains=q)
                | Q(company_name__icontains=q)
                | Q(contact_first_name__icontains=q)
                | Q(contact_last_name__icontains=q)
                | Q(contact_email__icontains=q)
                | Q(contact_phone__icontains=q)
            ).distinct()
        
        # Add current user to each lead for unread notes check
        for lead in queryset:
            lead._current_user = self.request.user
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["lead_status_choices"] = list(Lead._meta.get_field("status").choices or [])
        context["user_role"] = getattr(self.request, 'profile', None)
        context["UserRole"] = UserRole
        
        # Add available profiles for assignment dropdown
        if context["user_role"]:
            from common.models import Profile
            if context["user_role"].role == 'MANAGER':
                # Managers can assign to any employee OR to themselves
                available_profiles = Profile.objects.filter(
                    role='EMPLOYEE',
                    is_active=True
                )
                context["available_profiles"] = available_profiles
            elif context["user_role"].role == 'EMPLOYEE':
                # Employees can only assign to managers OR to themselves
                available_profiles = Profile.objects.filter(
                    role='MANAGER',
                    is_active=True
                )
                context["available_profiles"] = available_profiles
        
        return context


class LeadCreateUI(LoginRequiredMixin, CreateView):
    form_class = LeadCreateForm
    template_name = "ui/leads_new.html"
    success_url = reverse_lazy("ui-leads-list")

    def dispatch(self, request, *args, **kwargs):
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return redirect('/login/')
        
        # Check if user has a profile
        if not hasattr(request, 'profile') or request.profile is None:
            messages.error(request, "User profile not found. Please contact administrator.")
            return redirect('/login/')
        
        # Managers and employees can create leads
        if request.profile.role not in [UserRole.MANAGER.value, UserRole.EMPLOYEE.value]:
            raise PermissionDenied("Only managers and employees can create leads.")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['UserRole'] = UserRole
        return context

    def post(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        
        # Handle "Add New" options for status and source
        if request.profile.role == UserRole.MANAGER.value:
            status = request.POST.get('status')
            source = request.POST.get('source')
            
            # Handle new status
            if status == '__add_new__':
                new_status_name = request.POST.get('new_status_name', '').strip()
                if new_status_name:
                    from leads.models import LeadStatus
                    status_obj, created = LeadStatus.objects.get_or_create(name=new_status_name)
                    if created:
                        messages.success(request, f'New status "{new_status_name}" created successfully!')
                    # Update the form data to use the new status
                    form.data = form.data.copy()
                    form.data['status'] = status_obj.name
                else:
                    messages.error(request, 'Please enter a status name.')
                    return self.render_to_response(self.get_context_data(form=form))
            
            # Handle new source
            if source == '__add_new__':
                new_source_name = request.POST.get('new_source_name', '').strip()
                if new_source_name:
                    from leads.models import LeadSource
                    source_obj, created = LeadSource.objects.get_or_create(name=new_source_name)
                    if created:
                        messages.success(request, f'New source "{new_source_name}" created successfully!')
                    # Update the form data to use the new source
                    form.data = form.data.copy()
                    form.data['source'] = source_obj.name
                else:
                    messages.error(request, 'Please enter a source name.')
                    return self.render_to_response(self.get_context_data(form=form))
        
        forms_valid = form.is_valid()
        if not forms_valid:
            messages.error(request, "Please correct the errors and try again.")
            return self.render_to_response(self.get_context_data(form=form))

        # Create related records as needed, atomically
        with transaction.atomic():
            # Embedded snapshot already on form.instance via ModelForm
            self.object = form.save()

        messages.success(request, "Lead created successfully.")
        return redirect(self.get_success_url())



class LeadUpdateUI(LoginRequiredMixin, UpdateView):
    model = Lead
    form_class = LeadCreateForm
    template_name = "ui/leads_edit.html"
    success_url = reverse_lazy("ui-leads-list")

    def dispatch(self, request, *args, **kwargs):
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return redirect('/login/')
        
        # Check if user has a profile
        if not hasattr(request, 'profile') or request.profile is None:
            messages.error(request, "User profile not found. Please contact administrator.")
            return redirect('/login/')
        
        # Check permissions based on role
        lead = self.get_object()
        if request.profile.role == UserRole.EMPLOYEE.value:
            # Employees cannot edit leads - they can only update status and assignment through dropdowns
            raise PermissionDenied("Employees cannot edit leads. Use the inline dropdowns to update status and assignment.")
        elif request.profile.role == UserRole.DEV_LEAD.value:
            # Development leads cannot edit leads - they can only update status to 'closed' through dropdown
            raise PermissionDenied("Development leads cannot edit leads. Use the status dropdown to update status.")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs


class LeadDeleteUI(LoginRequiredMixin, DeleteView):
    model = Lead
    template_name = "ui/lead_confirm_delete.html"
    success_url = reverse_lazy("ui-leads-list")

    def dispatch(self, request, *args, **kwargs):
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return redirect('/login/')
        
        # Check if user has a profile
        if not hasattr(request, 'profile') or request.profile is None:
            messages.error(request, "User profile not found. Please contact administrator.")
            return redirect('/login/')
        
        # Only managers can delete leads
        if request.profile.role != UserRole.MANAGER.value:
            raise PermissionDenied("Only managers can delete leads.")
        return super().dispatch(request, *args, **kwargs)


class LeadFollowUpStatusUpdateUI(LoginRequiredMixin, View):
    def post(self, request, pk):
        # Check permissions
        if not hasattr(request, 'profile'):
            return JsonResponse({"ok": False, "error": "unauthorized"}, status=403)
        
        lead = get_object_or_404(Lead, pk=pk)
        
        # Check if user can update this lead
        if request.profile.role == UserRole.EMPLOYEE.value and lead.assigned_to != request.profile:
            return JsonResponse({"ok": False, "error": "unauthorized"}, status=403)
        
        status_value = request.POST.get("status")
        valid_statuses = dict(Lead.FOLLOW_UP_STATUS_CHOICES)
        if status_value not in valid_statuses:
            return JsonResponse({"ok": False, "error": "invalid_status"}, status=400)
        
        lead.follow_up_status = status_value
        lead.save(update_fields=["follow_up_status"])
        return JsonResponse({"ok": True, "status": status_value, "label": valid_statuses[status_value]})


class LeadStatusUpdateUI(LoginRequiredMixin, View):
    def post(self, request, pk):
        # Check permissions
        if not hasattr(request, 'profile'):
            return JsonResponse({"ok": False, "error": "unauthorized"}, status=403)
        
        lead = get_object_or_404(Lead, pk=pk)
        
        # Check if user can update this lead
        if request.profile.role == UserRole.EMPLOYEE.value and lead.assigned_to != request.profile:
            return JsonResponse({"ok": False, "error": "unauthorized"}, status=403)
        
        status_value = request.POST.get("status")
        
        # Role-based status restrictions
        if request.profile.role == UserRole.DEV_LEAD.value and status_value != 'closed':
            return JsonResponse({"ok": False, "error": "development_lead_can_only_close"}, status=400)
        
        from common.utils import get_lead_status_choices
        choices = dict(get_lead_status_choices())
        if status_value not in choices:
            return JsonResponse({"ok": False, "error": "invalid_status"}, status=400)
        
        lead.status = status_value
        lead.save(update_fields=["status"])
        return JsonResponse({"ok": True, "status": status_value, "label": choices[status_value]})


class LeadDetailUI(LoginRequiredMixin, DetailView):
    model = Lead
    template_name = "ui/lead_detail.html"
    context_object_name = "lead"

    def dispatch(self, request, *args, **kwargs):
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return redirect('/login/')
        
        # Check if user has a profile
        if not hasattr(request, 'profile') or request.profile is None:
            messages.error(request, "User profile not found. Please contact administrator.")
            return redirect('/login/')
        
        # Check permissions
        lead = self.get_object()
        if request.profile.role == UserRole.EMPLOYEE.value and lead.assigned_to != request.profile:
            raise PermissionDenied("You can only view leads assigned to you.")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['UserRole'] = UserRole
        context["notes"] = self.object.notes.all()
        context["note_form"] = LeadNoteForm()
        context["user_role"] = getattr(self.request, 'profile', None)
        return context


class LeadNotesView(LoginRequiredMixin, View):
    """View for handling lead notes/chat functionality"""
    
    def dispatch(self, request, *args, **kwargs):
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)
        
        # Check if user has a profile
        if not hasattr(request, 'profile') or request.profile is None:
            return JsonResponse({"error": "profile_not_found"}, status=403)
        
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk)
        
        # Check permissions - allow all roles to view notes, but employees can only see notes for their assigned leads
        if request.profile.role == UserRole.EMPLOYEE.value and lead.assigned_to != request.profile:
            return JsonResponse({"error": "unauthorized"}, status=403)
        
        notes = lead.notes.all()
        
        # Mark notes as read for this user (only if they weren't the author)
        from leads.models import LeadNoteRead
        for note in notes:
            # Only mark as read if the current user is not the author
            if note.author != request.profile:
                LeadNoteRead.objects.get_or_create(
                    note=note,
                    user=request.user
                )
        
        return JsonResponse({
            "notes": [
                {
                    "id": note.id,
                    "message": note.message,
                    "author_name": note.author.user.first_name or note.author.user.email,
                    "created_at": note.created_at.isoformat(),
                    "created_on_arrow": note.created_on_arrow
                }
                for note in notes
            ]
        })
    
    def post(self, request, pk):
        lead = get_object_or_404(Lead, pk=pk)
        
        # Check permissions - allow all roles to add notes, but employees can only add notes to their assigned leads
        if request.profile.role == UserRole.EMPLOYEE.value and lead.assigned_to != request.profile:
            return JsonResponse({"success": False, "error": "unauthorized"}, status=403)
        
        form = LeadNoteForm(request.POST)
        if form.is_valid():
            note = form.save(commit=False)
            note.lead = lead
            note.author = request.profile
            note.save()
            
            return JsonResponse({
                "success": True,
                "note": {
                    "id": note.id,
                    "message": note.message,
                    "author_name": note.author.user.first_name or note.author.user.email,
                    "created_at": note.created_at.isoformat(),
                    "created_on_arrow": note.created_on_arrow
                }
            })
        else:
            return JsonResponse({"success": False, "errors": form.errors}, status=400)


class RemindersView(LoginRequiredMixin, View):
    """Trello-like reminders view for employees and managers"""
    template_name = 'ui/reminders.html'
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/login/')
        
        if not hasattr(request, 'profile') or request.profile is None:
            messages.error(request, "User profile not found. Please contact administrator.")
            return redirect('/login/')
        
        # Only employees and managers can access reminders
        if request.profile.role not in [UserRole.EMPLOYEE.value, UserRole.MANAGER.value]:
            raise PermissionDenied("Only employees and managers can access reminders.")
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request):
        now = timezone.now()
        
        if request.profile.role == UserRole.EMPLOYEE.value:
            # Get leads assigned to this employee
            assigned_leads = Lead.objects.filter(assigned_to=request.profile)
        else:  # MANAGER
            # Get leads assigned to the manager
            assigned_leads = Lead.objects.filter(assigned_to=request.profile)
        
        # Past reminders: passed date, still pending
        past_reminders = assigned_leads.filter(
            follow_up_at__lt=now,
            follow_up_status='pending'
        ).order_by('follow_up_at')
        
        # Done reminders: status is done (only show if manager updated them)
        if request.profile.role == UserRole.EMPLOYEE.value:
            done_reminders = assigned_leads.filter(
                follow_up_status='done'
            ).order_by('-follow_up_at')
        else:  # MANAGER
            # For managers, show done reminders that they marked as done
            done_reminders = assigned_leads.filter(
                follow_up_status='done'
            ).order_by('-follow_up_at')
        
        # Upcoming reminders: future date, still pending
        upcoming_reminders = assigned_leads.filter(
            follow_up_at__gt=now,
            follow_up_status='pending'
        ).order_by('follow_up_at')
        
        context = {
            'past_reminders': past_reminders,
            'done_reminders': done_reminders,
            'upcoming_reminders': upcoming_reminders,
            'user_role': request.profile,
            'UserRole': UserRole,
        }
        
        return render(request, self.template_name, context)


class LeadAssignmentUpdateUI(LoginRequiredMixin, View):
    """View for handling inline lead assignment updates"""
    
    def post(self, request, pk):
        # Check permissions
        if not hasattr(request, 'profile'):
            return JsonResponse({"success": False, "error": "unauthorized"}, status=403)
        
        lead = get_object_or_404(Lead, pk=pk)
        
        # Only managers can reassign leads
        if request.profile.role != UserRole.MANAGER.value:
            return JsonResponse({"success": False, "error": "only_managers_can_reassign"}, status=403)
        
        assigned_to_id = request.POST.get("assigned_to")
        
        if assigned_to_id:
            try:
                # Get the profile to assign to
                from common.models import Profile
                assigned_profile = Profile.objects.get(
                    id=assigned_to_id,
                    is_active=True
                )
                lead.assigned_to = assigned_profile
            except Profile.DoesNotExist:
                return JsonResponse({"success": False, "error": "invalid_profile"}, status=400)
        else:
            # Unassign the lead
            lead.assigned_to = None
        
        lead.save(update_fields=["assigned_to"])
        
        return JsonResponse({
            "success": True, 
            "assigned_to": assigned_to_id,
            "assigned_to_name": lead.assigned_to.user.first_name if lead.assigned_to else "Unassigned"
        })

