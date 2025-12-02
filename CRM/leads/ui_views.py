from multiprocessing import context
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import render
import csv

from .models import Lead, LeadNote
from leads.utils.forms import LeadCreateForm, LeadNoteForm
from utils.roles_enum import UserRole

class LeadListUI(LoginRequiredMixin, ListView):
    model = Lead
    template_name = "ui/leads_list.html"
    context_object_name = "leads"
    paginate_by = 20

    def get_queryset(self):
        queryset = super().get_queryset().order_by("-created_at")
        
        # Exclude projects from leads list
        queryset = queryset.filter(is_project=False)
        
        # Check if user is authenticated and has profile
        if not self.request.user.is_authenticated:
            return queryset.none()

        if not hasattr(self.request.user, 'profile') or self.request.user.profile is None:
            return queryset.none()
        
        # Role-based filtering
        if int(self.request.user.profile.role) == UserRole.EMPLOYEE.value:
            queryset = queryset.filter(assigned_to=self.request.user.profile)
        elif int(self.request.user.profile.role) == UserRole.DEV_LEAD.value:
            pass
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
        
        # Optimize queries: prefetch related objects to avoid N+1 queries
        from django.db.models import Prefetch
        queryset = queryset.select_related(
            'status',
            'assigned_to',
            'assigned_to__user'
        ).prefetch_related(
            Prefetch(
                'notes',
                queryset=LeadNote.objects.select_related('author', 'author__user').prefetch_related('read_by'),
                to_attr='_prefetched_notes'
            )
        )
        
        # Add current user to each lead for unread notes check
        for lead in queryset:
            lead._current_user = self.request.user
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get dynamic status choices from LeadStatus model
        from leads.utils.choices import get_lead_status_choices
        context["lead_status_choices"] = get_lead_status_choices()
        context["user_profile"] = getattr(self.request.user, 'profile', None)

        
        # Add available profiles for assignment dropdown based on user role
        if context["user_profile"]:
            from common.models import Profile
            user_role_value = int(context["user_profile"].role)
            
            if user_role_value == UserRole.MANAGER.value:
                available_profiles = Profile.objects.select_related('user').filter(
                    role=UserRole.EMPLOYEE.value,
                    is_active=True,
                    user__is_deleted=False
                ).order_by('user__first_name', 'user__email')
                context["available_profiles"] = available_profiles
            elif user_role_value == UserRole.EMPLOYEE.value:
                available_profiles = Profile.objects.select_related('user').filter(
                    role=UserRole.MANAGER.value,
                    is_active=True,
                    user__is_deleted=False
                ).order_by('user__first_name', 'user__email')
                context["available_profiles"] = available_profiles
            else:
                # Developers and other roles don't get assignment options
                context["available_profiles"] = Profile.objects.none()
        
        # Column customization
        context["available_columns"] = self.get_available_columns()
        context["visible_columns"] = self.get_visible_columns()
        
        return context
    
    def get_available_columns(self):
        """Get all available columns for customization"""
        return {
            'title': 'Lead Title',
            'linkedin': 'LinkedIn',
            'status': 'Status',
            'assigned_to': 'Assigned To',
            'follow_up_at': 'Follow-up At',
            'follow_up_status': 'Follow-up Status',
            'company_name': 'Company',
            'contact_name': 'Contact Name',
            'contact_email': 'Contact Email',
            'contact_phone': 'Contact Phone',
            'source': 'Source',
            'description': 'Description',
            'created_at': 'Created Date',
            'always_active': 'Always Active',
            'priority': 'Priority',
        }
    
    def get_visible_columns(self):
        """Get currently visible columns from session or default"""
        # Get from session or use defaults
        visible_columns = self.request.session.get('leads_visible_columns', [
            'title', 'linkedin', 'status', 'assigned_to', 'follow_up_at', 'follow_up_status'
        ])
        
        # Ensure we have at least the title column
        if 'title' not in visible_columns:
            visible_columns.insert(0, 'title')
            
        return visible_columns


