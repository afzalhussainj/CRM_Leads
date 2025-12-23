import binascii
import os
import uuid
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from .utils.manager import UserManager
from django.db import models
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField

from common.utils.choices import ROLES
from common.base import BaseModel
from utils.roles_enum import UserRole


class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(
        default=uuid.uuid4, unique=True, editable=False, db_index=True, primary_key=True
    )
    email = models.EmailField(_("email address"), unique=True)
    first_name = models.CharField(_("first name"), max_length=150, blank=True)
    last_name = models.CharField(_("last name"), max_length=150, blank=True)
    activation_key = models.CharField(max_length=150, null=True, blank=True)
    key_expires = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    is_staff = models.BooleanField(_('staff status'), default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        db_table = "users"
        ordering = ("-is_active",)
        indexes = [
            models.Index(fields=['is_deleted']),
            models.Index(fields=['is_active', 'is_deleted']),
            models.Index(fields=['email']),  # Email should already be unique, but ensure index exists
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


def generate_unique_key():
    return str(uuid.uuid4())


class Profile(BaseModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = PhoneNumberField(null=True, unique=True)
    alternate_phone = PhoneNumberField(null=True, blank=True)
    role = models.IntegerField(
        choices=[(role.value, role.name) for role in UserRole],
        default=UserRole.EMPLOYEE.value
        )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Profile"
        verbose_name_plural = "Profiles"
        db_table = "profile"
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['role', 'is_active']),
            models.Index(fields=['user', 'is_active']),
        ]

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}"


    @property
    def user_details(self):
        return {
            'email': self.user.email,
            'id': self.user.id,
            'is_active': self.user.is_active,
        }


def generate_key():
    return binascii.hexlify(os.urandom(8)).decode()

class LeadStatus(models.Model):
    """Model to store lead status options that can be managed through admin"""
    name = models.CharField(max_length=100, unique=True)
    sort_order = models.IntegerField(default=0)
    
    class Meta:
        verbose_name = "Lead Status"
        verbose_name_plural = "Lead Statuses"
        db_table = "lead_status"
        ordering = ["sort_order", "name"]
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Invalidate cache when status is saved
        from django.core.cache import cache
        cache.delete('lead_status_choices')
    
    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        # Invalidate cache when status is deleted
        from django.core.cache import cache
        cache.delete('lead_status_choices')
    

class LeadSource(models.Model):
    """Model to store lead source options that can be managed through admin"""
    source = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name = "Lead Source"
        verbose_name_plural = "Lead Sources"
        db_table = "lead_source"
        ordering = ["source"]
    
    def __str__(self):
        return self.source
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Invalidate cache when source is saved
        from django.core.cache import cache
        cache.delete('lead_source_choices')
    
    def delete(self, *args, **kwargs):
        super().delete(*args, **kwargs)
        # Invalidate cache when source is deleted
        from django.core.cache import cache
        cache.delete('lead_source_choices')



