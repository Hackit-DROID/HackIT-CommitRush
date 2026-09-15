from django.urls import path
from core.auth_views import (
    github_login_view,
    github_callback_view,
    logout_view,
    me_view,
)

urlpatterns = [
    path('auth/github/login/', github_login_view, name='github-login'),
    path('auth/github/callback/', github_callback_view, name='github-callback'),
    path('auth/logout/', logout_view, name='auth-logout'),
    path('auth/me/', me_view, name='auth-me'),
]