class LeadColumnCustomizationView(LoginRequiredMixin, View):
    """View for handling column customization updates"""
    
    def post(self, request):
        """Update visible columns based on user selection"""
        selected_columns = request.POST.getlist('columns')
        
        # Validate that at least title is selected
        if 'title' not in selected_columns:
            selected_columns.insert(0, 'title')
        
        # Save to session
        request.session['leads_visible_columns'] = selected_columns
        
        return JsonResponse({
            'success': True,
            'message': 'Column preferences updated successfully'
        })


class LeadCreateUI(LoginRequiredMixin, CreateView):
    form_class = LeadCreateForm
    template_name = "ui/leads_new.html"
    success_url = reverse_lazy("ui-leads-list")

    def dispatch(self, request, *args, **kwargs):
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return redirect('/login/')
        
        # Check if user has a profile
        if not hasattr(request.user, 'profile') or request.user.profile is None:
            messages.error(request, "User profile not found. Please contact administrator.")
            return redirect('/login/')
        
        # Managers and employees can create leads
        if int(request.user.profile.role) not in [UserRole.MANAGER.value, UserRole.EMPLOYEE.value]:
            raise PermissionDenied("Only managers and employees can create leads.")
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context

    def post(self, request, *args, **kwargs):
        self.object = None
        form = self.get_form()
        
        
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
        if not hasattr(request.user, 'profile') or request.user.profile is None:
            messages.error(request, "User profile not found. Please contact administrator.")
            return redirect('/login/')
        if int(request.user.profile.role) == UserRole.EMPLOYEE.value:
            # Employees cannot edit leads - they can only update status and assignment through dropdowns
            raise PermissionDenied("Employees cannot edit leads. Use the inline dropdowns to update status and assignment.")
        
        lead = self.get_object()
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
        if not hasattr(request.user, 'profile') or request.user.profile is None:
            messages.error(request, "User profile not found. Please contact administrator.")
            return redirect('/login/')
        
        # Only managers can delete leads
        if int(request.user.profile.role) != UserRole.MANAGER.value:
            raise PermissionDenied("Only managers can delete leads.")
        return super().dispatch(request, *args, **kwargs)


class LeadFollowUpStatusUpdateUI(LoginRequiredMixin, View):
    def post(self, request, pk):
        # Check permissions
        if not hasattr(request.user, 'profile'):
            return JsonResponse({"ok": False, "error": "unauthorized"}, status=403)
        
        # Optimize: Use select_related
        lead = get_object_or_404(
            Lead.objects.select_related('status', 'assigned_to', 'assigned_to__user'),
            pk=pk
        )
        
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
        if not hasattr(request.user, 'profile'):
            return JsonResponse({"ok": False, "error": "unauthorized"}, status=403)
        
        # Optimize: Use select_related
        lead = get_object_or_404(
            Lead.objects.select_related('status', 'assigned_to', 'assigned_to__user'),
            pk=pk
        )
        
        # Check if user can update this lead
        if int(request.user.profile.role) == UserRole.EMPLOYEE.value and lead.assigned_to != request.user.profile:
            return JsonResponse({"ok": False, "error": "unauthorized"}, status=403)
        
        status_value = request.POST.get("status")
        
        # Role-based status restrictions
        if int(request.user.profile.role) == UserRole.DEV_LEAD.value and status_value != 'closed':
            return JsonResponse({"ok": False, "error": "development_lead_can_only_close"}, status=400)
        
        # Get the LeadStatus object by name
        from common.models import LeadStatus
        try:
            status_obj = LeadStatus.objects.get(name=status_value)
        except LeadStatus.DoesNotExist:
            return JsonResponse({"ok": False, "error": "invalid_status"}, status=400)
        
        lead.status = status_obj
        lead.save(update_fields=["status"])
        return JsonResponse({"ok": True, "status": status_value, "label": status_obj.name})


