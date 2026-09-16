import logging
import re
import requests
from django.conf import settings
from django.db import transaction

from core.models import Issue, IssueLabel, Project

logger = logging.getLogger(__name__)

GITHUB_API_BASE_URL = 'https://api.github.com'
REPO_PATTERN = re.compile(r'^[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+$')


class GitHubSyncError(Exception):
    """Base exception for all GitHub sync errors."""
    pass


class GitHubConfigurationError(GitHubSyncError):
    """Raised when GitHub client configuration is invalid or missing."""
    pass


class GitHubResourceNotFoundError(GitHubSyncError):
    """Raised when the requested repository is not found on GitHub (HTTP 404)."""
    pass


class GitHubAuthenticationError(GitHubSyncError):
    """Raised when GitHub API authentication or permission check fails (HTTP 401/403)."""
    pass


class GitHubRateLimitError(GitHubSyncError):
    """Raised when GitHub API rate limits are exceeded (HTTP 403 rate limit / 429)."""
    pass


class GitHubAPIError(GitHubSyncError):
    """Raised when GitHub API returns an unexpected server error (HTTP 5xx / unexpected status)."""
    pass


class GitHubNetworkError(GitHubSyncError):
    """Raised on connection timeout or network level failure."""
    pass


class GitHubDataError(GitHubSyncError):
    """Raised when GitHub response payload is malformed or missing required fields."""
    pass


def parse_repo_identifier(repo_identifier: str) -> tuple[str, str]:
    """
    Validate and parse a repository identifier in 'owner/name' format.
    Raises ValueError if the input is malformed.
    """
    cleaned = (repo_identifier or '').strip()
    if not cleaned or not REPO_PATTERN.match(cleaned):
        raise ValueError(f"Invalid repository identifier '{repo_identifier}'. Expected format: 'owner/name'.")

    parts = cleaned.split('/')
    if (
        len(parts) != 2
        or not parts[0]
        or not parts[1]
        or parts[0].strip('.') == ''
        or parts[1].strip('.') == ''
    ):
        raise ValueError(f"Invalid repository identifier '{repo_identifier}'. Expected format: 'owner/name'.")

    return parts[0], parts[1]


