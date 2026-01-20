from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from utils.roles_enum import UserRole
import logging

logger = logging.getLogger(__name__)

def send_follow_up_reminder(lead, hours_before=2):
    """
    Send a follow-up reminder email to the assigned user.
    
    Args:
        lead: Lead instance with follow_up_at and assigned_to fields
        hours_before: Hours before follow-up time to send the reminder (default: 2)
    """
    try:
        # Check if lead has follow-up scheduled and is assigned
        if not lead.follow_up_at or not lead.assigned_to:
            logger.warning(f"Lead {lead.pk} has no follow-up time or assigned user")
            return False
        
        # Check if follow-up is in the future
        if lead.follow_up_at <= timezone.now():
            logger.warning(f"Lead {lead.pk} follow-up time has already passed")
            return False
        
        # Check if reminder should be sent now (2 hours before)
        reminder_time = lead.follow_up_at - timedelta(hours=hours_before)
        current_time = timezone.now()
        
        # Only send if we're within 1 hour of the reminder time
        if abs((reminder_time - current_time).total_seconds()) > 3600:  # 1 hour tolerance
            logger.debug(f"Lead {lead.pk} reminder not due yet. Reminder time: {reminder_time}, Current: {current_time}")
            return False
        
        # Get the assigned user's email
        user_email = lead.assigned_to.user.email
        if not user_email:
            logger.error(f"User {lead.assigned_to.user.username} has no email address")
            return False
        
        # Prepare email context
        # Use FRONTEND_URL for React app links
        frontend_url = getattr(settings, 'FRONTEND_URL', 'https://slcwcrm.vercel.app')
        context = {
            'lead': lead,
            'follow_up_time': lead.follow_up_at,
            'current_time': current_time,
            'hours_until': hours_before,
            'UserRole': UserRole,
            'frontend_url': frontend_url,
            'lead_detail_url': f"{frontend_url}/leads/{lead.pk}",
        }
        
        # Render email templates
        html_message = render_to_string('emails/follow_up_reminder.html', context)
        plain_message = render_to_string('emails/follow_up_reminder.txt', context)
        
        # Send email
        subject = f"🔔 Follow-up Reminder: {lead.title}"
        
        success = send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            html_message=html_message,
            fail_silently=False,
        )
        
        if success:
            logger.info(f"Follow-up reminder sent successfully to {user_email} for lead {lead.pk}")
            return True
        else:
            logger.error(f"Failed to send follow-up reminder to {user_email} for lead {lead.pk}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending follow-up reminder for lead {lead.pk}: {str(e)}")
        return False

def send_bulk_follow_up_reminders():
    """
    Send follow-up reminders for all leads that need them.
    This function should be called by a scheduled task (e.g., cron job).
    """
    from leads.models import Lead
    
    try:
        # Get leads with follow-ups scheduled in the next 2-3 hours
        now = timezone.now()
        reminder_start = now + timedelta(hours=1.5)  # 1.5 hours from now
        reminder_end = now + timedelta(hours=2.5)    # 2.5 hours from now
        
        # Optimize: Use select_related
        leads_to_remind = Lead.objects.select_related(
            'status', 'assigned_to', 'assigned_to__user'
        ).filter(
            follow_up_at__gte=reminder_start,
            follow_up_at__lte=reminder_end,
            follow_up_status='pending',
            assigned_to__isnull=False
        ).select_related('assigned_to__user')
        
        logger.info(f"Found {leads_to_remind.count()} leads needing follow-up reminders")
        
        success_count = 0
        for lead in leads_to_remind:
            if send_follow_up_reminder(lead):
                success_count += 1
        
        logger.info(f"Successfully sent {success_count} follow-up reminders out of {leads_to_remind.count()}")
        return success_count
        
    except Exception as e:
        logger.error(f"Error in bulk follow-up reminder process: {str(e)}")
        return 0
