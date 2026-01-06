from django.urls import path
from leads import views

app_name = "api_leads"

urlpatterns = [
    # create-from-site endpoint removed - it depended on the Leads model which has been removed
    path("", views.LeadListView.as_view()),
    path("<str:pk>/", views.LeadDetailView.as_view()),
    path("<str:pk>/follow-up-status/", views.LeadFollowUpStatusUpdateView.as_view(), name="api_lead_follow_up_status"),
    path("<str:pk>/notes/", views.LeadNotesListView.as_view(), name="api_lead_notes"),
    path("<str:pk>/notes/unread/", views.LeadNotesUnreadListView.as_view(), name="api_lead_notes_unread"),
    path("<str:pk>/notes/<str:note_pk>/", views.LeadNoteDetailView.as_view(), name="api_lead_note_detail"),
    path("<str:pk>/notes/<str:note_pk>/read/", views.LeadNoteMarkReadView.as_view(), name="api_lead_note_mark_read"),
]
