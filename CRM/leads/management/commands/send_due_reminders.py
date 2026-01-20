from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import logging

from leads.models import Lead
from common.utils.email_mailtrap import send_mailtrap_email
from django.template.loader import render_to_string

# Setup logging
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Send due follow-up reminder emails (cron-friendly, no Celery)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=200,
            help="Max reminders to send per run (default 200)",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        now = timezone.now()
        
        # Log start
        self.stdout.write(self.style.WARNING(f"[{now.isoformat()}] Starting send_due_reminders command"))
        logger.info(f"[{now.isoformat()}] Starting send_due_reminders command with limit={limit}")

        # Offsets in minutes
        offsets = {
            "exact": 0,
            "30min": 30,
            "1hour": 60,
            "1day": 1440,
        }

        # Fetch leads that need reminders and have not been sent yet
        self.stdout.write("Querying leads with send_reminder_email=True, follow_up_at not null, and reminder_email_sent_at null...")
        leads = (
            Lead.objects.select_related("assigned_to", "assigned_to__user", "status", "lifecycle")
            .filter(
                send_reminder_email=True,
                follow_up_at__isnull=False,
                reminder_email_sent_at__isnull=True,
            )
            .order_by("follow_up_at")[:limit]
        )
        
        leads_count = leads.count()
        self.stdout.write(self.style.SUCCESS(f"Found {leads_count} leads to process"))
        logger.info(f"Found {leads_count} leads to process")

        sent_count = 0
        skipped_count = 0

        for index, lead in enumerate(leads, 1):
            self.stdout.write(f"\n[{index}/{leads_count}] Processing lead ID {lead.id}: {lead.title}")
            logger.info(f"[{index}/{leads_count}] Processing lead ID {lead.id}: {lead.title}")
            
            offset_minutes = offsets.get(lead.reminder_time_offset or "exact", 0)
            scheduled_at = lead.follow_up_at - timedelta(minutes=offset_minutes)
            
            self.stdout.write(f"  - Offset: {lead.reminder_time_offset} ({offset_minutes} minutes)")
            self.stdout.write(f"  - Follow-up at: {lead.follow_up_at.isoformat()}")
            self.stdout.write(f"  - Scheduled send time: {scheduled_at.isoformat()}")
            self.stdout.write(f"  - Current time: {now.isoformat()}")
            
            logger.info(f"  - Offset: {lead.reminder_time_offset} ({offset_minutes} minutes)")
            logger.info(f"  - Follow-up at: {lead.follow_up_at.isoformat()}")
            logger.info(f"  - Scheduled send time: {scheduled_at.isoformat()}")

            if scheduled_at > now:
                self.stdout.write(self.style.WARNING(f"  - SKIPPED: Send time is in future (scheduled: {scheduled_at.isoformat()}, now: {now.isoformat()})"))
                logger.info(f"  - SKIPPED: Send time is in future")
                skipped_count += 1
                continue

            # Safety: ensure assigned user email exists
            if not lead.assigned_to:
                self.stdout.write(self.style.WARNING(f"  - SKIPPED: No assigned_to profile"))
                logger.warning(f"  - SKIPPED: No assigned_to profile for lead ID {lead.id}")
                skipped_count += 1
                continue
            
            assigned_email = getattr(lead.assigned_to.user, "email", None)
            if not assigned_email:
                self.stdout.write(self.style.WARNING(f"  - SKIPPED: Assigned user has no email"))
                logger.warning(f"  - SKIPPED: Assigned user {lead.assigned_to.user.id} has no email")
                skipped_count += 1
                continue

            self.stdout.write(f"  - Assigned to: {lead.assigned_to.user.email}")
            logger.info(f"  - Assigned to: {lead.assigned_to.user.email}")

            lead_detail_url = f"/leads/{lead.id}/view/"
            from django.conf import settings
            domain = getattr(settings, "DOMAIN_NAME", "")
            if domain:
                lead_detail_url = f"{domain}/leads/{lead.id}/view/"

            self.stdout.write(f"  - Lead detail URL: {lead_detail_url}")

            context = {
                "user": lead.assigned_to.user,
                "lead_instance": lead,
                "lead_detail_url": lead_detail_url,
                "follow_up_at": lead.follow_up_at,
                "reminder_offset": dict(lead.REMINDER_TIME_CHOICES).get(lead.reminder_time_offset, "exact time"),
            }

            subject = f"Follow-up Reminder: {lead.title}"
            self.stdout.write(f"  - Subject: {subject}")
            logger.info(f"  - Subject: {subject}")
            
            try:
                html_content = render_to_string("emails/follow_up_reminder.html", context=context)
                self.stdout.write(f"  - Template rendered successfully ({len(html_content)} chars)")
                logger.info(f"  - Template rendered successfully ({len(html_content)} chars)")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  - FAILED: Template render error: {str(e)}"))
                logger.error(f"  - FAILED: Template render error: {str(e)}")
                skipped_count += 1
                continue

            # Send email via Mailtrap
            self.stdout.write(f"  - Sending email to {lead.assigned_to.user.email}...")
            logger.info(f"  - Sending email to {lead.assigned_to.user.email}...")
            
            try:
                result = send_mailtrap_email(
                    subject=subject,
                    recipients=[lead.assigned_to.user.email],
                    html=html_content,
                    text=None,
                    from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                )
                self.stdout.write(f"  - Email send result: {result}")
                logger.info(f"  - Email send result: {result}")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  - FAILED: Email send error: {str(e)}"))
                logger.error(f"  - FAILED: Email send error: {str(e)}")
                skipped_count += 1
                continue

            # Mark as sent
            try:
                lead.reminder_email_sent_at = now
                lead.save(update_fields=["reminder_email_sent_at"])
                self.stdout.write(self.style.SUCCESS(f"  - ✓ SENT: Email sent and reminder_email_sent_at updated"))
                logger.info(f"  - ✓ SENT: Email sent and reminder_email_sent_at updated")
                sent_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  - FAILED: Could not update reminder_email_sent_at: {str(e)}"))
                logger.error(f"  - FAILED: Could not update reminder_email_sent_at: {str(e)}")
                skipped_count += 1
                continue

        # Final summary
        summary = f"Reminders sent: {sent_count}, skipped: {skipped_count}"
        self.stdout.write(self.style.SUCCESS(f"\n[{timezone.now().isoformat()}] {summary}"))
        logger.info(f"[{timezone.now().isoformat()}] {summary}")
