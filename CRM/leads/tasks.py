import re

from celery import Celery
from django.conf import settings
from django.db.models import Q
from django.template.loader import render_to_string

from common.models import Profile
from common.utils.email_mailtrap import send_mailtrap_email
from leads.models import Lead
from utils.roles_enum import UserRole

app = Celery("redis://")


def get_rendered_html(template_name, context={}):
    html_content = render_to_string(template_name, context)
    return html_content


@app.task
def send_email(
    subject,
    html_content,
    text_content=None,
    from_email=None,
    recipients=[],
    attachments=[],
    bcc=[],
    cc=[],
):
    """Send email using Mailtrap API"""
    if not from_email:
        from_email = settings.DEFAULT_FROM_EMAIL
    
    send_mailtrap_email(
        subject=subject,
        recipients=recipients,
        html=html_content,
        text=text_content,
        from_email=from_email,
    )


@app.task
def send_lead_assigned_emails(lead_id, new_assigned_to_list, site_address):
    # Optimize: Use select_related
    lead_instance = Lead.objects.select_related(
        'status', 'assigned_to', 'assigned_to__user'
    ).filter(
        ~Q(status="development phase"), pk=lead_id, is_active=True
    ).first()
    if not (lead_instance and new_assigned_to_list):
        return False

    # Optimize: Use select_related
    users = Profile.objects.select_related('user').filter(
        id__in=new_assigned_to_list,
        user__is_deleted=False
    ).distinct()
    subject = "Lead '%s' has been assigned to you" % lead_instance
    from_email = settings.DEFAULT_FROM_EMAIL
    template_name = "leads/lead_assigned.html"

    url = site_address
    url += "/leads/" + str(lead_instance.id) + "/view/"

    context = {
        "lead_instance": lead_instance,
        "lead_detail_url": url,
        'UserRole': UserRole,
    }
    mail_kwargs = {"subject": subject, "from_email": from_email}
    for profile in users:
        if profile.user.email:
            context["user"] = profile.user
            html_content = get_rendered_html(template_name, context)
            mail_kwargs["html_content"] = html_content
            mail_kwargs["recipients"] = [profile.user.email]
            send_email.delay(**mail_kwargs)


@app.task
def send_email_to_assigned_user(recipients, lead_id, source=""):
    """Send email to users when leads are assigned to them."""
    # Optimize: Use select_related
    lead = Lead.objects.select_related(
        'status', 'assigned_to', 'assigned_to__user'
    ).get(id=lead_id)
    created_by = lead.created_by
    lead_detail_url = f"{settings.DOMAIN_NAME}/leads/{lead.id}/view/"
    for user in recipients:
        # Optimize: Use select_related
        profile = Profile.objects.select_related('user').filter(
            id=user, 
            is_active=True,
            user__is_deleted=False
        ).first()
        if profile and profile.user.email:
            context = {}
            context["user"] = profile.user
            context["lead_instance"] = lead
            context["lead_detail_url"] = lead_detail_url
            context["created_by"] = created_by
            context["source"] = source
            context["UserRole"] = UserRole
            subject = "Assigned a lead for you"
            html_content = render_to_string(
                "leads/lead_assigned.html", context=context
            )
            
            # Send via Mailtrap API
            send_mailtrap_email(
                subject=subject,
                recipients=[profile.user.email],
                html=html_content,
                text=None,
                from_email=settings.DEFAULT_FROM_EMAIL,
            )