class GitHubClient:
    """
    Authenticated GitHub REST API client for read-side synchronization.
    Handles headers, timeouts, error status mapping, and ensures secrets are not leaked.
    """

    def __init__(
        self,
        token: str | None = None,
        timeout: int = 10,
        base_url: str = GITHUB_API_BASE_URL,
    ):
        self.token = token if token is not None else getattr(settings, 'GITHUB_API_TOKEN', '')
        self.timeout = timeout
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()

    def _get_headers(self) -> dict[str, str]:
        headers = {
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'HackIT-CommitRush-Sync/1.0',
        }
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        return headers

    def get_repository(self, owner: str, repo: str) -> dict:
        """
        Fetch repository metadata from GET /repos/{owner}/{repo}.
        Never leaks authorization tokens in error messages or logs.
        """
        if not owner or not repo:
            raise ValueError("Owner and repository name must be non-empty.")

        url = f"{self.base_url}/repos/{owner}/{repo}"
        headers = self._get_headers()

        try:
            response = self.session.get(
                url,
                headers=headers,
                timeout=self.timeout,
            )
        except requests.Timeout as e:
            logger.warning("GitHub API request timed out for repository %s/%s", owner, repo)
            raise GitHubNetworkError(f"GitHub API request timed out after {self.timeout}s.") from e
        except requests.RequestException as e:
            logger.warning("GitHub API network failure for repository %s/%s", owner, repo)
            raise GitHubNetworkError("Failed to communicate with GitHub REST API.") from e

        if response.status_code == 200:
            try:
                data = response.json()
            except ValueError as e:
                raise GitHubDataError("Invalid JSON returned by GitHub API.") from e

            if not isinstance(data, dict):
                raise GitHubDataError("Malformed response payload returned by GitHub API (expected JSON object).")

            # Validate required repository fields
            if 'id' not in data or not data.get('name') or not data.get('full_name'):
                raise GitHubDataError("GitHub repository payload is missing essential fields ('id', 'name', 'full_name').")

            return data

        if response.status_code == 404:
            logger.info("GitHub repository %s/%s not found (HTTP 404)", owner, repo)
            raise GitHubResourceNotFoundError(f"Repository '{owner}/{repo}' was not found on GitHub (HTTP 404).")

        if response.status_code == 401:
            logger.warning("GitHub authentication failed for %s/%s (HTTP 401)", owner, repo)
            raise GitHubAuthenticationError("GitHub API authentication failed (HTTP 401). Verify GITHUB_API_TOKEN configuration.")

        if response.status_code == 403:
            rate_remaining = response.headers.get('X-RateLimit-Remaining')
            if rate_remaining == '0':
                logger.warning("GitHub API rate limit reached (HTTP 403)")
                raise GitHubRateLimitError("GitHub API rate limit exceeded (HTTP 403).")
            logger.warning("GitHub API permission denied or rate limited (HTTP 403) for %s/%s", owner, repo)
            raise GitHubAuthenticationError(f"GitHub API permission denied or rate limited (HTTP 403) for '{owner}/{repo}'.")

        if response.status_code == 429:
            logger.warning("GitHub API rate limit reached (HTTP 429)")
            raise GitHubRateLimitError("GitHub API rate limit reached (HTTP 429).")

        if response.status_code >= 500:
            logger.warning("GitHub API server error HTTP %s for %s/%s", response.status_code, owner, repo)
            raise GitHubAPIError(f"GitHub API server error (HTTP {response.status_code}).")

        logger.warning("GitHub API unexpected response HTTP %s for %s/%s", response.status_code, owner, repo)
        raise GitHubAPIError(f"GitHub API returned unexpected status {response.status_code}.")

    def get_issues(self, owner: str, repo: str, state: str = 'all') -> list[dict]:
        """
        Fetch all issues for repository from GET /repos/{owner}/{repo}/issues.
        Handles multi-page pagination. Filters out pull requests.
        """
        if not owner or not repo:
            raise ValueError("Owner and repository name must be non-empty.")

        url = f"{self.base_url}/repos/{owner}/{repo}/issues"
        headers = self._get_headers()
        params = {
            'state': state,
            'per_page': 100,
            'page': 1,
        }

        all_issues = []

        while url:
            try:
                response = self.session.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=self.timeout,
                )
            except requests.Timeout as e:
                logger.warning("GitHub API request timed out fetching issues for %s/%s", owner, repo)
                raise GitHubNetworkError(f"GitHub API request timed out after {self.timeout}s.") from e
            except requests.RequestException as e:
                logger.warning("GitHub API network failure fetching issues for %s/%s", owner, repo)
                raise GitHubNetworkError("Failed to communicate with GitHub REST API.") from e

            if response.status_code == 200:
                try:
                    data = response.json()
                except ValueError as e:
                    raise GitHubDataError("Invalid JSON returned by GitHub API.") from e

                if not isinstance(data, list):
                    raise GitHubDataError("Malformed response payload returned by GitHub API (expected JSON array).")

                for item in data:
                    if not isinstance(item, dict):
                        continue
                    # Skip Pull Requests returned by GitHub's issues endpoint
                    if 'pull_request' in item:
                        continue
                    if 'id' in item and 'number' in item:
                        all_issues.append(item)

                # Check Link header for rel="next"
                next_url = None
                if 'Link' in response.headers:
                    links = requests.utils.parse_header_links(response.headers['Link'])
                    for link in links:
                        if link.get('rel') == 'next':
                            next_url = link.get('url')
                            break

                if next_url:
                    url = next_url
                    params = None  # query params already part of next_url
                else:
                    # Fallback pagination if Link header missing but full page returned
                    if params and len(data) == params.get('per_page', 100):
                        params['page'] += 1
                    else:
                        url = None

                continue

            if response.status_code == 404:
                logger.info("GitHub repository %s/%s not found when fetching issues (HTTP 404)", owner, repo)
                raise GitHubResourceNotFoundError(f"Repository '{owner}/{repo}' was not found on GitHub (HTTP 404).")

            if response.status_code == 401:
                logger.warning("GitHub authentication failed fetching issues for %s/%s (HTTP 401)", owner, repo)
                raise GitHubAuthenticationError("GitHub API authentication failed (HTTP 401). Verify GITHUB_API_TOKEN configuration.")

            if response.status_code == 403:
                rate_remaining = response.headers.get('X-RateLimit-Remaining')
                if rate_remaining == '0':
                    logger.warning("GitHub API rate limit reached (HTTP 403)")
                    raise GitHubRateLimitError("GitHub API rate limit exceeded (HTTP 403).")
                logger.warning("GitHub API permission denied or rate limited (HTTP 403) for %s/%s", owner, repo)
                raise GitHubAuthenticationError(f"GitHub API permission denied or rate limited (HTTP 403) for '{owner}/{repo}'.")

            if response.status_code == 429:
                logger.warning("GitHub API rate limit reached (HTTP 429)")
                raise GitHubRateLimitError("GitHub API rate limit reached (HTTP 429).")

            if response.status_code >= 500:
                logger.warning("GitHub API server error HTTP %s fetching issues for %s/%s", response.status_code, owner, repo)
                raise GitHubAPIError(f"GitHub API server error (HTTP {response.status_code}).")

            logger.warning("GitHub API unexpected response HTTP %s fetching issues for %s/%s", response.status_code, owner, repo)
            raise GitHubAPIError(f"GitHub API returned unexpected status {response.status_code}.")

        return all_issues


