import datetime
import socket

from celery import Celery, shared_task
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
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
        
        # Send via Django SMTP
        msg = EmailMultiAlternatives(
            subject,
            html_content,
            settings.DEFAULT_FROM_EMAIL,
            [user_email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()


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
        
        # Send via Django SMTP
        msg = EmailMultiAlternatives(
            subject,
            html_content,
            settings.DEFAULT_FROM_EMAIL,
            [user.email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()


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
        
        # Send via Django SMTP
        msg = EmailMultiAlternatives(
            subject,
            html_content,
            settings.DEFAULT_FROM_EMAIL,
            [user_email]
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send()


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
    
    # Send via Django SMTP
    msg = EmailMultiAlternatives(
        subject,
        html_content,
        settings.DEFAULT_FROM_EMAIL,
        [user_email]
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send()


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
        "user": user,
    }

    html_content = render_to_string("password_reset_email.html", context)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=html_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user_email],
    )
    msg.attach_alternative(html_content, "text/html")

    logger.info("Sending password reset email to %s", user_email)

    # 🔥 fail_silently=False is important
    msg.send(fail_silently=False)

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
    logger = logging.getLogger(__name__)

    logger.info("Celery task started for password reset email: %s", user_email)

    result = _send_email_to_reset_password_sync(user_email)

    if not result:
        raise Exception("Email sending returned False")

    logger.info("Celery task completed successfully for %s", user_email)
    return True
