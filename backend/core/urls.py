from django.urls import path
from core.api_views import (
    AdminAuditLogListView,
    AdminFarmingReviewListView,
    AdminGitHubSyncView,

    AdminIssueDetailView,
    AdminIssueListView,
    AdminOpsMetricsView,
    AdminParticipantDetailView,
    AdminParticipantModerationView,
    AdminPointAdjustmentView,
    AdminSystemControlsView,
    ContributionDetailView,
    DashboardView,
    EventStatsView,
    IssueCategoryListView,
    IssueDetailView,
    IssueListView,
    LeaderboardView,
    MyContributionsListView,
    OpsMetricsView,
    ProjectDetailView,
    ProjectListView,
    PublicProfileView,
)
from core.auth_views import (
    csrf_view,
    dev_login_view,
    frontend_profile_redirect,
    github_callback_view,
    github_login_view,
    logout_view,
    me_view,
)
from core.health_views import health_view
from core.views import custom_404_view
from core.webhook_views import github_webhook_view

urlpatterns = [
    path('', health_view, name='root'),
    path('health/', health_view, name='health'),
    path('404/', custom_404_view, name='custom-404'),
    path('profile/', frontend_profile_redirect, name='profile-redirect'),
    path('auth/csrf/', csrf_view, name='auth-csrf'),
    path('auth/dev-login/', dev_login_view, name='dev-login'),
    path('auth/github/login/', github_login_view, name='github-login'),
    path('auth/github/callback/', github_callback_view, name='github-callback'),
    path('auth/logout/', logout_view, name='auth-logout'),
    path('auth/me/', me_view, name='auth-me'),
    # M3 Core Read APIs (PRD §16, Plan M3-T1, M3-T2, M3-T3, M3-T4)
    path('projects/', ProjectListView.as_view(), name='project-list'),
    path('projects/<path:slug>/', ProjectDetailView.as_view(), name='project-detail'),
    path('issues/', IssueListView.as_view(), name='issue-list'),
    path('issues/categories/', IssueCategoryListView.as_view(), name='issue-category-list'),
    path('issues/<int:pk>/', IssueDetailView.as_view(), name='issue-detail'),
    # M4 GitHub Webhook Receiver (PRD §13.2, §16, Plan M4-T1)
    path('webhooks/github/', github_webhook_view, name='github-webhook'),
    # M5 Contribution Status APIs (PRD §16, Plan M5-T4)
    path('contributions/mine/', MyContributionsListView.as_view(), name='my-contributions-list'),
    path('contributions/<int:pk>/', ContributionDetailView.as_view(), name='contribution-detail'),
    # M7 Leaderboard, Dashboard, Profile & Stats (PRD §8.6, §16, Plan M7-T1, M7-T2, M7-T3, M7-T4, M7-T5)
    path('leaderboard/', LeaderboardView.as_view(), name='leaderboard'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('profile/<str:username>/', PublicProfileView.as_view(), name='profile-detail'),
    path('stats/', EventStatsView.as_view(), name='stats'),
    # Secure Administrator-Only API Layer (PRD §14, §16, §18)
    path('admin/controls/', AdminSystemControlsView.as_view(), name='admin-controls'),
    path('admin/metrics/', AdminOpsMetricsView.as_view(), name='admin-metrics'),
    path('admin/github/sync/', AdminGitHubSyncView.as_view(), name='admin-github-sync'),
    path('admin/issues/', AdminIssueListView.as_view(), name='admin-issue-list'),
    path('admin/issues/<int:pk>/', AdminIssueDetailView.as_view(), name='admin-issue-detail'),
    path('admin/participants/<int:pk>/', AdminParticipantDetailView.as_view(), name='admin-participant-detail'),
    path('admin/participants/<int:pk>/suspend/', AdminParticipantModerationView.as_view(), name='admin-participant-suspend'),
    path('admin/points/adjust/', AdminPointAdjustmentView.as_view(), name='admin-point-adjust'),
    path('admin/audit-logs/', AdminAuditLogListView.as_view(), name='admin-audit-logs'),
    path('admin/farming-reviews/', AdminFarmingReviewListView.as_view(), name='admin-farming-reviews'),
]


