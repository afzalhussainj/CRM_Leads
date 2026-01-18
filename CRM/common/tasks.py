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
from common.utils.email_mailtrap import send_mailtrap_email
from utils.roles_enum import UserRole

app = Celery("redis://")


@app.task
def send_password_set_email_to_new_employee(user_id):
    """Send password set email to newly created employees."""
    import logging
    logger = logging.getLogger(__name__)
    
    user_obj = User.objects.filter(id=user_id, is_deleted=False).first()
    if not user_obj:
        logger.warning("User not found for id %s", user_id)
        return False
    
    logger.info("Preparing password set email for %s", user_obj.email)
    
    # Generate password reset token (same flow as password reset)
    uid = urlsafe_base64_encode(force_bytes(user_obj.pk))
    token = default_token_generator.make_token(user_obj)
    
    frontend_url = settings.FRONTEND_URL
    reset_link = f"{frontend_url}/reset-password/{uid}/{token}/"
    
    user_name = f"{user_obj.first_name} {user_obj.last_name}".strip()
    subject = "Set Your Password - SLCW CRM Account"
    context = {
        "reset_link": reset_link,
        "user_name": user_name or user_obj.email,
    }
    
    html_content = render_to_string("password_reset_email.html", context)
    
    logger.info("Sending password set email to %s", user_obj.email)
    
    send_mailtrap_email(
        subject=subject,
        recipients=[user_obj.email],
        html=html_content,
        text=None,
        from_email=settings.DEFAULT_FROM_EMAIL,
    )
    
    logger.info("Password set email sent successfully to %s", user_obj.email)
    return True


@app.task
def send_email_user_status(
    user_id,
    status_changed_user="",
):
    """Send status change email (activated/deactivated) to users."""
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
        
        # Send via Mailtrap API
        send_mailtrap_email(
            subject=subject,
            recipients=[user.email],
            html=html_content,
            text=None,
            from_email=settings.DEFAULT_FROM_EMAIL,
        )


@app.task
def send_email_user_delete(
    user_email,
    deleted_by="",
):
    """Send account deletion notification email to users."""
    if user_email:
        context = {}
        context["message"] = "deleted"
        context["deleted_by"] = deleted_by
        context["email"] = user_email
        context["UserRole"] = UserRole
        
        subject = "CRM: Your account has been deleted"
        html_content = render_to_string("user_delete_email.html", context=context)
        
        # Send via Mailtrap API
        send_mailtrap_email(
            subject=subject,
            recipients=[user_email],
            html=html_content,
            text=None,
            from_email=settings.DEFAULT_FROM_EMAIL,
        )


@app.task
def resend_activation_link_to_user(
    user_email="",
):
    """Send activation link when user requests to resend."""
    user_obj = User.objects.filter(email=user_email, is_deleted=False).first()
    if not user_obj:
        return False
        
    user_obj.is_active = False
    user_obj.save()
    
    context = {}
    context["email"] = user_email
    context["user_email"] = user_email
    context["UserRole"] = UserRole
    context["url"] = settings.DOMAIN_NAME
    context["uid"] = urlsafe_base64_encode(force_bytes(user_obj.pk))
    context["token"] = account_activation_token.make_token(user_obj)
    context["message"] = "activation_link"
    user_name = f"{user_obj.first_name} {user_obj.last_name}".strip()
    context["user_name"] = user_name or user_email
    time_delta_two_hours = datetime.datetime.strftime(
        timezone.now() + datetime.timedelta(hours=2), "%Y-%m-%d-%H-%M-%S"
    )
    activation_key = context["token"] + time_delta_two_hours
    user_obj.activation_key = activation_key
    user_obj.key_expires = timezone.now() + datetime.timedelta(hours=2)
    user_obj.save()

    context["complete_url"] = context[
        "url"
    ] + "/auth/activate_user/{}/{}/{}/".format(
        context["uid"],
        context["token"],
        activation_key,
    )

    subject = "Your SLCW CRM activation link"
    html_content = render_to_string("user_status_activate.html", context=context)

    # Send via Mailtrap API
    send_mailtrap_email(
        subject=subject,
        recipients=[user_email],
        html=html_content,
        text=None,
        from_email=settings.DEFAULT_FROM_EMAIL,
    )


def _send_email_to_reset_password_sync(user_email):
    """Send password reset email using Django SMTP"""
    import logging
    logger = logging.getLogger(__name__)

    logger.info("Preparing password reset email for %s", user_email)

    user = User.objects.filter(email=user_email, is_deleted=False).first()
    if not user:
        logger.warning("User not found for email %s", user_email)
        return False

    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    frontend_url = settings.FRONTEND_URL
    reset_link = f"{frontend_url}/reset-password/{uid}/{token}/"

    subject = "Password Reset Request"
    context = {
        "reset_link": reset_link,
        "user_name": f"{user.first_name} {user.last_name}",
    }

    html_content = render_to_string("password_reset_email.html", context)

    logger.info("Sending password reset email to %s", user_email)

    send_mailtrap_email(
        subject=subject,
        recipients=[user_email],
        html=html_content,
        text=None,
        from_email=settings.DEFAULT_FROM_EMAIL,
    )

    logger.info("Password reset email sent successfully to %s", user_email)
    return True

# Celery task for password reset email
@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
    retry_backoff=True,
)
def send_email_to_reset_password(self, user_email):
    import logging
    from django.conf import settings

    logger = logging.getLogger(__name__)

    logger.info("Celery task started for password reset email: %s", user_email)

    result = _send_email_to_reset_password_sync(user_email)

    if not result:
        raise Exception("Email sending returned False")

    logger.info("Celery task completed successfully for %s", user_email)
    return True
