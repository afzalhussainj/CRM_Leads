import os
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views
from django.urls import include, path
from django.urls import re_path as url
from django.views.generic import TemplateView
from .views import SiteAdminView
from leads.ui_views import LeadListUI, LeadCreateUI, LeadUpdateUI, LeadDeleteUI, LeadFollowUpStatusUpdateUI, LeadStatusUpdateUI, LeadDetailUI, LeadNotesView, RemindersView, LeadAssignmentUpdateUI
from common.views import LoginUIView, logout_ui_view, AddEmployeeView, ManageLeadOptionsView, TestEmailView

# from drf_yasg import openapi
# from drf_yasg.views import get_schema_view
from rest_framework import permissions
 

app_name = "crm"

urlpatterns = [
    url(
        r"^healthz/$",
        TemplateView.as_view(template_name="healthz.html"),
        name="healthz",
    ),
    # API routes removed after pruning accounts/contacts apps

    path("django-admin/", admin.site.urls),

    path("dashboard/", TemplateView.as_view(template_name="dashboard.html"), name="dashboard"),
    # Contacts/Companies removed in embedded leads mode
    path("ui/leads/", LeadListUI.as_view(), name="ui-leads-list"),
    path("ui/leads/new/", LeadCreateUI.as_view(), name="ui-leads-new"),
    path("ui/leads/<uuid:pk>/edit/", LeadUpdateUI.as_view(), name="ui-leads-edit"),
    path("ui/leads/<uuid:pk>/delete/", LeadDeleteUI.as_view(), name="ui-leads-delete"),
    path("ui/leads/<uuid:pk>/status/", LeadFollowUpStatusUpdateUI.as_view(), name="ui-leads-status"),
    path("ui/leads/<uuid:pk>/lead-status/", LeadStatusUpdateUI.as_view(), name="ui-leads-lead-status"),
    path("ui/leads/<uuid:pk>/assign/", LeadAssignmentUpdateUI.as_view(), name="ui-leads-assign"),
    path("ui/leads/<uuid:pk>/", LeadDetailUI.as_view(), name="ui-leads-detail"),
    path("ui/leads/<uuid:pk>/notes/", LeadNotesView.as_view(), name="ui-leads-notes"),
    path("login/", LoginUIView.as_view(), name="login"),
    path("logout/", logout_ui_view, name="logout"),
    path("add-employee/", AddEmployeeView.as_view(), name="add-employee"),
    path("manage-lead-options/", ManageLeadOptionsView.as_view(), name="manage-lead-options"),
    path("reminders/", RemindersView.as_view(), name="reminders"),
    path("test-email/", TestEmailView.as_view(), name="test-email"),
    path("", SiteAdminView.as_view(), name="site-admin"),
]


if settings.DEBUG:
    from django.conf.urls.static import static
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    # urlpatterns = urlpatterns + static(
    #     settings.MEDIA_URL, document_root=settings.MEDIA_ROOT
    # )