def sync_project(repo_data: dict) -> tuple[Project, bool]:
    """
    Synchronize repository metadata into the Project model.
    
    Mapping rules:
    - github_repo_id: repo_data['id'] (immutable unique key)
    - owner: repo_data['owner']['login'] or repo_data['owner']
    - name: repo_data['name']
    - full_name: repo_data['full_name']
    - language: repo_data.get('language') or ''
    - description: repo_data.get('description') or ''
    
    Non-destructive update rule:
    - If Project exists: updates mutable GitHub metadata. DOES NOT overwrite Project.is_enabled.
    - If Project is created: uses model default (is_enabled=True).
    
    Returns (project, created: bool).
    """
    github_repo_id = repo_data.get('id')
    if github_repo_id is None:
        raise GitHubDataError("Missing required 'id' in GitHub repository payload.")

    name = repo_data.get('name') or ''
    full_name = repo_data.get('full_name') or ''

    owner_data = repo_data.get('owner')
    if isinstance(owner_data, dict):
        owner = owner_data.get('login') or ''
    elif isinstance(owner_data, str):
        owner = owner_data
    else:
        owner = full_name.split('/')[0] if '/' in full_name else ''

    language = repo_data.get('language') or ''
    description = repo_data.get('description') or ''

    if not name or not full_name or not owner:
        raise GitHubDataError("Incomplete repository identification metadata in GitHub response.")

    with transaction.atomic():
        project = Project.objects.select_for_update().filter(github_repo_id=github_repo_id).first()

        if project:
            updated_fields = []
            if project.owner != owner:
                project.owner = owner
                updated_fields.append('owner')
            if project.name != name:
                project.name = name
                updated_fields.append('name')
            if project.full_name != full_name:
                project.full_name = full_name
                updated_fields.append('full_name')
            if project.language != language:
                project.language = language
                updated_fields.append('language')
            if project.description != description:
                project.description = description
                updated_fields.append('description')

            if updated_fields:
                project.save(update_fields=updated_fields)

            return project, False

        project = Project.objects.create(
            github_repo_id=github_repo_id,
            owner=owner,
            name=name,
            full_name=full_name,
            language=language,
            description=description,
        )
        return project, True


def sync_label(label_data: dict | str) -> tuple[IssueLabel | None, bool]:
    """
    Synchronize a single GitHub label into the IssueLabel model.
    Handles dict payloads ({'name': '...', 'color': '...'}) and string names.
    
    Mapping rules:
    - name: label name (globally unique per schema, stripped, max 255 chars)
    - color: label hex color code (stripped, max 50 chars)
    
    Returns (IssueLabel instance or None, created: bool).
    """
    if isinstance(label_data, dict):
        raw_name = label_data.get('name')
        raw_color = label_data.get('color')
    elif isinstance(label_data, str):
        raw_name = label_data
        raw_color = ''
    else:
        return None, False

    name = (raw_name or '').strip()
    if not name:
        return None, False

    color = (raw_color or '').strip()

    with transaction.atomic():
        label = IssueLabel.objects.select_for_update().filter(name=name).first()
        if label:
            if color and label.color != color:
                label.color = color
                label.save(update_fields=['color'])
            return label, False

        label, created = IssueLabel.objects.get_or_create(
            name=name,
            defaults={'color': color},
        )
        return label, created


