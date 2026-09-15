from django.urls import path
from core.auth_views import (
    github_login_view,
    github_callback_view,
    logout_view,
    me_view,
)
from core.health_views import health_view

urlpatterns = [
    path('health/', health_view, name='health'),
    path('auth/github/login/', github_login_view, name='github-login'),
    path('auth/github/callback/', github_callback_view, name='github-callback'),
    path('auth/logout/', logout_view, name='auth-logout'),
    path('auth/me/', me_view, name='auth-me'),
]
