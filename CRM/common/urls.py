from django.urls import path

from common import views

app_name = "api_common"


urlpatterns = [
    path("dashboard/", views.ApiHomeView.as_view()),
    # Authentication endpoints
    path("auth/login/", views.login_view, name="api_login"),
    path("auth/logout/", views.logout_view, name="api_logout"),
    path(
        "auth/refresh-token/",
        views.refresh_token_view,
        name="token_refresh",
    ),
    path(
        "auth/password-reset-request/",
        views.password_reset_request,
        name="api_password_reset_request",
    ),
    path(
        "auth/password-reset-confirm/",
        views.password_reset_confirm,
        name="api_password_reset_confirm",
    ),
    # GoogleLoginView
    path("auth/google/", views.GoogleLoginView.as_view()),
    path("profile/", views.ProfileView.as_view()),
    path("users/get-teams-and-users/", views.GetTeamsAndUsersView.as_view()),
    path("users/create-employee/", views.create_employee, name="api_create_employee"),
    path("users/", views.UsersListView.as_view()),
    path("user/<str:pk>/", views.UserDetailView.as_view()),
    # path("documents/", views.DocumentListView.as_view()),
    # path("documents/<str:pk>/", views.DocumentDetailView.as_view()),
    path("api-settings/", views.DomainList.as_view()),
    path("api-settings/<str:pk>/", views.DomainDetailView.as_view()),
    path("user/<str:pk>/status/", views.UserStatusView.as_view()),
]