def sync_issue(project: Project, issue_data: dict) -> tuple[Issue, bool]:
    """
    Synchronize issue metadata into the Issue model and synchronize its labels (M2-T2, M2-T3).
    
    Mapping rules:
    - github_issue_id: issue_data['id'] (immutable unique key)
    - project: Project foreign key
    - number: issue_data['number']
    - title: issue_data.get('title') or ''
    - status: 'closed' if issue_data.get('state') == 'closed' else 'open'
    
    Non-destructive update rule:
    - If Issue exists: updates mutable GitHub metadata ('title', 'status', 'number', 'project').
      DOES NOT overwrite operator-customized fields: 'points', 'difficulty', 'category', 'is_featured'.
    - If Issue is created: uses model defaults (points=50, difficulty='', category='', is_featured=False).
    
    Label synchronization (M2-T3):
    - If 'labels' key is provided in issue_data:
      - Synchronizes each IssueLabel in database (idempotent / unique on name).
      - Associates labels with the issue via M:N relationship (issue.labels.set(...)).
      - Replaces removed labels for this issue without deleting IssueLabel records or affecting other issues.
    
    Returns (issue, created: bool).
    """
    github_issue_id = issue_data.get('id')
    if github_issue_id is None:
        raise GitHubDataError("Missing required 'id' in GitHub issue payload.")

    number = issue_data.get('number')
    if number is None:
        raise GitHubDataError("Missing required 'number' in GitHub issue payload.")

    title = issue_data.get('title') or ''
    github_state = (issue_data.get('state') or 'open').lower()
    status = 'closed' if github_state == 'closed' else 'open'

    with transaction.atomic():
        issue = Issue.objects.select_for_update().filter(github_issue_id=github_issue_id).first()

        if issue:
            updated_fields = []
            if issue.project_id != project.id:
                issue.project = project
                updated_fields.append('project')
            if issue.number != number:
                issue.number = number
                updated_fields.append('number')
            if issue.title != title:
                issue.title = title
                updated_fields.append('title')
            if issue.status != status:
                issue.status = status
                updated_fields.append('status')

            if updated_fields:
                issue.save(update_fields=updated_fields)

            created = False
        else:
            issue = Issue.objects.create(
                github_issue_id=github_issue_id,
                project=project,
                number=number,
                title=title,
                status=status,
            )
            created = True

        if 'labels' in issue_data:
            raw_labels = issue_data.get('labels') or []
            if isinstance(raw_labels, list):
                label_objects = []
                for item in raw_labels:
                    label_obj, _ = sync_label(item)
                    if label_obj is not None:
                        label_objects.append(label_obj)
                issue.labels.set(label_objects)

        return issue, created


def sync_issues_for_project(project: Project, issues_data: list[dict]) -> tuple[int, int]:
    """
    Synchronize a list of issue payloads for a given project.
    Returns (created_count, updated_count).
    """
    created_count = 0
    updated_count = 0

    for issue_data in issues_data:
        # Extra safety check to skip PRs
        if 'pull_request' in issue_data:
            continue

        _, created = sync_issue(project, issue_data)
        if created:
            created_count += 1
        else:
            updated_count += 1

    return created_count, updated_count


def sync_repository_by_name(repo_identifier: str, client: GitHubClient | None = None) -> tuple[Project, bool]:
    """
    Fetch repository by 'owner/name' and synchronize into Project table.
    Returns (project, created: bool).
    """
    owner, repo = parse_repo_identifier(repo_identifier)
    if client is None:
        client = GitHubClient()

    repo_data = client.get_repository(owner, repo)
    return sync_project(repo_data)


def sync_repository_and_issues(
    repo_identifier: str,
    client: GitHubClient | None = None,
    sync_issues_flag: bool = True,
) -> tuple[Project, bool, int, int]:
    """
    Fetch and synchronize repository metadata and all its issues.
    Returns (project, repo_created: bool, issues_created: int, issues_updated: int).
    """
    owner, repo = parse_repo_identifier(repo_identifier)
    if client is None:
        client = GitHubClient()

    repo_data = client.get_repository(owner, repo)
    project, repo_created = sync_project(repo_data)

    issues_created = 0
    issues_updated = 0

    if sync_issues_flag:
        issues_data = client.get_issues(owner, repo, state='all')
        issues_created, issues_updated = sync_issues_for_project(project, issues_data)

    return project, repo_created, issues_created, issues_updated
