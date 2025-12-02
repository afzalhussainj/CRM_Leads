from multiprocessing import context
from django.views.generic import TemplateView
from django.db.models import Q, Count, Min
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
import datetime
import json

from leads.models import Lead
from utils.roles_enum import UserRole


class SiteAdminView(LoginRequiredMixin, TemplateView):
    template_name = "site_admin.html"
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/login/')
        # Check if user has a profile
        if not hasattr(request.user, 'profile') or request.user.profile is None:
            return redirect('/login/')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["ROLE_EMPLOYEE_VALUE"] = UserRole.EMPLOYEE.value
        context["ROLE_DEV_LEAD_VALUE"] = UserRole.DEV_LEAD.value

        # Get user profile and role
        user_profile = self.request.user.profile
        user_role = user_profile.role
        
        # Initialize base_leads_queryset for all roles
        base_leads_queryset = Lead.objects.none()
        
        # Role-based data filtering
        if user_role == UserRole.MANAGER.value:
            # Manager sees all data (excluding projects)
            # Optimize: Use select_related and single aggregation query
            base_leads_queryset = Lead.objects.select_related(
                'status', 'assigned_to', 'assigned_to__user'
            ).filter(is_project=False)
            
            # Optimize: Use single aggregation query instead of multiple count queries
            from django.db.models import Count, Q
            counts = base_leads_queryset.aggregate(
                total=Count('id'),
                my_leads=Count('id', filter=Q(assigned_to=user_profile)),
                assigned=Count('id', filter=Q(assigned_to__isnull=False)),
                unassigned=Count('id', filter=Q(assigned_to__isnull=True))
            )
            
            context["total_leads"] = counts['total'] or 0
            context["my_leads_count"] = counts['my_leads'] or 0
            context["assigned_leads_count"] = counts['assigned'] or 0
            context["unassigned_leads_count"] = counts['unassigned'] or 0
            
            # Always active leads for managers (excluding projects)
            always_active_leads = base_leads_queryset.filter(always_active=True).order_by('-created_at')[:10]
            context["always_active_leads"] = always_active_leads
            
            # Projects for managers
            projects = Lead.objects.select_related(
                'status', 'assigned_to', 'assigned_to__user'
            ).filter(is_project=True).order_by('-created_at')[:10]
            context["projects"] = projects
            
            # Companies and contacts (all) - optimize with single query
            company_contact_counts = base_leads_queryset.aggregate(
                companies=Count('company_name', filter=~Q(company_name=""), distinct=True),
                contacts=Count('contact_email', filter=~Q(contact_email=""), distinct=True)
            )
            context["companies_count"] = company_contact_counts['companies'] or 0
            context["contacts_count"] = company_contact_counts['contacts'] or 0
            
        elif user_role == 'EMPLOYEE':
            # Employee sees only their assigned leads (excluding projects)
            base_leads_queryset = Lead.objects.select_related(
                'status', 'assigned_to', 'assigned_to__user'
            ).filter(assigned_to=user_profile, is_project=False)
            my_leads_queryset = base_leads_queryset
            
            # Optimize: Use single aggregation query
            from django.db.models import Count, Q
            counts = base_leads_queryset.aggregate(
                total=Count('id'),
                pending=Count('id', filter=Q(follow_up_status='pending')),
                companies=Count('company_name', filter=~Q(company_name=""), distinct=True),
                contacts=Count('contact_email', filter=~Q(contact_email=""), distinct=True)
            )
            
            context["total_leads"] = counts['total'] or 0
            context["my_leads_count"] = counts['total'] or 0
            context["my_pending_leads"] = counts['pending'] or 0
            context["companies_count"] = counts['companies'] or 0
            context["contacts_count"] = counts['contacts'] or 0
            
        elif user_role == 'DEVELOPMENT_LEAD':
            # Development lead sees leads in development phase (excluding projects)
            base_leads_queryset = Lead.objects.select_related(
                'status', 'assigned_to', 'assigned_to__user'
            ).filter(status='development', is_project=False)
            my_leads_queryset = base_leads_queryset
            
            # Optimize: Use single aggregation query
            from django.db.models import Count, Q
            counts = base_leads_queryset.aggregate(
                total=Count('id'),
                companies=Count('company_name', filter=~Q(company_name=""), distinct=True),
                contacts=Count('contact_email', filter=~Q(contact_email=""), distinct=True)
            )
            
            context["total_leads"] = counts['total'] or 0
            context["my_leads_count"] = counts['total'] or 0
            context["companies_count"] = counts['companies'] or 0
            context["contacts_count"] = counts['contacts'] or 0
        
        else:
            # Default case for any other roles - no leads
            context["total_leads"] = 0
            context["my_leads_count"] = 0
            context["companies_count"] = 0
            context["contacts_count"] = 0
        
        # Follow-up status breakdown (role-based) - optimize with aggregation
        from django.db.models import Count, Q
        follow_up_counts_agg = base_leads_queryset.aggregate(
            pending=Count('id', filter=Q(follow_up_status='pending')),
            done=Count('id', filter=Q(follow_up_status='done'))
        )
        follow_up_counts = {
            'pending': follow_up_counts_agg['pending'] or 0,
            'done': follow_up_counts_agg['done'] or 0,
        }
        context["follow_up_counts"] = follow_up_counts
        
        # Open leads count (role-based) - reuse from aggregation
        context["open_leads_count"] = follow_up_counts['pending']

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


        # Search results (role-based) - optimize with select_related
        q = self.request.GET.get("q", "").strip()
        context["q"] = q
        context["search_companies"] = []
        context["search_contacts"] = []
        context["search_leads"] = []
        if q:
            context["search_leads"] = base_leads_queryset.select_related(
                'status', 'assigned_to', 'assigned_to__user'
            ).filter(
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


