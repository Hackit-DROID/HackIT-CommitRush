import logging
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import exceptions, generics, permissions, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from core.leaderboard import calculate_participant_rank, fetch_leaderboard_data, invalidate_leaderboard_cache
from core.stats import fetch_event_stats
from core.models import (
    AuditLog,
    Contribution,
    DailyContributionUsage,
    EventConfig,
    Issue,
    Participant,
    PointTransaction,
    Project,
    WebhookEvent,
)
from core.semaphore import RedisMergeSemaphore
from core.serializers import (
    AdminPointAdjustmentSerializer,
    ContributionSerializer,
    DashboardSerializer,
    EventStatsSerializer,
    IssueDetailSerializer,
    IssueListSerializer,
    LeaderboardEntrySerializer,
    OpsMetricsResponseSerializer,
    ProjectDetailSerializer,
    ProjectListSerializer,
    PublicProfileSerializer,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Throttling Classes (PRD §16, §19, §20, Plan M3-T5, M7-T1, M7-T4)
# =============================================================================

class DynamicRateMixin:
    """Helper to dynamically resolve throttle rates from active Django settings."""
    def get_rate(self):
        rf_settings = getattr(settings, 'REST_FRAMEWORK', {})
        rates = rf_settings.get('DEFAULT_THROTTLE_RATES', api_settings.DEFAULT_THROTTLE_RATES)
        if hasattr(self, 'scope') and self.scope in rates:
            return rates[self.scope]
        return rates.get(self.scope)


class ProjectsListAnonRateThrottle(DynamicRateMixin, AnonRateThrottle):
    """Anonymous IP-based rate throttle for the /projects/ list endpoint (~100 req/min)."""
    scope = 'projects_list'


class ProjectsListUserRateThrottle(DynamicRateMixin, UserRateThrottle):
    """Authenticated user rate throttle for the /projects/ list endpoint (~100 req/min)."""
    scope = 'projects_list'

    def get_cache_key(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return None
        return self.cache_format % {
            'scope': self.scope,
            'ident': request.user.pk
        }


class IssuesListAnonRateThrottle(DynamicRateMixin, AnonRateThrottle):
    """Anonymous IP-based rate throttle for the /issues/ list endpoint (~100 req/min)."""
    scope = 'issues_list'


class IssuesListUserRateThrottle(DynamicRateMixin, UserRateThrottle):
    """Authenticated user rate throttle for the /issues/ list endpoint (~100 req/min)."""
    scope = 'issues_list'

    def get_cache_key(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return None
        return self.cache_format % {
            'scope': self.scope,
            'ident': request.user.pk
        }


class LeaderboardAnonRateThrottle(DynamicRateMixin, AnonRateThrottle):
    """Anonymous IP-based rate throttle for the /leaderboard/ list endpoint (~100 req/min)."""
    scope = 'leaderboard_list'


class LeaderboardUserRateThrottle(DynamicRateMixin, UserRateThrottle):
    """Authenticated user rate throttle for the /leaderboard/ list endpoint (~100 req/min)."""
    scope = 'leaderboard_list'

    def get_cache_key(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return None
        return self.cache_format % {
            'scope': self.scope,
            'ident': request.user.pk
        }


class ProfileAnonRateThrottle(DynamicRateMixin, AnonRateThrottle):
    """Anonymous IP-based rate throttle for the /profile/{username}/ endpoint (~100 req/min)."""
    scope = 'profile_detail'


class ProfileUserRateThrottle(DynamicRateMixin, UserRateThrottle):
    """Authenticated user rate throttle for the /profile/{username}/ endpoint (~100 req/min)."""
    scope = 'profile_detail'

    def get_cache_key(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return None
        return self.cache_format % {
            'scope': self.scope,
            'ident': request.user.pk
        }


class StatsAnonRateThrottle(DynamicRateMixin, AnonRateThrottle):
    """Anonymous IP-based rate throttle for the /stats/ endpoint (~120 req/min)."""
    scope = 'stats_list'


class StatsUserRateThrottle(DynamicRateMixin, UserRateThrottle):
    """Authenticated user rate throttle for the /stats/ endpoint (~120 req/min)."""
    scope = 'stats_list'

    def get_cache_key(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return None
        return self.cache_format % {
            'scope': self.scope,
            'ident': request.user.pk
        }





# =============================================================================
# Query Parameter Helper Functions
# =============================================================================

def parse_boolean_param(value: str | None, param_name: str) -> bool | None:
    """
    Parse a boolean query parameter.
    Returns True/False if present, None if omitted.
    Raises ValidationError (HTTP 400) if an invalid boolean string is supplied.
    """
    if value is None:
        return None
    val_clean = str(value).strip().lower()
    if val_clean in ('true', '1', 'yes', 't'):
        return True
    if val_clean in ('false', '0', 'no', 'f'):
        return False
    raise ValidationError({
        param_name: f"Invalid boolean value '{value}' for parameter '{param_name}'. Expected 'true' or 'false'."
    })


def parse_non_negative_int_param(value: str | None, param_name: str) -> int | None:
    """
    Parse a non-negative integer query parameter.
    Returns int if present, None if omitted.
    Raises ValidationError (HTTP 400) if an invalid integer or negative value is supplied.
    """
    if value is None:
        return None
    try:
        val = int(str(value).strip())
        if val < 0:
            raise ValidationError({
                param_name: f"Parameter '{param_name}' must be a non-negative integer (received '{value}')."
            })
        return val
    except (ValueError, TypeError):
        raise ValidationError({
            param_name: f"Invalid integer value '{value}' for parameter '{param_name}'."
        })


# =============================================================================
# Pagination Classes
# =============================================================================

class StandardResultsSetPagination(PageNumberPagination):
    """
    Standard pagination for project listings.
    Default page size: 20, max page size: 100.
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class IssuePagination(PageNumberPagination):
    """
    Server-side pagination for issue exploration.
    Default page size: 25, max page size: 100.
    Ensures client never loads all issues in a single request (PRD §8.2, §16).
    """
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


# =============================================================================
# API Views
# =============================================================================

class ProjectListView(generics.ListAPIView):
    """
    M3-T1: GET /api/v1/projects/
    Public, paginated list of tracked repositories.
    Supports filters:
      - search: case-insensitive partial match on full_name, name, or description
      - language: case-insensitive exact match on primary language
      - enabled: boolean filter on is_enabled ('true' / 'false')
    Throttled per IP / per user budget (M3-T5).
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ProjectsListAnonRateThrottle, ProjectsListUserRateThrottle]
    serializer_class = ProjectListSerializer
    pagination_class = StandardResultsSetPagination

    def get_queryset(self):
        queryset = Project.objects.all().order_by('full_name', 'id')
        params = self.request.query_params

        # Filter: search
        search_query = params.get('search')
        if search_query:
            clean_search = search_query.strip()
            if clean_search:
                queryset = queryset.filter(
                    Q(full_name__icontains=clean_search)
                    | Q(name__icontains=clean_search)
                    | Q(description__icontains=clean_search)
                )

        # Filter: language
        language = params.get('language')
        if language:
            clean_lang = language.strip()
            if clean_lang:
                queryset = queryset.filter(language__iexact=clean_lang)

        # Filter: enabled
        enabled_param = params.get('enabled')
        if enabled_param is not None:
            is_enabled_val = parse_boolean_param(enabled_param, 'enabled')
            if is_enabled_val is not None:
                queryset = queryset.filter(is_enabled=is_enabled_val)

        return queryset


class ProjectDetailView(generics.RetrieveAPIView):
    """
    M3-T2: GET /api/v1/projects/{slug}/
    Public detail view for a tracked project.
    Resolves project slug without requiring schema modifications (AMB-9):
      1. full_name exact match (e.g. 'hackit/awesome-project')
      2. name exact match (e.g. 'awesome-project')
      3. hyphen-converted slug match (e.g. 'hackit-awesome-project' -> 'hackit/awesome-project')
    Returns metadata, issue count, and contribution activity metrics.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = []
    serializer_class = ProjectDetailSerializer

    def get_object(self):
        slug = self.kwargs.get('slug', '').strip().rstrip('/')
        if not slug:
            raise NotFound(detail="Project not found.")

        # 1. Direct match on full_name
        project = Project.objects.filter(full_name__iexact=slug).first()
        if project:
            return project

        # 2. Direct match on name
        project = Project.objects.filter(name__iexact=slug).first()
        if project:
            return project

        # 3. Hyphen-to-slash conversion (owner-repo -> owner/repo)
        if '-' in slug and '/' not in slug:
            converted_slug = slug.replace('-', '/', 1)
            project = Project.objects.filter(full_name__iexact=converted_slug).first()
            if project:
                return project

        raise NotFound(detail=f"Project '{slug}' not found.")


class IssueListView(generics.ListAPIView):
    """
    M3-T3: GET /api/v1/issues/
    Public, server-side paginated list of tracked issues.
    Filters:
      - project: repo slug, full_name, or name
      - language: project language
      - difficulty: difficulty tier (e.g., beginner, intermediate, advanced)
      - category: issue category (e.g., backend, frontend, docs)
      - points_min: minimum points threshold (non-negative integer)
      - points_max: maximum points threshold (non-negative integer)
      - status: issue status (e.g., open, closed, disabled)
      - is_featured: boolean filter
    Sorting:
      - sort query parameter: 'points', '-points', 'newest', '-newest', 'oldest'
      - Default ordering: '-points', '-created_at', '-id'
      - Note on 'newest': uses persisted 'created_at' timestamp across all repositories
        with deterministic '-id' tie-breaker for true chronological sorting (M3-T3).
    Throttled per IP / per user budget (M3-T5).
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [IssuesListAnonRateThrottle, IssuesListUserRateThrottle]
    serializer_class = IssueListSerializer
    pagination_class = IssuePagination

    SORT_MAPPINGS = {
        'points': ['points', '-created_at', '-id'],
        '-points': ['-points', '-created_at', '-id'],
        'newest': ['-created_at', '-id'],
        '-newest': ['created_at', 'id'],
        'oldest': ['created_at', 'id'],
        'id': ['id'],
        '-id': ['-id'],
    }

    def get_queryset(self):
        queryset = Issue.objects.select_related('project').prefetch_related('labels')
        params = self.request.query_params

        # Filter: project
        project_param = params.get('project')
        if project_param:
            proj_slug = project_param.strip()
            if proj_slug:
                q_project = Q(project__full_name__iexact=proj_slug) | Q(project__name__iexact=proj_slug)
                if '-' in proj_slug and '/' not in proj_slug:
                    converted_slug = proj_slug.replace('-', '/', 1)
                    q_project |= Q(project__full_name__iexact=converted_slug)
                queryset = queryset.filter(q_project)

        # Filter: language
        language = params.get('language')
        if language:
            clean_lang = language.strip()
            if clean_lang:
                queryset = queryset.filter(project__language__iexact=clean_lang)

        # Filter: difficulty
        difficulty = params.get('difficulty')
        if difficulty:
            clean_diff = difficulty.strip()
            if clean_diff:
                queryset = queryset.filter(difficulty__iexact=clean_diff)

        # Filter: category
        category = params.get('category')
        if category:
            clean_cat = category.strip()
            if clean_cat:
                queryset = queryset.filter(category__iexact=clean_cat)

        # Filter: status
        status_param = params.get('status')
        if status_param:
            clean_status = status_param.strip()
            if clean_status:
                queryset = queryset.filter(status__iexact=clean_status)

        # Filter: is_featured
        is_featured_param = params.get('is_featured')
        if is_featured_param is not None:
            is_featured_val = parse_boolean_param(is_featured_param, 'is_featured')
            if is_featured_val is not None:
                queryset = queryset.filter(is_featured=is_featured_val)

        # Filter: points_min
        points_min = parse_non_negative_int_param(params.get('points_min'), 'points_min')
        if points_min is not None:
            queryset = queryset.filter(points__gte=points_min)

        # Filter: points_max
        points_max = parse_non_negative_int_param(params.get('points_max'), 'points_max')
        if points_max is not None:
            queryset = queryset.filter(points__lte=points_max)

        # Sorting
        sort_param = params.get('sort') or params.get('ordering')
        if sort_param:
            clean_sort = sort_param.strip()
            if clean_sort not in self.SORT_MAPPINGS:
                valid_options = ', '.join(self.SORT_MAPPINGS.keys())
                raise ValidationError({
                    'sort': f"Invalid sort key '{clean_sort}'. Supported sort options: {valid_options}."
                })
            ordering_fields = self.SORT_MAPPINGS[clean_sort]
        else:
            ordering_fields = ['-points', '-created_at', '-id']

        return queryset.order_by(*ordering_fields)


class IssueDetailView(generics.RetrieveAPIView):
    """
    M3-T4: GET /api/v1/issues/{id}/
    Public issue detail view.
    Returns full issue metadata, project context, and canonical GitHub issue URL.
    Does not call GitHub synchronously.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = []
    serializer_class = IssueDetailSerializer
    queryset = Issue.objects.select_related('project').prefetch_related('labels')
    lookup_field = 'pk'


# =============================================================================
# Contribution Status APIs (PRD §16, §19, Plan M5-T4)
# =============================================================================

class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Object-level permission allowing only the contribution owner or admin/staff to view.
    PRD §16, §19, Plan M5-T4.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff or request.user.is_superuser:
            return True
        return hasattr(obj, 'participant') and obj.participant is not None and obj.participant.user_id == request.user.id


class ContributionPagination(PageNumberPagination):
    """
    Pagination for contribution listings.
    Default page size: 20, max page size: 100.
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class MyContributionsListView(generics.ListAPIView):
    """
    M5-T4: GET /api/v1/contributions/mine/
    Returns the authenticated participant's contribution history and statuses (PRD §16).
    Enforces object-level isolation (participant.user == request.user).
    Zero synchronous calls to GitHub.
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ContributionSerializer
    pagination_class = ContributionPagination

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return Contribution.objects.none()

        queryset = Contribution.objects.filter(
            participant__user=user
        ).select_related(
            'participant',
            'issue__project',
            'pull_request__repo',
        )

        status_param = self.request.query_params.get('status')
        if status_param:
            clean_status = status_param.strip().upper()
            if clean_status:
                queryset = queryset.filter(status=clean_status)

        return queryset.order_by('-created_at', '-id')


class ContributionDetailView(generics.RetrieveAPIView):
    """
    M5-T4: GET /api/v1/contributions/{id}/
    Returns detailed status for a single contribution (PRD §16).
    Restricted to the contribution owner or admin/staff.
    Zero synchronous calls to GitHub.
    """
    permission_classes = [permissions.IsAuthenticated, IsOwnerOrAdmin]
    serializer_class = ContributionSerializer
    queryset = Contribution.objects.select_related(
        'participant',
        'issue__project',
        'pull_request__repo',
    )
    lookup_field = 'pk'


# =============================================================================
# Admin Point Adjustment API (PRD §14, §16, Plan M6-T6)
# =============================================================================

class AdminPointAdjustmentView(APIView):
    """
    M6-T6: POST /api/v1/admin/points/adjust/
    Allows administrative staff to manually adjust a participant's points (PRD §14, §16, Plan M6-T6).
    Enforces:
    - Server-side staff authorization (permissions.IsAdminUser).
    - Non-negative balance constraint (rejects adjustments resulting in negative total).
    - Atomic transaction with row-level locks on Participant.
    - Immutable PointTransaction ledger entry (status='ADMIN_ADJUST').
    - AuditLog audit trail creation.
    """
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = AdminPointAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        participant_id = serializer.validated_data['participant_id']
        points_delta = serializer.validated_data['points']
        reason = serializer.validated_data['reason']

        with transaction.atomic():
            try:
                participant = Participant.objects.select_for_update().get(id=participant_id)
            except Participant.DoesNotExist:
                return Response(
                    {'error': f"Participant with ID {participant_id} not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

            previous_points = participant.total_points
            new_points = previous_points + points_delta

            if new_points < 0:
                return Response(
                    {
                        'error': 'Point adjustment would result in a negative point balance.',
                        'current_points': previous_points,
                        'requested_delta': points_delta,
                        'resulting_points': new_points,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Update participant points
            participant.total_points = new_points
            participant.save(update_fields=['total_points'])

            # Record ledger entry
            pt = PointTransaction.objects.create(
                contribution=None,
                participant=participant,
                points=points_delta,
                status='ADMIN_ADJUST',
                reason=reason,
            )

            # Record audit trail
            AuditLog.objects.create(
                actor=request.user,
                action='admin_point_adjustment',
                target_type='Participant',
                target_id=str(participant.id),
                details={
                    'previous_points': previous_points,
                    'new_points': new_points,
                    'delta': points_delta,
                    'reason': reason,
                    'transaction_id': pt.id,
                },
            )

            # Invalidate cached leaderboard pages
            invalidate_leaderboard_cache()

            logger.info(
                "Admin %s adjusted points for %s by %d (new total: %d, txn: %d, reason: '%s')",
                request.user.username,
                participant.github_username,
                points_delta,
                new_points,
                pt.id,
                reason,
            )

            return Response(
                {
                    'status': 'success',
                    'participant_id': participant.id,
                    'github_username': participant.github_username,
                    'previous_points': previous_points,
                    'new_points': new_points,
                    'delta': points_delta,
                    'transaction_id': pt.id,
                    'reason': reason,
                },
                status=status.HTTP_200_OK,
            )


# =============================================================================
# M7 Leaderboard, Dashboard & Public Profile Views (PRD §8.6, §16, §19, §20)
# =============================================================================

class LeaderboardView(APIView):
    """
    M7-T1 & M7-T2: GET /api/v1/leaderboard/
    Returns paginated public leaderboard rankings (PRD §8.6, §16, §20).
    Ordering: total_points DESC, merged_count DESC, id ASC.
    Optimized with Redis caching (TTL ~60s) and fallback to indexed PostgreSQL query.
    Supports ?include_me=true to include the authenticated participant's own rank.
    Respects EventConfig.leaderboard_frozen state (M7-T2).
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LeaderboardAnonRateThrottle, LeaderboardUserRateThrottle]

    def get(self, request):
        page_raw = request.query_params.get('page', '1')
        page_size_raw = request.query_params.get('page_size', '20')

        try:
            page = int(page_raw)
            if page < 1:
                page = 1
        except (ValueError, TypeError):
            raise ValidationError({'page': f"Invalid page number '{page_raw}'."})

        try:
            page_size = int(page_size_raw)
            if page_size < 1:
                page_size = 20
            elif page_size > 100:
                page_size = 100
        except (ValueError, TypeError):
            raise ValidationError({'page_size': f"Invalid page_size '{page_size_raw}'."})

        # Check include_me / current participant
        current_participant = None
        include_me_param = request.query_params.get('include_me')
        wants_me = False
        if include_me_param is not None:
            wants_me = parse_boolean_param(include_me_param, 'include_me')
        else:
            wants_me = bool(request.user and request.user.is_authenticated)

        if wants_me and request.user and request.user.is_authenticated:
            current_participant = getattr(request.user, 'participant', None)

        data = fetch_leaderboard_data(
            page=page,
            page_size=page_size,
            current_participant=current_participant if wants_me else None,
        )

        base_url = request.build_absolute_uri(request.path)
        next_url = None
        prev_url = None
        total_pages = data['total_pages']
        count = data['count']

        if page < total_pages and (page * page_size) < count:
            next_url = f"{base_url}?page={page + 1}&page_size={page_size}"
        if page > 1 and page <= total_pages + 1:
            prev_url = f"{base_url}?page={page - 1}&page_size={page_size}"

        response_payload = {
            'count': data['count'],
            'page': data['page'],
            'page_size': data['page_size'],
            'total_pages': data['total_pages'],
            'next': next_url,
            'previous': prev_url,
            'is_frozen': data['is_frozen'],
            'results': data['results'],
            'me': data['me'],
        }

        return Response(response_payload, status=status.HTTP_200_OK)


class DashboardView(APIView):
    """
    M7-T3: GET /api/v1/dashboard/
    Single aggregated endpoint serving the authenticated participant's complete dashboard (PRD §16, Plan M7-T3).
    Returns:
    - participant profile (id, github_id, github_username, avatar_url, is_suspended)
    - rank (matching exact leaderboard ordering)
    - total points
    - merged contribution count
    - daily usage & limit progress (contributions count, points count, caps)
    - in-progress contributions (non-terminal states)
    - recent activity (latest 10 contributions)
    Zero synchronous calls to GitHub.
    Enforces object-level authentication (request.user).
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        participant = getattr(user, 'participant', None)
        if not participant:
            raise NotFound("Participant profile not found for authenticated user.")

        config = EventConfig.get_solo()
        today = timezone.now().date()

        # Authoritative daily usage
        daily_usage, _ = DailyContributionUsage.objects.get_or_create(
            participant=participant,
            date=today,
            defaults={'contributions_count': 0, 'points_count': 0},
        )

        daily_usage_data = {
            'date': today,
            'contributions_count': daily_usage.contributions_count,
            'max_contributions': config.max_contributions_per_day,
            'points_count': daily_usage.points_count,
            'max_points': config.max_points_per_day,
        }

        # Calculate exact rank matching leaderboard
        rank = calculate_participant_rank(participant.id)

        # In-progress contributions (non-terminal states per PRD §11)
        in_progress_statuses = ['PENDING', 'QUEUED', 'UNDER_REVIEW', 'APPROVED', 'MERGING', 'RETRY', 'FLAGGED']
        in_progress_qs = (
            Contribution.objects.filter(
                participant=participant,
                status__in=in_progress_statuses,
            )
            .select_related('participant', 'issue__project', 'pull_request__repo')
            .order_by('-created_at', '-id')
        )

        # Recent activity (all statuses, bounded to latest 10)
        recent_activity_qs = (
            Contribution.objects.filter(participant=participant)
            .select_related('participant', 'issue__project', 'pull_request__repo')
            .order_by('-created_at', '-id')[:10]
        )

        dashboard_data = {
            'participant': participant,
            'rank': rank,
            'total_points': participant.total_points,
            'merged_count': participant.merged_count,
            'daily_usage': daily_usage_data,
            'in_progress_contributions': in_progress_qs,
            'recent_activity': recent_activity_qs,
        }

        serializer = DashboardSerializer(dashboard_data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class PublicProfileView(APIView):
    """
    M7-T4: GET /api/v1/profile/<str:username>/
    Public contributor profile API exposing safe aggregate metrics only (PRD §16, §19, Plan M7-T4).
    Excludes private workflow details, internal moderation flags, tokens, or audit logs.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ProfileAnonRateThrottle, ProfileUserRateThrottle]

    def get(self, request, username):
        clean_username = username.strip() if username else ''
        if not clean_username:
            raise NotFound("Username parameter is required.")

        participant = Participant.objects.filter(
            github_username__iexact=clean_username
        ).first()

        if not participant or participant.is_suspended:
            raise NotFound(f"Participant '{clean_username}' not found.")

        # Aggregate counts
        contributions_qs = participant.contributions.all()
        total_contributions = contributions_qs.count()
        merged_contributions = contributions_qs.filter(status='MERGED').count()
        in_progress_contributions = contributions_qs.filter(
            status__in=['PENDING', 'QUEUED', 'UNDER_REVIEW', 'APPROVED', 'MERGING', 'RETRY', 'FLAGGED']
        ).count()
        rejected_contributions = contributions_qs.filter(status='REJECTED').count()

        # Rank
        rank = calculate_participant_rank(participant.id)

        # Safe recent merged contributions (latest 5)
        recent_merged_qs = (
            contributions_qs.filter(status='MERGED')
            .select_related('issue__project', 'pull_request__repo')
            .order_by('-merged_at', '-id')[:5]
        )

        recent_merged = [
            {
                'id': c.id,
                'project_name': c.pull_request.repo.full_name if c.pull_request and c.pull_request.repo else (c.issue.project.full_name if c.issue else ''),
                'issue_number': c.issue.number if c.issue else 0,
                'issue_title': c.issue.title if c.issue else '',
                'points': c.issue.points if c.issue else 0,
                'merged_at': c.merged_at,
                'github_url': f"https://github.com/{c.pull_request.repo.full_name}/pull/{c.pull_request.number}" if c.pull_request and c.pull_request.repo else '',
            }
            for c in recent_merged_qs
        ]

        profile_data = {
            'id': participant.id,
            'github_id': participant.github_id,
            'github_username': participant.github_username,
            'avatar_url': participant.avatar_url,
            'total_points': participant.total_points,
            'merged_count': participant.merged_count,
            'rank': rank,
            'stats': {
                'total_contributions': total_contributions,
                'merged_contributions': merged_contributions,
                'in_progress_contributions': in_progress_contributions,
                'rejected_contributions': rejected_contributions,
            },
            'recent_merged_contributions': recent_merged,
        }

        serializer = PublicProfileSerializer(profile_data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class EventStatsView(APIView):
    """
    M7-T5: GET /api/v1/stats/
    Public aggregate event stats endpoint (PRD §8.6, §16, §23, Plan M7-T5).
    Cached with ~60s TTL, refreshed asynchronously by Celery Beat.
    Zero synchronous GitHub calls.
    """
    permission_classes = [permissions.AllowAny]
    throttle_classes = [StatsAnonRateThrottle, StatsUserRateThrottle]

    def get(self, request):
        stats_data = fetch_event_stats()
        serializer = EventStatsSerializer(stats_data)
        return Response(serializer.data, status=status.HTTP_200_OK)


class OpsMetricsView(APIView):
    """
    M8-T6: GET /api/v1/ops/metrics/
    Operator dashboard metrics endpoint (PRD §12.6, §18, Plan M8-T6).
    Restricted to staff/admin users (permissions.IsAdminUser).
    Zero synchronous GitHub calls.
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        config = EventConfig.get_solo()
        now = timezone.now()

        # 1. Queue counts
        validation_queued = Contribution.objects.filter(status='QUEUED').count()
        validation_under_review = Contribution.objects.filter(status='UNDER_REVIEW').count()
        merge_approved = Contribution.objects.filter(status='APPROVED').count()
        merge_active = Contribution.objects.filter(status='MERGING').count()
        flagged_or_retry = Contribution.objects.filter(status__in=['FLAGGED', 'RETRY']).count()
        webhooks_total = WebhookEvent.objects.count()
        webhooks_unprocessed = WebhookEvent.objects.filter(processed_at__isnull=True).count()

        # 2. Merge semaphore usage
        semaphore = RedisMergeSemaphore()
        active_semaphore_slots = semaphore.get_current_usage()
        available_slots = max(0, config.merge_concurrency - active_semaphore_slots)

        # 3. Oldest queued item age
        oldest_queued = Contribution.objects.filter(status__in=['QUEUED', 'APPROVED']).order_by('created_at').first()
        oldest_age = int((now - oldest_queued.created_at).total_seconds()) if oldest_queued else None

        # 4. Last webhook activity
        last_webhook = WebhookEvent.objects.order_by('-id').first()
        last_webhook_at = last_webhook.processed_at if (last_webhook and last_webhook.processed_at) else None

        data = {
            'event_status': config.event_status,
            'system_status': {
                'merge_paused': config.merge_paused,
                'validation_paused': config.validation_paused,
                'submissions_paused': config.submissions_paused,
                'leaderboard_frozen': config.leaderboard_frozen,
            },
            'queues': {
                'validation_queued': validation_queued,
                'validation_under_review': validation_under_review,
                'merge_approved': merge_approved,
                'merge_active': merge_active,
                'flagged_or_retry': flagged_or_retry,
                'webhooks_total': webhooks_total,
                'webhooks_unprocessed': webhooks_unprocessed,
            },
            'semaphore': {
                'configured_concurrency': config.merge_concurrency,
                'active_semaphore_slots': active_semaphore_slots,
                'available_slots': available_slots,
            },
            'oldest_queued_item_age_seconds': oldest_age,
            'last_webhook_received_at': last_webhook_at,
            'generated_at': now,
        }

        serializer = OpsMetricsResponseSerializer(data)
        return Response(serializer.data, status=status.HTTP_200_OK)