class LeadDetailUI(LoginRequiredMixin, DetailView):
    model = Lead
    template_name = "ui/lead_detail.html"
    context_object_name = "lead"

    def dispatch(self, request, *args, **kwargs):
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return redirect('/login/')
        
        # Check if user has a profile
        if not hasattr(request.user, 'profile') or request.user.profile is None:
            messages.error(request, "User profile not found. Please contact administrator.")
            return redirect('/login/')
        
        # Check permissions
        lead = self.get_object()
        if int(request.user.profile.role) == UserRole.EMPLOYEE.value and lead.assigned_to != request.user.profile:
            raise PermissionDenied("You can only view leads assigned to you.")
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        # Optimize queryset with select_related and prefetch_related
        return super().get_queryset().select_related(
            'status',
            'assigned_to',
            'assigned_to__user'
        ).prefetch_related(
            'notes__author',
            'notes__author__user',
            'notes__read_by'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Use prefetched notes to avoid additional queries
        context["notes"] = self.object.notes.select_related('author', 'author__user').all()
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
        if not hasattr(request.user, 'profile') or request.user.profile is None:
            return JsonResponse({"error": "profile_not_found"}, status=403)
        
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request, pk):
        # Optimize queryset with select_related
        lead = get_object_or_404(
            Lead.objects.select_related('assigned_to', 'assigned_to__user'),
            pk=pk
        )
        
        # Check permissions - allow all roles to view notes, but employees can only see notes for their assigned leads
        if int(request.user.profile.role) == UserRole.EMPLOYEE.value and lead.assigned_to != request.user.profile:
            return JsonResponse({"error": "unauthorized"}, status=403)
        
        # Use prefetch_related to avoid N+1 queries
        notes = lead.notes.select_related('author', 'author__user').prefetch_related('read_by').all()
        
        # Mark notes as read for this user (only if they weren't the author)
        from leads.models import LeadNoteRead
        from django.db.models import Q
        # Bulk create read records for unread notes
        unread_notes = [note for note in notes if note.author != request.user.profile]
        if unread_notes:
            existing_reads = set(
                LeadNoteRead.objects.filter(
                    note__in=unread_notes,
                    user=request.user
                ).values_list('note_id', flat=True)
            )
            new_reads = [
                LeadNoteRead(note=note, user=request.user)
                for note in unread_notes
                if note.id not in existing_reads
            ]
            if new_reads:
                LeadNoteRead.objects.bulk_create(new_reads, ignore_conflicts=True)
        
        # Order notes by created_at (oldest first, so newest appear at bottom)
        notes_list = list(notes.order_by('created_at'))
        
        return JsonResponse({
            "notes": [
                {
                    "id": note.id,
                    "message": note.message,
                    "author_name": (note.author.user.first_name + ' ' + note.author.user.last_name).strip() or note.author.user.email,
                    "created_at": note.created_at.isoformat(),
                    "created_on_arrow": note.created_on_arrow
                }
                for note in notes_list
            ]
        })
    
    def post(self, request, pk):
        # Optimize: Use select_related
        lead = get_object_or_404(
            Lead.objects.select_related('status', 'assigned_to', 'assigned_to__user'),
            pk=pk
        )
        
        # Check permissions - allow all roles to add notes, but employees can only add notes to their assigned leads
        if int(request.user.profile.role) == UserRole.EMPLOYEE.value and lead.assigned_to != request.user.profile:
            return JsonResponse({"success": False, "error": "unauthorized"}, status=403)
        
        form = LeadNoteForm(request.POST)
        if form.is_valid():
            note = form.save(commit=False)
            note.lead = lead
            note.author = request.user.profile
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
        
        if not hasattr(request.user, 'profile') or request.user.profile is None:
            messages.error(request, "User profile not found. Please contact administrator.")
            return redirect('/login/')
        
        # Only employees and managers can access reminders
        if int(request.user.profile.role) not in [UserRole.EMPLOYEE.value, UserRole.MANAGER.value]:
            raise PermissionDenied("Only employees and managers can access reminders.")
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request):
        from datetime import datetime, timedelta
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
        tomorrow_start = today_start + timedelta(days=1)
        
        # Optimize queryset with select_related
        # Exclude projects and only get leads with follow_up_at set
        base_queryset = Lead.objects.select_related(
            'status', 'assigned_to', 'assigned_to__user'
        ).filter(
            is_project=False,
            follow_up_at__isnull=False
        )
        
        if int(request.user.profile.role) == UserRole.EMPLOYEE.value:
            # Get leads assigned to this employee
            assigned_leads = base_queryset.filter(assigned_to=request.user.profile)
        else:  # MANAGER
            # Managers see all assigned leads (not just their own)
            assigned_leads = base_queryset.filter(assigned_to__isnull=False)
        
        # Pending reminders: yesterday and before, still pending
        pending_reminders = assigned_leads.filter(
            follow_up_at__lt=today_start,
            follow_up_status='pending'
        ).order_by('follow_up_at')
        
        # Due today reminders: today's date, still pending
        due_today_reminders = assigned_leads.filter(
            follow_up_at__gte=today_start,
            follow_up_at__lte=today_end,
            follow_up_status='pending'
        ).order_by('follow_up_at')
        
        # Upcoming reminders: tomorrow and after, still pending
        upcoming_reminders = assigned_leads.filter(
            follow_up_at__gte=tomorrow_start,
            follow_up_status='pending'
        ).order_by('follow_up_at')
        
        # Done reminders: status is done
        done_reminders = assigned_leads.filter(
            follow_up_status='done'
        ).order_by('-follow_up_at')
        
        # Convert querysets to lists to ensure they're evaluated properly
        context = {
            'pending_reminders': list(pending_reminders),
            'due_today_reminders': list(due_today_reminders),
            'upcoming_reminders': list(upcoming_reminders),
            'done_reminders': list(done_reminders),
            'user_role': request.user.profile,
            'UserRole': UserRole,
        }
        
        return render(request, self.template_name, context)


