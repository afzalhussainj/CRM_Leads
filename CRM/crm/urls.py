import os
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
# UI views commented out - using React frontend instead
# from django.views.generic import TemplateView
# from .views import SiteAdminView
# from leads.ui_views import LeadListUI, LeadCreateUI, LeadUpdateUI, LeadDeleteUI, LeadFollowUpStatusUpdateUI, LeadStatusUpdateUI, LeadDetailUI, LeadNotesView, RemindersView, LeadAssignmentUpdateUI, LeadColumnCustomizationView, LeadCSVExportView, LeadToggleAlwaysActiveView, LeadTogglePriorityView, LeadToggleProjectView, ProjectsListView, ProjectsColumnCustomizationView
from leads.combined_management_views import CombinedManagementView, StatusCreateView, StatusDeleteView, SourceCreateView, SourceDeleteView, LeadSourceListView, LeadStatusListView
# from leads.employee_management_views import EmployeeManagementView, EmployeeToggleActiveView, EmployeeSoftDeleteView
# from common.views import AddEmployeeView, TestEmailView

 

app_name = "crm"

urlpatterns = [
    path("django-admin/", admin.site.urls),
    
    # API endpoints
    path("api/common/", include("common.urls")),
    path("api/leads/", include("leads.urls")),

    # UI routes commented out - using React frontend instead
    # path("dashboard/", TemplateView.as_view(template_name="dashboard.html"), name="dashboard"),
    
    # path("ui/leads/", LeadListUI.as_view(), name="ui-leads-list"),
    # path("ui/leads/new/", LeadCreateUI.as_view(), name="ui-leads-new"),
    # path("ui/leads/<uuid:pk>/edit/", LeadUpdateUI.as_view(), name="ui-leads-edit"),
    # path("ui/leads/<uuid:pk>/delete/", LeadDeleteUI.as_view(), name="ui-leads-delete"),
    # path("ui/leads/<uuid:pk>/status/", LeadFollowUpStatusUpdateUI.as_view(), name="ui-leads-status"),
    # path("ui/leads/<uuid:pk>/lead-status/", LeadStatusUpdateUI.as_view(), name="ui-leads-lead-status"),
    # path("ui/leads/<uuid:pk>/assign/", LeadAssignmentUpdateUI.as_view(), name="ui-leads-assign"),
    # path("ui/leads/<uuid:pk>/toggle-always-active/", LeadToggleAlwaysActiveView.as_view(), name="ui-leads-toggle-always-active"),
    # path("ui/leads/<uuid:pk>/toggle-priority/", LeadTogglePriorityView.as_view(), name="ui-leads-toggle-priority"),
    # path("ui/leads/<uuid:pk>/toggle-project/", LeadToggleProjectView.as_view(), name="ui-leads-toggle-project"),
    # path("ui/leads/<uuid:pk>/notes/", LeadNotesView.as_view(), name="ui-leads-notes"),
    # path("ui/leads/<uuid:pk>/", LeadDetailUI.as_view(), name="ui-leads-detail"),
    # path("ui/leads/customize-columns/", LeadColumnCustomizationView.as_view(), name="ui-leads-customize-columns"),
    # path("ui/leads/export/", LeadCSVExportView.as_view(), name="ui-leads-export"),
    # path("ui/projects/", ProjectsListView.as_view(), name="ui-projects"),
    # path("ui/projects/customize-columns/", ProjectsColumnCustomizationView.as_view(), name="ui-projects-customize-columns"),
    
    # # Combined Options Management URLs
    # path("ui/options/", CombinedManagementView.as_view(), name="ui-options"),
    # Options (statuses/sources)
    path("ui/options/statuses/", LeadStatusListView.as_view(), name="api_options_statuses"),
    path("ui/options/sources/", LeadSourceListView.as_view(), name="api_options_sources"),
    path("ui/options/statuses/create/", StatusCreateView.as_view(), name="ui-options-statuses-create"),
    # path("ui/options/statuses/<int:pk>/delete/", StatusDeleteView.as_view(), name="ui-options-statuses-delete"),
    path("ui/options/sources/create/", SourceCreateView.as_view(), name="ui-options-sources-create"),
    # path("ui/options/sources/<int:pk>/delete/", SourceDeleteView.as_view(), name="ui-options-sources-delete"),
    
    # # Employee Management URLs
    # path("ui/employees/", EmployeeManagementView.as_view(), name="ui-employees"),
    # path("ui/employees/<uuid:pk>/toggle-active/", EmployeeToggleActiveView.as_view(), name="ui-employees-toggle-active"),
    # path("ui/employees/<uuid:pk>/delete/", EmployeeSoftDeleteView.as_view(), name="ui-employees-delete"),
    # path("add-employee/", AddEmployeeView.as_view(), name="add-employee"),
    # path("reminders/", RemindersView.as_view(), name="reminders"),
    # path("test-email/", TestEmailView.as_view(), name="test-email"),
    # path("", SiteAdminView.as_view(), name="site-admin"),
]


if settings.DEBUG:
    from django.conf.urls.static import static
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
