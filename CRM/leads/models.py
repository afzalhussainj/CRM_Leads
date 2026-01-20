import arrow
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy

from common.models import Profile, LeadStatus, LeadLifecycle
from common.base import BaseModel 

class Lead(BaseModel):
    title = models.CharField(
        pgettext_lazy("Treatment Pronouns for the customer", "Title"), max_length=64
    )
    status = models.ForeignKey(
        LeadStatus, 
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    lifecycle = models.ForeignKey(
        LeadLifecycle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Lead lifecycle stage"
    )
    source = models.CharField(
        _("Source of Lead"), max_length=255, blank=True, null=True
    )
    description = models.TextField(blank=True, null=True)
    # Follow-up reminder fields
    follow_up_at = models.DateTimeField(null=True, blank=True)
    FOLLOW_UP_STATUS_CHOICES = (
        ("pending", "Pending"),
        ("done", "Done"),
    )
    follow_up_status = models.CharField(
        max_length=16,
        choices=FOLLOW_UP_STATUS_CHOICES,
        null=True,
        blank=True
    )
    # Follow-up reminder notification settings
    send_reminder_email = models.BooleanField(default=False)
    REMINDER_TIME_CHOICES = (
        ("exact", "At exact time"),
        ("30min", "30 minutes before"),
        ("1hour", "1 hour before"),
        ("1day", "1 day before"),
    )
    reminder_time_offset = models.CharField(
        max_length=10,
        choices=REMINDER_TIME_CHOICES,
        default="exact",
        blank=True,
        null=True
    )
    is_active = models.BooleanField(default=False)
    always_active = models.BooleanField(default=False)
    priority = models.BooleanField(default=False)
    is_project = models.BooleanField(default=False)
    company_name = models.CharField(max_length=255, blank=True, default="")
    contact_first_name = models.CharField(max_length=255, blank=True, default="")
    contact_last_name = models.CharField(max_length=255, blank=True, default="")
    contact_email = models.EmailField(blank=True, default="")
    contact_phone = models.CharField(max_length=255, blank=True, null=True)
    contact_position_title = models.CharField(max_length=255, blank=True, default="")
    contact_linkedin_url = models.URLField(blank=True, default="")
    # Workflow assignment fields
    assigned_to = models.ForeignKey(
        Profile, 
        on_delete=models.PROTECT, 
        related_name="assigned_leads",
        help_text="Employee assigned to work on this lead"
    )
    class Meta:
        verbose_name = "Lead"
        verbose_name_plural = "Leads"
        db_table = "lead"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=['is_project', 'is_active']),
            models.Index(fields=['follow_up_status', 'follow_up_at']),
            models.Index(fields=['assigned_to', 'is_active']),
            models.Index(fields=['created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['is_project', 'created_at']),
        ]

    def __str__(self):
        return f"{self.title}"



    @property
    def created_on_arrow(self):
        return arrow.get(self.created_at).humanize()

    @property
    def get_team_users(self):
        return Profile.objects.none()

    def get_status_display(self):
        """Get the display name for the status"""
        from leads.utils.choices import get_lead_status_choices
        choices = dict(get_lead_status_choices())
        return choices.get(self.status, self.status)

    def get_source_display(self):
        """Get the display name for the source"""
        from leads.utils.choices import get_lead_source_choices
        choices = dict(get_lead_source_choices())
        return choices.get(self.source, self.source)
    
    @property
    def has_unread_notes(self):
        """Check if lead has unread notes for the current user (notes sent TO them, not BY them)"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Try to get current user from queryset or instance
        current_user = None
        if hasattr(self, '_current_user'):
            current_user = self._current_user
        elif hasattr(self, '_state') and hasattr(self._state, 'db') and hasattr(self, '_prefetched_objects_cache'):
            # Try to get from queryset if available
            queryset = getattr(self, '_queryset', None)
            if queryset and hasattr(queryset, '_current_user'):
                current_user = queryset._current_user
        
        if not current_user:
            # If no user context, just check if notes exist
            return self.notes.exists()
        
        # Get the current user's profile - optimize with select_related if not prefetched
        try:
            # Check if profile was prefetched
            if hasattr(current_user, 'profile'):
                current_profile = current_user.profile
            else:
                current_profile = Profile.objects.select_related('user').get(user=current_user)
        except Profile.DoesNotExist:
            return False
        
        # Use prefetched notes if available to avoid additional queries
        if hasattr(self, '_prefetched_notes'):
            # Filter notes sent to user (not by user)
            notes_sent_to_user = [n for n in self._prefetched_notes if n.author != current_profile]
            
            # Check if any note hasn't been read by current user
            # read_by is prefetched, so we can check it efficiently
            for note in notes_sent_to_user:
                # Check if note has read_by prefetched
                if hasattr(note, 'read_by'):
                    # Check if current user is in the read_by list
                    user_has_read = any(
                        read.user_id == current_user.id 
                        for read in note.read_by.all()
                    )
                    if not user_has_read:
                        return True
                else:
                    # Note exists but no read records, so it's unread
                    return True
            return False
        else:
            # Fallback: use database query (less efficient but works)
            notes_sent_to_user = self.notes.exclude(author=current_profile)
            read_notes = LeadNoteRead.objects.filter(
                note__lead=self,
                note__in=notes_sent_to_user,
                user=current_user
            ).values_list('note_id', flat=True)
            
            total_notes_sent_to_user = notes_sent_to_user.values_list('id', flat=True)
            return len(total_notes_sent_to_user) > len(read_notes)


class LeadNote(BaseModel):
    """Model for lead notes/chat functionality"""
    lead = models.ForeignKey(
        Lead, 
        on_delete=models.CASCADE, 
        related_name="notes"
    )
    author = models.ForeignKey(
        Profile, 
        on_delete=models.CASCADE,
        related_name="lead_notes"
    )
    message = models.TextField()
    
    class Meta:
        verbose_name = "Lead Note"
        verbose_name_plural = "Lead Notes"
        db_table = "lead_notes"
        ordering = ("created_at",)  # Show oldest first (bottom) to newest last (top)
        indexes = [
            models.Index(fields=['lead', 'created_at']),
            models.Index(fields=['author', 'created_at']),
        ]
    
    def __str__(self):
        return self.message
    
    @property
    def created_on_arrow(self):
        return arrow.get(self.created_at).humanize()


class LeadNoteRead(BaseModel):
    """Model to track which notes each user has read"""
    note = models.ForeignKey(
        LeadNote,
        on_delete=models.CASCADE,
        related_name="read_by"
    )
    user = models.ForeignKey(
        'common.User',
        on_delete=models.CASCADE,
        related_name="read_notes"
    )
    
    class Meta:
        verbose_name = "Lead Note Read"
        verbose_name_plural = "Lead Note Reads"
        db_table = "lead_note_reads"
        unique_together = ('note', 'user')
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['note', 'user']),
        ]
    
    def __str__(self):
        return f"{self.user.email} read note {self.note.id}"
