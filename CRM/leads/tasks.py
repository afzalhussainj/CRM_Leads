import re

from celery import Celery
from django.conf import settings
from django.core.cache import cache
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.db.models import Q
from django.template.loader import render_to_string

from common.models import Profile
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
    # send email to user with attachment
    if not from_email:
        from_email = settings.DEFAULT_FROM_EMAIL
    if not text_content:
        text_content = ""
    email = EmailMultiAlternatives(
        subject, text_content, from_email, recipients, bcc=bcc, cc=cc
    )
    email.attach_alternative(html_content, "text/html")
    for attachment in attachments:
        # Example: email.attach('design.png', img_data, 'image/png')
        email.attach(*attachment)
    email.send()


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
    """Send Mail To Users When they are assigned to a lead"""
    # Optimize: Use select_related
    lead = Lead.objects.select_related(
        'status', 'assigned_to', 'assigned_to__user'
    ).get(id=lead_id)
    created_by = lead.created_by
    for user in recipients:
        recipients_list = []
        # Optimize: Use select_related
        profile = Profile.objects.select_related('user').filter(
            id=user, 
            is_active=True,
            user__is_deleted=False
        ).first()
        if profile:
            recipients_list.append(profile.user.email)
            context = {}
            context["url"] = settings.DOMAIN_NAME
            context["user"] = profile.user
            context["lead"] = lead
            context["created_by"] = created_by
            context["source"] = source
            context["UserRole"] = UserRole
            subject = "Assigned a lead for you. "
            html_content = render_to_string(
                "assigned_to/leads_assigned.html", context=context
            )
            msg = EmailMessage(subject, html_content, to=recipients_list)
            msg.content_subtype = "html"
            msg.send()




@app.task
def update_leads_cache():
    queryset = (
        Lead.objects.all()
        .exclude(status="development phase")
        .select_related("created_by")
        .prefetch_related(
            "tags",
            "assigned_to",
        )
    )
    open_leads = queryset.exclude(status="closed")
    close_leads = queryset.filter(status="closed")
    cache.set("admin_leads_open_queryset", open_leads, 60 * 60)
    cache.set("admin_leads_close_queryset", close_leads, 60 * 60)
