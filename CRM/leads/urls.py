from django.urls import path
from leads import views

app_name = "api_leads"

urlpatterns = [
    path(
        "create-from-site/",
        views.CreateLeadFromSite.as_view(),
        name="create_lead_from_site",
    ),
    path("", views.LeadListView.as_view()),
    path("<str:pk>/", views.LeadDetailView.as_view()),
]
