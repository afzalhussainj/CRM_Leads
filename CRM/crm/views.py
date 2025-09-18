from multiprocessing import context
from django.views.generic import TemplateView
from django.db.models import Q, Count, Min
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
import datetime
import json

from leads.models import Lead, LeadNote
from utils.roles_enum import UserRole


class SiteAdminView(LoginRequiredMixin, TemplateView):
    template_name = "site_admin.html"
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/login/')
        # Check if user has a profile
        if not hasattr(request, 'profile') or request.user.profile is None:
            return redirect('/login/')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ROLE_EMPLOYEE_VALUE"] = UserRole.EMPLOYEE.value
        context["ROLE_DEV_LEAD_VALUE"] = UserRole.DEV_LEAD.value

        # Get user profile and role
        user_profile = self.request.user.profile
        user_role = user_profile.role
        
        # Role-based data filtering
        if user_role == UserRole.MANAGER.value:
            # Manager sees all data
            base_leads_queryset = Lead.objects.all()
            my_leads_queryset = Lead.objects.filter(assigned_to=user_profile)
            team_leads_queryset = Lead.objects.filter(assigned_to__isnull=False)
            unassigned_leads_queryset = Lead.objects.filter(assigned_to__isnull=True)
            
            # Total leads for manager
            context["total_leads"] = base_leads_queryset.count()
            context["my_leads_count"] = my_leads_queryset.count()
            context["assigned_leads_count"] = team_leads_queryset.count()
            context["unassigned_leads_count"] = unassigned_leads_queryset.count()
            
            # Companies and contacts (all)
            context["companies_count"] = base_leads_queryset.exclude(company_name="").values("company_name").distinct().count()
            context["contacts_count"] = base_leads_queryset.exclude(contact_email="").values("contact_email").distinct().count()
            
        elif user_role == 'EMPLOYEE':
            # Employee sees only their assigned leads
            base_leads_queryset = Lead.objects.filter(assigned_to=user_profile)
            my_leads_queryset = base_leads_queryset
            
            # Only show employee's data
            context["total_leads"] = base_leads_queryset.count()
            context["my_leads_count"] = base_leads_queryset.count()
            context["my_pending_leads"] = base_leads_queryset.filter(follow_up_status='pending').count()
            
            # Companies and contacts (only from employee's leads)
            context["companies_count"] = base_leads_queryset.exclude(company_name="").values("company_name").distinct().count()
            context["contacts_count"] = base_leads_queryset.exclude(contact_email="").values("contact_email").distinct().count()
            
        elif user_role == 'DEVELOPMENT_LEAD':
            # Development lead sees leads in development phase
            base_leads_queryset = Lead.objects.filter(status='development')
            my_leads_queryset = base_leads_queryset
            
            # Only show development leads
            context["total_leads"] = base_leads_queryset.count()
            context["my_leads_count"] = base_leads_queryset.count()
            
            # Companies and contacts (only from development leads)
            context["companies_count"] = base_leads_queryset.exclude(company_name="").values("company_name").distinct().count()
            context["contacts_count"] = base_leads_queryset.exclude(contact_email="").values("contact_email").distinct().count()
        
        
        # Follow-up status breakdown (role-based)
        follow_up_counts = {
            'pending': base_leads_queryset.filter(follow_up_status='pending').count(),
            'done': base_leads_queryset.filter(follow_up_status='done').count(),
        }
        context["follow_up_counts"] = follow_up_counts
        
        # Open leads count (role-based)
        context["open_leads_count"] = base_leads_queryset.filter(follow_up_status="pending").count()

        # Upcoming reminders (role-based)
        context["upcoming_reminders"] = (
            base_leads_queryset.filter(follow_up_at__isnull=False, follow_up_status="pending")
            .order_by("follow_up_at")[:5]
        )

        # Recent activity: combine recent created items (role-based)
        recent_leads = list(base_leads_queryset.order_by("-created_at").values("created_at", "title")[:10])

        activity = []
        for l in recent_leads:
            activity.append({
                "when": l["created_at"],
                "item": f"Lead • {l.get('title')}",
                "action": "Created",
                "owner": "—",
            })
        activity.sort(key=lambda x: x["when"], reverse=True)
        context["recent_activity"] = activity[:5]

        # Unread notes - only show notes sent TO the current user (not BY the current user)
        from leads.models import LeadNoteRead
        read_note_ids = LeadNoteRead.objects.filter(
            user=self.request.user
        ).values_list('note_id', flat=True)
        
        # Get notes that are NOT sent by the current user (i.e., sent TO the current user)
        # and that the current user hasn't read yet
        unread_notes = LeadNote.objects.select_related('lead', 'author__user').exclude(
            author=self.request.user.profile  # Exclude notes sent BY the current user
        ).exclude(
            id__in=read_note_ids  # Exclude notes already read by the current user
        ).order_by('-created_at')[:10]
        context["recent_notes"] = unread_notes

        # Search results (role-based)
        q = self.request.GET.get("q", "").strip()
        context["q"] = q
        context["search_companies"] = []
        context["search_contacts"] = []
        context["search_leads"] = []
        if q:
            context["search_leads"] = base_leads_queryset.filter(
                Q(title__icontains=q)
                | Q(company_name__icontains=q)
                | Q(contact_first_name__icontains=q)
                | Q(contact_last_name__icontains=q)
                | Q(contact_email__icontains=q)
            )[:10]

        # Leads over time (role-based)
        today = timezone.now().date()
        agg = base_leads_queryset.aggregate(first=Min("created_at"))
        first_created_dt = agg.get("first")
        first_created_date = None
        if first_created_dt is not None:
            try:
                first_created_date = first_created_dt.date()
            except Exception:
                first_created_date = None
        if first_created_date is None:
            first_created_date = today
        start_date = first_created_date - datetime.timedelta(days=1)
        # Safety cap to avoid huge ranges
        if (today - start_date).days > 120:
            start_date = today - datetime.timedelta(days=120)

        daily_counts = (
            base_leads_queryset.filter(created_at__date__gte=start_date)
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(count=Count("id"))
            .order_by("day")
        )
        day_to_count = {row["day"]: row["count"] for row in daily_counts}
        labels = []
        counts = []
        num_days = (today - start_date).days + 1
        for i in range(num_days):
            d = start_date + datetime.timedelta(days=i)
            labels.append(d.strftime("%b %d"))
            counts.append(day_to_count.get(d, 0))
        context["leads_over_time_labels_json"] = json.dumps(labels)
        context["leads_over_time_counts_json"] = json.dumps(counts)

        print("Context in SiteAdminView:", context)  # Debug print statement

        return context


