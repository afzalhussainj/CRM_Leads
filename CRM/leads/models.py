import arrow
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils.translation import pgettext_lazy
from phonenumber_field.modelfields import PhoneNumberField

from common.models import Profile, LeadStatus
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
    follow_up_status = models.CharField(max_length=16, choices=FOLLOW_UP_STATUS_CHOICES, default="pending")
    is_active = models.BooleanField(default=False)
    always_active = models.BooleanField(default=False)
    priority = models.BooleanField(default=False)
    is_project = models.BooleanField(default=False)
    company_name = models.CharField(max_length=255, blank=True, default="")
    contact_first_name = models.CharField(max_length=255, blank=True, default="")
    contact_last_name = models.CharField(max_length=255, blank=True, default="")
    contact_email = models.EmailField(blank=True, default="")
    contact_phone = PhoneNumberField(null=True, blank=True)
    contact_position_title = models.CharField(max_length=255, blank=True, default="")
    contact_linkedin_url = models.URLField(blank=True, default="")
    # Workflow assignment fields
    assigned_to = models.ForeignKey(
        Profile, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name="assigned_leads",
        help_text="Employee assigned to work on this lead"
    )
    class Meta:
        verbose_name = "Lead"
        verbose_name_plural = "Leads"
        db_table = "lead"
        ordering = ("-created_at",)

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
        if not hasattr(self, '_current_user'):
            return self.notes.exists()
        
        # Get the current user's profile
        try:
            current_profile = Profile.objects.get(user=self._current_user)
        except Profile.DoesNotExist:
            return False
        
        # Get notes sent TO the current user (not BY the current user)
        notes_sent_to_user = self.notes.exclude(author=current_profile)
        
        # Check if user has read all notes sent to them
        read_notes = LeadNoteRead.objects.filter(
            note__lead=self,
            note__in=notes_sent_to_user,
            user=self._current_user
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
    
    def __str__(self):
        return f"{self.user.email} read note {self.note.id}"