class LeadAssignmentUpdateUI(LoginRequiredMixin, View):
    """View for handling inline lead assignment updates"""
    
    def post(self, request, pk):
        # Check permissions
        if not hasattr(request.user, 'profile'):
            return JsonResponse({"success": False, "error": "unauthorized"}, status=403)
        
        # Optimize: Use select_related
        lead = get_object_or_404(
            Lead.objects.select_related('status', 'assigned_to', 'assigned_to__user'),
            pk=pk
        )
        
        # Check if user has permission to reassign
        user_role = int(request.user.profile.role)
        if user_role not in [UserRole.MANAGER.value, UserRole.EMPLOYEE.value]:
            return JsonResponse({"success": False, "error": "insufficient_permissions"}, status=403)
        
        assigned_to_id = request.POST.get("assigned_to")
        
        if assigned_to_id:
            try:
                # Get the profile to assign to - optimize with select_related
                from common.models import Profile
                assigned_profile = Profile.objects.select_related('user').get(
                    id=assigned_to_id,
                    is_active=True,
                    user__is_deleted=False
                )
                
                # Additional validation, managers can assign to anyone while employees can only reassign to managers
                if user_role == UserRole.EMPLOYEE.value:
                    if int(assigned_profile.role) != UserRole.MANAGER.value:
                        return JsonResponse({"success": False, "error": "employees_can_only_reassign_to_managers"}, status=403)
                elif user_role == UserRole.MANAGER.value:
                    pass
                
                lead.assigned_to = assigned_profile
                lead.save()
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


