import re

from celery import Celery
from django.conf import settings
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.db.models import Q
from django.template.loader import render_to_string

from common.models import Profile
from common.utils.email_resend import send_email_html
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
    """Send email using Resend API (attachments, bcc, cc not supported in simple version)"""
    if not from_email:
        from_email = settings.DEFAULT_FROM_EMAIL
    
    # Send to each recipient using Resend
    for recipient in recipients:
        send_email_html(subject, recipient, html_content, from_email=from_email)
    
    # Note: BCC and CC not directly supported in this simple Resend implementation
    # If needed, can send separately to bcc/cc recipients


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
    """Send Mail To Users When they are assigned to a lead - Using Resend"""
    # Optimize: Use select_related
    lead = Lead.objects.select_related(
        'status', 'assigned_to', 'assigned_to__user'
    ).get(id=lead_id)
    created_by = lead.created_by
    for user in recipients:
        # Optimize: Use select_related
        profile = Profile.objects.select_related('user').filter(
            id=user, 
            is_active=True,
            user__is_deleted=False
        ).first()
        if profile and profile.user.email:
            context = {}
            context["url"] = settings.DOMAIN_NAME
            context["user"] = profile.user
            context["lead"] = lead
            context["created_by"] = created_by
            context["source"] = source
            context["UserRole"] = UserRole
            subject = "Assigned a lead for you"
            html_content = render_to_string(
                "assigned_to/leads_assigned.html", context=context
            )
            
            # Send via Resend
            send_email_html(subject, profile.user.email, html_content)



