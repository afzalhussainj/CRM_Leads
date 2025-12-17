import datetime

from celery import Celery
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from common.models import Profile, User
from common.utils.token_generator import account_activation_token
from utils.roles_enum import UserRole

app = Celery("redis://")


@app.task
def send_email_to_new_user(user_id):

    """Send Mail To Users When their account is created"""
    # No need for select_related (User has no foreign keys in this context)
    user_obj = User.objects.filter(id=user_id, is_deleted=False).first()

    if user_obj:
        context = {}
        user_email = user_obj.email
        context["url"] = settings.DOMAIN_NAME
        context["uid"] = (urlsafe_base64_encode(force_bytes(user_obj.pk)),)
        context["token"] = account_activation_token.make_token(user_obj)
        context["UserRole"] = UserRole
        time_delta_two_hours = datetime.datetime.strftime(
            timezone.now() + datetime.timedelta(hours=2), "%Y-%m-%d-%H-%M-%S"
        )
        # creating an activation token and saving it in user model
        activation_key = context["token"] + time_delta_two_hours
        user_obj.activation_key = activation_key
        user_obj.save()

        context["complete_url"] = context[
            "url"
        ] + "/auth/activate-user/{}/{}/{}/".format(
            context["uid"][0],
            context["token"],
            activation_key,
        )
        recipients = [
            user_email,
        ]
        subject = "Welcome to SLCW CRM"
        html_content = render_to_string("user_status_in.html", context=context)

        msg = EmailMessage(
            subject,
            html_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients,
        )
        msg.content_subtype = "html"
        msg.send()


@app.task
def send_email_user_status(
    user_id,
    status_changed_user="",
):
    """Send Mail To Users Regarding their status i.e active or inactive"""
    user = User.objects.filter(id=user_id).first()
    if user:
        context = {}
        context["message"] = "deactivated"
        context["email"] = user.email
        context["url"] = settings.DOMAIN_NAME
        context["UserRole"] = UserRole
        if user.is_active:
            context["message"] = "activated"
        context["status_changed_user"] = status_changed_user
        if context["message"] == "activated":
            subject = "Account Activated "
            html_content = render_to_string(
                "user_status_activate.html", context=context
            )
        else:
            subject = "Account Deactivated "
            html_content = render_to_string(
                "user_status_deactivate.html", context=context
            )
        recipients = []
        recipients.append(user.email)
        if recipients:
            msg = EmailMessage(
                subject,
                html_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=recipients,
            )
            msg.content_subtype = "html"
            msg.send()


@app.task
def send_email_user_delete(
    user_email,
    deleted_by="",
):
    """Send Mail To Users When their account is deleted"""
    if user_email:
        context = {}
        context["message"] = "deleted"
        context["deleted_by"] = deleted_by
        context["email"] = user_email
        context["UserRole"] = UserRole
        recipients = []
        recipients.append(user_email)
        subject = "CRM : Your account is Deleted. "
        html_content = render_to_string("user_delete_email.html", context=context)
        if recipients:
            msg = EmailMessage(
                subject,
                html_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=recipients,
            )
            msg.content_subtype = "html"
            msg.send()


@app.task
def resend_activation_link_to_user(
    user_email="",
):
    """Send Mail To Users When requested for resend activation link"""

    # No need for select_related (User has no foreign keys in this context)
    user_obj = User.objects.filter(email=user_email, is_deleted=False).first()
    user_obj.is_active = False
    user_obj.save()
    if user_obj:
        context = {}
        context["user_email"] = user_email
        context["UserRole"] = UserRole
        context["url"] = settings.DOMAIN_NAME
        context["uid"] = (urlsafe_base64_encode(force_bytes(user_obj.pk)),)
        context["token"] = account_activation_token.make_token(user_obj)
        time_delta_two_hours = datetime.datetime.strftime(
            timezone.now() + datetime.timedelta(hours=2), "%Y-%m-%d-%H-%M-%S"
        )
        context["token"] = context["token"]
        activation_key = context["token"] + time_delta_two_hours
        user_obj.activation_key = activation_key
        user_obj.key_expires = timezone.now() + datetime.timedelta(hours=2)
        user_obj.save()

        context["complete_url"] = context[
            "url"
        ] + "/auth/activate_user/{}/{}/{}/".format(
            context["uid"][0],
            context["token"],
            activation_key,
        )
        recipients = [context["complete_url"]]
        recipients.append(user_email)
        subject = "Welcome to SLCW CRM"
        html_content = render_to_string("user_status_in.html", context=context)
        if recipients:
            msg = EmailMessage(
                subject,
                html_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=recipients,
            )
            msg.content_subtype = "html"
            msg.send()


@app.task
def send_email_to_reset_password(user_email):
    """Send Mail To Users When they request password reset"""
    user = User.objects.filter(email=user_email, is_deleted=False).first()
    if not user:
        return
    
    context = {}
    context["user_email"] = user_email
    context["uid"] = urlsafe_base64_encode(force_bytes(user.pk))
    context["token"] = default_token_generator.make_token(user)
    context["UserRole"] = UserRole
    
    # Use FRONTEND_URL for the reset link (points to React frontend)
    frontend_url = getattr(settings, "FRONTEND_URL", "https://skycrm.vercel.app")
    context["complete_url"] = f"{frontend_url}/reset-password/{context['uid']}/{context['token']}/"
    
    subject = "Reset Your Password"
    recipients = [user_email]
    html_content = render_to_string(
        "registration/password_reset_email.html", context=context
    )
    if recipients:
        msg = EmailMessage(
            subject,
            html_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients
        )
        msg.content_subtype = "html"
        msg.send()