class LeadCSVExportView(LoginRequiredMixin, View):
    """View for exporting leads to CSV - managers only"""
    
    def dispatch(self, request, *args, **kwargs):
        # Check if user is a manager
        if not hasattr(request.user, 'profile') or int(request.user.profile.role) != UserRole.MANAGER.value:
            raise PermissionDenied("Only managers can export leads")
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request):
        """Export leads to CSV"""
        
        # Get all leads (managers can see all, excluding projects) - optimize with select_related
        leads = Lead.objects.select_related(
            'status',
            'assigned_to',
            'assigned_to__user'
        ).filter(is_project=False).order_by('-created_at')
        
        # Apply search filter if provided
        search_query = request.GET.get('q', '').strip()
        if search_query:
            leads = leads.filter(
                Q(title__icontains=search_query)
                | Q(company_name__icontains=search_query)
                | Q(contact_first_name__icontains=search_query)
                | Q(contact_last_name__icontains=search_query)
                | Q(contact_email__icontains=search_query)
            )
        
        # Create CSV response
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="leads_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
        
        writer = csv.writer(response)
        
        # Write headers based on all available columns
        headers = [field.name for field in Lead._meta.get_fields() if not field.auto_created]
        writer.writerow(headers)
        headers = [field for field in Lead._meta.get_fields() if not field.auto_created]
        

        for lead in leads:
            row = []
            for field in headers:                 
                value = getattr(lead, field.name) or None
                if value is None:
                    value = "NULL" 
                row.append(value)

                # if field.concrete:
                #     row.append(getattr(lead, field.name) or '')
                #     print('concrete')
                # elif field.is_relation and not field.many_to_many:
                #     related_obj = getattr(lead, field.name, None)
                #     if related_obj:
                #         if hasattr(related_obj, "first_name"):
                #             value = related_obj.name
                #         elif hasattr(related_obj, "email"):
                #             value = related_obj.email
                #         else:
                #             value = str(related_obj)
                #     print('not concrete')
                #     row.append(value)
            
            writer.writerow(row)

        return response


