import datetime
import socket

from celery import Celery, shared_task
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from common.models import Profile, User
from common.utils.token_generator import account_activation_token
from common.utils.email_resend import send_reset_email, send_email_html
from utils.roles_enum import UserRole

app = Celery("redis://")


@app.task
def send_email_to_new_user(user_id):
    """Send Mail To Users When their account is created - Using Resend"""
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
        
        subject = "Welcome to SLCW CRM"
        html_content = render_to_string("common/user_status_activate.html", context=context)
        
        # Send via Resend
        send_email_html(subject, user_email, html_content)


@app.task
def send_email_user_status(
    user_id,
    status_changed_user="",
):
    """Send Mail To Users Regarding their status i.e active or inactive - Using Resend"""
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
            subject = "Account Activated"
            html_content = render_to_string(
                "user_status_activate.html", context=context
            )
        else:
            subject = "Account Deactivated"
            html_content = render_to_string(
                "user_status_deactivate.html", context=context
            )
        
        # Send via Resend
        send_email_html(subject, user.email, html_content)


@app.task
def send_email_user_delete(
    user_email,
    deleted_by="",
):
    """Send Mail To Users When their account is deleted - Using Resend"""
    if user_email:
        context = {}
        context["message"] = "deleted"
        context["deleted_by"] = deleted_by
        context["email"] = user_email
        context["UserRole"] = UserRole
        
        subject = "CRM: Your account has been deleted"
        html_content = render_to_string("user_delete_email.html", context=context)
        
        # Send via Resend
        send_email_html(subject, user_email, html_content)


@app.task
def resend_activation_link_to_user(
    user_email="",
):
    """Send Mail To Users When requested for resend activation link - Using Resend"""
    user_obj = User.objects.filter(email=user_email, is_deleted=False).first()
    if not user_obj:
        return False
        
    user_obj.is_active = False
    user_obj.save()
    
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
    
    subject = "Welcome to SLCW CRM - Activation Link"
    html_content = render_to_string("common/user_status_activate.html", context=context)
    
    # Send via Resend
    send_email_html(subject, user_email, html_content)


def _send_email_to_reset_password_sync(user_email):
    """Send Mail To Users When they request password reset (synchronous) - Using Resend"""
    user = User.objects.filter(email=user_email, is_deleted=False).first()
    if not user:
        return False
    
    # Generate reset token
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    
    # Use FRONTEND_URL for the reset link (points to React frontend)
    frontend_url = getattr(settings, "FRONTEND_URL")
    reset_link = f"{frontend_url}/reset-password/{uid}/{token}/"
    
    # Send email using Resend
    try:
        result = send_reset_email(user_email, reset_link)
        return result
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send password reset email via Resend: {str(e)}")
        return False

# Celery task for password reset email
@shared_task(bind=True, max_retries=3)
def send_email_to_reset_password(self, user_email):
    """Celery task for password reset email (async) - Uses Resend API"""
    try:
        result = _send_email_to_reset_password_sync(user_email)
        if not result:
            # Retry if email sending failed
            raise Exception("Email sending failed")
        return result
    except Exception as exc:
        # Retry after 60 seconds
        raise self.retry(exc=exc, countdown=60, max_retries=3)
