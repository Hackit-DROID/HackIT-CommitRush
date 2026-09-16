import logging
from django.db.models import Q
from rest_framework import exceptions, generics, permissions, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

from core.models import Contribution, Issue, Project
from core.serializers import (
    ContributionSerializer,
    IssueDetailSerializer,
    IssueListSerializer,
    ProjectDetailSerializer,
    ProjectListSerializer,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Throttling Classes (PRD §16, §19, §20, Plan M3-T5)
# =============================================================================

from django.conf import settings
from rest_framework.settings import api_settings


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