class LeadToggleAlwaysActiveView(LoginRequiredMixin, View):
    """View for toggling always_active status of a lead - managers only"""
    
    def dispatch(self, request, *args, **kwargs):
        # Check if user is a manager
        if not hasattr(request.user, 'profile') or int(request.user.profile.role) != UserRole.MANAGER.value:
            raise PermissionDenied("Only managers can toggle always active status")
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, pk):
        """Toggle always_active status of a lead"""
        try:
            # Optimize: Use select_related
            lead = get_object_or_404(
                Lead.objects.select_related('status', 'assigned_to', 'assigned_to__user'),
                pk=pk
            )
            lead.always_active = not lead.always_active
            lead.save(update_fields=['always_active'])
            
            return JsonResponse({
                'success': True,
                'always_active': lead.always_active,
                'message': f'Lead {"marked as" if lead.always_active else "removed from"} always active'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)


class LeadTogglePriorityView(LoginRequiredMixin, View):
    """View for toggling priority status of a lead - managers only"""
    
    def dispatch(self, request, *args, **kwargs):
        # Check if user is a manager
        if not hasattr(request.user, 'profile') or int(request.user.profile.role) != UserRole.MANAGER.value:
            raise PermissionDenied("Only managers can toggle priority status")
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, pk):
        """Toggle priority status of a lead"""
        try:
            # Optimize: Use select_related
            lead = get_object_or_404(
                Lead.objects.select_related('status', 'assigned_to', 'assigned_to__user'),
                pk=pk
            )
            lead.priority = not lead.priority
            lead.save(update_fields=['priority'])
            
            return JsonResponse({
                'success': True,
                'priority': lead.priority,
                'message': f'Lead {"marked as" if lead.priority else "removed from"} priority'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)


class LeadToggleProjectView(LoginRequiredMixin, View):
    """Toggle project status for a lead"""
    
    def dispatch(self, request, *args, **kwargs):
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return JsonResponse({"error": "unauthorized"}, status=401)
        
        # Check if user has a profile
        if not hasattr(request.user, 'profile') or request.user.profile is None:
            return JsonResponse({"error": "profile_not_found"}, status=403)
        
        # Only managers can toggle project status
        if int(request.user.profile.role) != UserRole.MANAGER.value:
            return JsonResponse({"error": "permission_denied"}, status=403)
        
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, pk):
        """Toggle is_project status of a lead"""
        try:
            # Optimize: Use select_related
            lead = get_object_or_404(
                Lead.objects.select_related('status', 'assigned_to', 'assigned_to__user'),
                pk=pk
            )
            old_status = lead.is_project
            lead.is_project = not lead.is_project
            lead.save(update_fields=['is_project'])
            
            return JsonResponse({
                'success': True,
                'is_project': lead.is_project,
                'old_status': old_status,
                'message': f'Lead {"converted to" if lead.is_project else "converted back from"} project'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)


class ProjectsListView(LoginRequiredMixin, ListView):
    """View for listing all projects"""
    model = Lead
    template_name = "ui/projects_list.html"
    context_object_name = "projects"
    paginate_by = 20
    
    def dispatch(self, request, *args, **kwargs):
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return redirect('/login/')
        
        # Check if user has a profile
        if not hasattr(request.user, 'profile') or request.user.profile is None:
            messages.error(request, "User profile not found. Please contact administrator.")
            return redirect('/login/')
        
        # Only managers can view projects
        if int(request.user.profile.role) != UserRole.MANAGER.value:
            raise PermissionDenied("Only managers can view projects")
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        """Get all projects (leads with is_project=True) with search functionality"""
        queryset = Lead.objects.filter(is_project=True).order_by('-created_at')
        
        # Apply search filter if provided
        search_query = self.request.GET.get('q', '').strip()
        if search_query:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(title__icontains=search_query)
                | Q(company_name__icontains=search_query)
                | Q(contact_first_name__icontains=search_query)
                | Q(contact_last_name__icontains=search_query)
                | Q(contact_email__icontains=search_query)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["total_projects"] = Lead.objects.filter(is_project=True).count()
        context["available_columns"] = self.get_available_columns()
        context["visible_columns"] = self.get_visible_columns()
        return context
    
    def get_available_columns(self):
        """Get available columns for projects (excluding restricted ones)"""
        return {
            'title': 'Project Title',
            'linkedin': 'LinkedIn',
            'company_name': 'Company',
            'contact_name': 'Contact Name',
            'contact_email': 'Contact Email',
            'contact_phone': 'Contact Phone',
            'source': 'Source',
            'description': 'Description',
            'created_at': 'Created Date',
            'is_project': 'Project Status',
            'priority': 'Priority',
        }
    
    def get_visible_columns(self):
        """Get currently visible columns from session or default"""
        # Get from session or use defaults
        visible_columns = self.request.session.get('projects_visible_columns', [
            'title', 'company_name', 'contact_name', 'contact_email', 'created_at'
        ])
        
        # Ensure all visible columns are valid
        available_columns = self.get_available_columns()
        return [col for col in visible_columns if col in available_columns]


class ProjectsColumnCustomizationView(LoginRequiredMixin, View):
    """View for customizing project columns"""
    
    def dispatch(self, request, *args, **kwargs):
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return redirect('/login/')
        
        # Check if user has a profile
        if not hasattr(request.user, 'profile') or request.user.profile is None:
            messages.error(request, "User profile not found. Please contact administrator.")
            return redirect('/login/')
        
        # Only managers can customize project columns
        if int(request.user.profile.role) != UserRole.MANAGER.value:
            raise PermissionDenied("Only managers can customize project columns")
        
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request):
        """Show column customization form"""
        available_columns = {
            'title': 'Project Title',
            'linkedin': 'LinkedIn',
            'company_name': 'Company',
            'contact_name': 'Contact Name',
            'contact_email': 'Contact Email',
            'contact_phone': 'Contact Phone',
            'source': 'Source',
            'description': 'Description',
            'created_at': 'Created Date',
            'is_project': 'Project Status',
        }
        
        visible_columns = request.session.get('projects_visible_columns', [
            'title', 'company_name', 'contact_name', 'contact_email', 'created_at'
        ])
        
        context = {
            'available_columns': available_columns,
            'visible_columns': visible_columns,
        }
        return render(request, 'ui/projects_column_customization.html', context)
    
    def post(self, request):
        """Save column customization"""
        selected_columns = request.POST.getlist('columns')
        
        # Validate selected columns
        available_columns = {
            'title': 'Project Title',
            'linkedin': 'LinkedIn',
            'company_name': 'Company',
            'contact_name': 'Contact Name',
            'contact_email': 'Contact Email',
            'contact_phone': 'Contact Phone',
            'source': 'Source',
            'description': 'Description',
            'created_at': 'Created Date',
            'is_project': 'Project Status',
        }
        
        # Filter to only include valid columns
        valid_columns = [col for col in selected_columns if col in available_columns]
        
        # Save to session
        request.session['projects_visible_columns'] = valid_columns
        
        messages.success(request, 'Project columns updated successfully!')
        return redirect('ui-projects')


