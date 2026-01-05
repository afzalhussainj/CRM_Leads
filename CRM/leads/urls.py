from django.urls import path
from leads import views

app_name = "api_leads"

urlpatterns = [
    # create-from-site endpoint removed - it depended on the Leads model which has been removed
    path("", views.LeadListView.as_view()),
    path("<str:pk>/", views.LeadDetailView.as_view()),
    path("<str:pk>/follow-up-status/", views.LeadFollowUpStatusUpdateView.as_view(), name="api_lead_follow_up_status"),
]
