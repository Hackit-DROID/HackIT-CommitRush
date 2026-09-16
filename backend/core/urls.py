from django.urls import path
from core.api_views import (
    AdminPointAdjustmentView,
    ContributionDetailView,
    IssueDetailView,
    IssueListView,
    MyContributionsListView,
    ProjectDetailView,
    ProjectListView,
)
from core.auth_views import (
    github_callback_view,
    github_login_view,
    logout_view,
    me_view,
)
from core.health_views import health_view
from core.webhook_views import github_webhook_view

urlpatterns = [
    path('health/', health_view, name='health'),
    path('auth/github/login/', github_login_view, name='github-login'),
    path('auth/github/callback/', github_callback_view, name='github-callback'),
    path('auth/logout/', logout_view, name='auth-logout'),
    path('auth/me/', me_view, name='auth-me'),
    # M3 Core Read APIs (PRD §16, Plan M3-T1, M3-T2, M3-T3, M3-T4)
    path('projects/', ProjectListView.as_view(), name='project-list'),
    path('projects/<path:slug>/', ProjectDetailView.as_view(), name='project-detail'),
    path('issues/', IssueListView.as_view(), name='issue-list'),
    path('issues/<int:pk>/', IssueDetailView.as_view(), name='issue-detail'),
    # M4 GitHub Webhook Receiver (PRD §13.2, §16, Plan M4-T1)
    path('webhooks/github/', github_webhook_view, name='github-webhook'),
    # M5 Contribution Status APIs (PRD §16, Plan M5-T4)
    path('contributions/mine/', MyContributionsListView.as_view(), name='my-contributions-list'),
    path('contributions/<int:pk>/', ContributionDetailView.as_view(), name='contribution-detail'),
    # M6 Admin Points Adjustment (PRD §14, §16, Plan M6-T6)
    path('admin/points/adjust/', AdminPointAdjustmentView.as_view(), name='admin-point-adjust'),
]
