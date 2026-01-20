from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from leads.models import Lead
from common.utils.email_mailtrap import send_mailtrap_email
from django.template.loader import render_to_string


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

        # Offsets in minutes
        offsets = {
            "exact": 0,
            "30min": 30,
            "1hour": 60,
            "1day": 1440,
        }

        # Fetch leads that need reminders and have not been sent yet
        leads = (
            Lead.objects.select_related("assigned_to", "assigned_to__user", "status", "lifecycle")
            .filter(
                send_reminder_email=True,
                follow_up_at__isnull=False,
                reminder_email_sent_at__isnull=True,
            )
            .order_by("follow_up_at")[:limit]
        )

        sent_count = 0
        skipped_count = 0

        for lead in leads:
            offset_minutes = offsets.get(lead.reminder_time_offset or "exact", 0)
            scheduled_at = lead.follow_up_at - timedelta(minutes=offset_minutes)

            if scheduled_at > now:
                skipped_count += 1
                continue

            # Safety: ensure assigned user email exists
            if not lead.assigned_to or not getattr(lead.assigned_to.user, "email", None):
                skipped_count += 1
                continue

            lead_detail_url = f"/leads/{lead.id}/view/"
            from django.conf import settings
            domain = getattr(settings, "DOMAIN_NAME", "")
            if domain:
                lead_detail_url = f"{domain}/leads/{lead.id}/view/"

            context = {
                "user": lead.assigned_to.user,
                "lead_instance": lead,
                "lead_detail_url": lead_detail_url,
                "follow_up_at": lead.follow_up_at,
                "reminder_offset": dict(lead.REMINDER_TIME_CHOICES).get(lead.reminder_time_offset, "exact time"),
            }

            subject = f"Follow-up Reminder: {lead.title}"
            html_content = render_to_string("emails/follow_up_reminder.html", context=context)

            # Send email via Mailtrap
            send_mailtrap_email(
                subject=subject,
                recipients=[lead.assigned_to.user.email],
                html=html_content,
                text=None,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            )

            # Mark as sent
            lead.reminder_email_sent_at = now
            lead.save(update_fields=["reminder_email_sent_at"])
            sent_count += 1

        self.stdout.write(self.style.SUCCESS(f"Reminders sent: {sent_count}, skipped: {skipped_count}"))
