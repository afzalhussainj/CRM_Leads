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
    is_staff = models.BooleanField(_('staff status'), default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        db_table = "users"
        ordering = ("-is_active",)

    def __str__(self):
        return self.email


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

    def __str__(self):
        return f"{self.user.email}"


    @property
    def user_details(self):
        return {
            'email': self.user.email,
            'id': self.user.id,
            'is_active': self.user.is_active,
        }


def generate_key():
    return binascii.hexlify(os.urandom(8)).decode()

class LeadStatus(BaseModel):
    """Model to store lead status options that can be managed through admin"""
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.IntegerField(default=0)
    
    class Meta:
        verbose_name = "Lead Status"
        verbose_name_plural = "Lead Statuses"
        db_table = "lead_status"
        ordering = ["sort_order", "name"]
    
    def __str__(self):
        return self.name
    

class Leads(BaseModel):
    status = models.ForeignKey(LeadStatus, on_delete=models.CASCADE)
    title = models.TextField()
    lead_assigned_to = models.ManyToManyField(
        Profile, related_name="lead_assignee_users"
    )
    created_by = models.ForeignKey(
        Profile,
        related_name="settings_created_by",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Leads"
        verbose_name_plural = "Leads"
        db_table = "leads"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.title}"


class LeadSource(BaseModel):
    """Model to store lead source options that can be managed through admin"""
    name = models.CharField(max_length=100, unique=True)
    phone = PhoneNumberField(null=True, unique=True)
    linkdein = models.CharField(
        max_length=150
    )
    lead = models.ForeignKey(Leads, on_delete=models.CASCADE)
    company = models.CharField(
        max_length=30,
        null=True
        )

    
    class Meta:
        verbose_name = "Lead Source"
        verbose_name_plural = "Lead Sources"
        db_table = "lead_source"
        ordering = ["name"]
    
    def __str__(self):
        return self.name

