from django.urls import path
from leads import views

app_name = "api_leads"

urlpatterns = [
    path("", views.LeadListView.as_view()),
    path("reminders/", views.RemindersListView.as_view(), name="api_reminders"),
    path("<str:pk>/", views.LeadDetailView.as_view()),
    path("<str:pk>/follow-up-status/", views.LeadFollowUpStatusUpdateView.as_view(), name="api_lead_follow_up_status"),
    path("<str:pk>/always-active/", views.LeadAlwaysActiveUpdateView.as_view(), name="api_lead_always_active"),
    path("<str:pk>/notes/mark-read/", views.LeadNoteMarkReadView.as_view(), name="api_lead_notes_mark_read"),
    path("<str:pk>/notes/unread/", views.LeadNotesUnreadListView.as_view(), name="api_lead_notes_unread"),
    path("<str:pk>/notes/", views.LeadNotesListView.as_view(), name="api_lead_notes"),
    path("<str:pk>/notes/<str:note_pk>/", views.LeadNoteDetailView.as_view(), name="api_lead_note_detail"),
]
