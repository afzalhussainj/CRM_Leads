import os
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from leads.combined_management_views import CombinedManagementView, StatusCreateView, StatusDeleteView, SourceCreateView, SourceDeleteView, LeadoptionsListView
from leads.employee_management_views import EmployeeListView, EmployeeToggleActiveView, EmployeeDeleteView

 

app_name = "crm"

urlpatterns = [
    path("django-admin/", admin.site.urls),

    # API endpoints
    path("api/common/", include("common.urls")),
    path("api/leads/", include("leads.urls")),

    #Combined Options Management URLs
    path("ui/options/", LeadoptionsListView.as_view(), name="api_options"),
    path("ui/options/statuses/create/", StatusCreateView.as_view(), name="ui-options-statuses-create"),
    path("ui/options/statuses/<int:pk>/delete/", StatusDeleteView.as_view(), name="ui-options-statuses-delete"),
    path("ui/options/sources/create/", SourceCreateView.as_view(), name="ui-options-sources-create"),
    path("ui/options/sources/<int:pk>/delete/", SourceDeleteView.as_view(), name="ui-options-sources-delete"),
    
    # Employee Management URLs
    path("ui/employees/", EmployeeListView.as_view(), name="api-employees-list"),
    path("ui/employees/<uuid:pk>/toggle-active/", EmployeeToggleActiveView.as_view(), name="api-employees-toggle-active"),
    path("ui/employees/<uuid:pk>/delete/", EmployeeDeleteView.as_view(), name="api-employees-delete"),
]