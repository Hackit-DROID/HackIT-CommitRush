from django.conf import settings
from django.db import IntegrityError, models
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.utils import timezone


class Participant(models.Model):
    """
    Extends Django User with event profile.
    PRD §15: Key fields: github_id (unique), github_username, avatar_url, is_suspended,
    total_points (denormalized, recomputed by trigger/signal). 1:1 with User.
    """
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='participant',
    )
    github_id = models.BigIntegerField(
        unique=True,
        help_text='Immutable GitHub User ID',
    )
    github_username = models.CharField(
        max_length=255,
        help_text='GitHub username cached at login',
    )
    avatar_url = models.URLField(
        max_length=1024,
        blank=True,
        null=True,
        help_text='Avatar URL cached from GitHub profile',
    )
    is_suspended = models.BooleanField(
        default=False,
        help_text='Suspended participants cannot be awarded points',
    )
    total_points = models.IntegerField(
        default=0,
        help_text='Denormalized total points counter',
    )
    merged_count = models.IntegerField(
        default=0,
        help_text='Denormalized count of merged contributions (PRD §15)',
    )

    class Meta:
        indexes = [
            models.Index(fields=['-total_points'], name='participant_total_pts_idx'),
            models.Index(fields=['-total_points', '-merged_count', 'id'], name='participant_leaderboard_idx'),
            models.Index(fields=['github_username'], name='participant_username_idx'),
        ]

    def __str__(self):
        return f"{self.github_username} (ID: {self.github_id})"


class Project(models.Model):
    """
    Tracked repository.
    PRD §15: Key fields: github_repo_id (unique), owner, name, full_name,
    language, is_enabled, description. 1:N Issue.
    """
    github_repo_id = models.BigIntegerField(
        unique=True,
        help_text='Immutable GitHub Repository ID',
    )
    owner = models.CharField(
        max_length=255,
        help_text='GitHub repository owner/organization',
    )
    name = models.CharField(
        max_length=255,
        help_text='GitHub repository name',
    )
    full_name = models.CharField(
        max_length=512,
        help_text='GitHub full repository name (owner/name)',
    )
    language = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text='Primary programming language',
    )
    is_enabled = models.BooleanField(
        default=True,
        help_text='Whether this project is active for event submissions',
    )
    description = models.TextField(
        blank=True,
        default='',
        help_text='Repository description',
    )

    class Meta:
        indexes = [
            models.Index(fields=['is_enabled'], name='project_is_enabled_idx'),
        ]

    def __str__(self):
        return self.full_name


class IssueLabel(models.Model):
    """
    GitHub label cache.
    PRD §15: Key fields: name (unique), color. M:N Issue.
    """
    name = models.CharField(
        max_length=255,
        unique=True,
        help_text='GitHub label name',
    )
    color = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text='Label hex color code',
    )

    def __str__(self):
        return self.name


class Issue(models.Model):
    """
    Tracked GitHub issue.
    PRD §15: Key fields: github_issue_id (unique), project_id, number, title,
    points, difficulty, category, status (open/closed/disabled), is_featured.
    FK Project; M:N IssueLabel.
    """
    github_issue_id = models.BigIntegerField(
        unique=True,
        help_text='Immutable GitHub Issue ID',
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='issues',
        help_text='Associated tracked project',
    )
    number = models.IntegerField(
        help_text='Issue number in the GitHub repository',
    )
    title = models.CharField(
        max_length=1024,
        help_text='Issue title',
    )
    points = models.IntegerField(
        default=50,
        help_text='Points awarded for resolving this issue',
    )
    difficulty = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text='Difficulty tier (e.g., beginner, intermediate, advanced)',
    )
    category = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text='Issue category/domain (e.g., backend, frontend, docs)',
    )
    status = models.CharField(
        max_length=50,
        default='open',
        help_text='Issue status: open, closed, or disabled',
    )
    is_featured = models.BooleanField(
        default=False,
        help_text='Whether this issue is highlighted in explorer UI',
    )
    labels = models.ManyToManyField(
        IssueLabel,
        blank=True,
        related_name='issues',
        help_text='Cached GitHub issue labels',
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        help_text='Issue creation timestamp',
    )
    created_by_github_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text='GitHub user ID of the issue creator (PRD §22)',
    )

    class Meta:
        indexes = [
            models.Index(fields=['project', 'status'], name='issue_project_status_idx'),
            models.Index(fields=['points'], name='issue_points_idx'),
            models.Index(fields=['difficulty'], name='issue_difficulty_idx'),
            models.Index(fields=['-created_at'], name='issue_created_at_idx'),
        ]

    def __str__(self):
        return f"#{self.number} {self.title} ({self.project.full_name})"


class PullRequest(models.Model):
    """
    GitHub PR cache.
    PRD §15: Key fields: github_pr_id (unique), repo_id, number, author_github_id,
    merged, merged_at, head_sha. FK Project, FK Participant (nullable if author not registered).
    """
    github_pr_id = models.BigIntegerField(
        unique=True,
        help_text='Immutable GitHub Pull Request ID',
    )
    repo = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name='pull_requests',
        help_text='Tracked project the PR was submitted against',
    )
    number = models.IntegerField(
        help_text='Pull request number in repository',
    )
    author_github_id = models.BigIntegerField(
        help_text='GitHub user ID of the PR author',
    )
    author_participant = models.ForeignKey(
        Participant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pull_requests',
        help_text='Registered participant corresponding to PR author, if exists',
    )
    merged = models.BooleanField(
        default=False,
        help_text='Whether the pull request is merged on GitHub',
    )
    merged_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamp when merged on GitHub',
    )
    head_sha = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text='Head commit SHA of the pull request branch',
    )
    base_branch = models.CharField(
        max_length=100,
        blank=True,
        default='main',
        help_text='Target base branch of the pull request (normally main)',
    )

    class Meta:
        indexes = [
            models.Index(fields=['repo', 'number'], name='pr_repo_number_idx'),
        ]

    def __str__(self):
        return f"PR #{self.number} ({self.repo.full_name})"


class Contribution(models.Model):
    """
    Core entity — CommitRush's view of a PR-against-tracked-issue.
    PRD §15: Key fields: participant_id, issue_id, pull_request_id, status, sub_status,
    locked_at, retry_count, flagged_reason, approved_at, merged_at, created_at, updated_at.
    FK Participant, FK Issue, FK PullRequest.
    unique(participant_id, pull_request_id).
    """
    participant = models.ForeignKey(
        Participant,
        on_delete=models.CASCADE,
        related_name='contributions',
        help_text='Participant who authored the contribution',
    )
    issue = models.ForeignKey(
        Issue,
        on_delete=models.CASCADE,
        related_name='contributions',
        help_text='Tracked issue being addressed',
    )
    pull_request = models.ForeignKey(
        PullRequest,
        on_delete=models.CASCADE,
        related_name='contributions',
        help_text='Pull request associated with this contribution',
    )
    status = models.CharField(
        max_length=50,
        default='PENDING',
        help_text='State machine status: PENDING, QUEUED, UNDER_REVIEW, APPROVED, MERGING, MERGED, REJECTED, FLAGGED, RETRY',
    )
    sub_status = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text='Sub-status or phase (e.g., VALIDATING)',
    )
    locked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamp when worker locked contribution for processing',
    )
    retry_count = models.IntegerField(
        default=0,
        help_text='Number of transient retry attempts',
    )
    flagged_reason = models.TextField(
        blank=True,
        default='',
        help_text='Explanation if held for admin review',
    )
    is_priority = models.BooleanField(
        default=False,
        help_text='Admin priority override for merge queue processing (PRD §12.3)',
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamp when validation succeeded and approved for merge queue',
    )
    merged_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamp when confirmed merged',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='Record creation timestamp',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text='Record last updated timestamp',
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['participant', 'pull_request'],
                name='unique_participant_pull_request',
            ),
        ]
        indexes = [
            models.Index(fields=['status'], name='contrib_status_idx'),
            models.Index(fields=['issue'], name='contrib_issue_idx'),
            models.Index(fields=['-is_priority', 'approved_at', 'id'], name='contrib_merge_prio_idx'),
            models.Index(fields=['participant', '-created_at'], name='contrib_part_created_idx'),
        ]

    def __str__(self):
        return f"Contribution {self.id} ({self.participant.github_username} - {self.status})"


class PointTransaction(models.Model):
    """
    Immutable ledger of point events.
    PRD §15: Key fields: contribution_id, participant_id, points,
    status (AWARDED/DEFERRED/REVOKED/ADMIN_ADJUST), reason, created_at.
    FK Contribution (nullable for admin adjustments), FK Participant.
    unique(contribution_id) where status=AWARDED.
    """
    contribution = models.ForeignKey(
        Contribution,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='point_transactions',
        help_text='Associated contribution (nullable for admin adjustments)',
    )
    participant = models.ForeignKey(
        Participant,
        on_delete=models.CASCADE,
        related_name='point_transactions',
        help_text='Participant receiving or deducted points',
    )
    points = models.IntegerField(
        help_text='Point delta (positive, negative, or zero for deferred)',
    )
    status = models.CharField(
        max_length=50,
        help_text='Transaction status: AWARDED, DEFERRED, REVOKED, or ADMIN_ADJUST',
    )
    reason = models.TextField(
        blank=True,
        default='',
        help_text='Reason for transaction or audit note',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='Ledger entry timestamp',
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['contribution'],
                condition=models.Q(status='AWARDED'),
                name='unique_awarded_point_transaction_per_contribution',
            ),
        ]
        indexes = [
            models.Index(fields=['participant', 'created_at'], name='pt_participant_created_idx'),
        ]

    def __str__(self):
        return f"PT {self.id}: {self.points} pts ({self.status}) for {self.participant.github_username}"


class DailyContributionUsage(models.Model):
    """
    Per-participant-per-day counters for daily limit enforcement.
    PRD §15: Key fields: participant_id, date, contributions_count, points_count.
    FK Participant. unique(participant_id, date).
    """
    participant = models.ForeignKey(
        Participant,
        on_delete=models.CASCADE,
        related_name='daily_usages',
        help_text='Participant tracked',
    )
    date = models.DateField(
        help_text='Date of activity (UTC)',
    )
    contributions_count = models.IntegerField(
        default=0,
        help_text='Number of credited contributions on this date',
    )
    points_count = models.IntegerField(
        default=0,
        help_text='Total points awarded on this date',
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['participant', 'date'],
                name='unique_participant_date_usage',
            ),
        ]

    def __str__(self):
        return f"Usage for {self.participant.github_username} on {self.date}"


class ScoringBreakdown(models.Model):
    """
    Auditable, reproducible record of points calculation for a contribution.
    PRD §14, §15, Section 9, 10, 11.
    Answers: "Why did this PR receive X points?"
    """
    contribution = models.OneToOneField(
        Contribution,
        on_delete=models.CASCADE,
        related_name='scoring_breakdown',
        help_text='Associated contribution',
    )
    point_transaction = models.OneToOneField(
        PointTransaction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='scoring_breakdown',
        help_text='Linked point transaction in ledger',
    )
    base_points = models.IntegerField(
        help_text='Initial base points evaluated from issue',
    )
    category = models.CharField(
        max_length=100,
        help_text='Classification category slug (e.g. feature, bug, docs)',
    )
    category_label = models.CharField(
        max_length=100,
        help_text='Human-readable category label (e.g. Feature, Bug Fix, Documentation)',
    )
    multiplier = models.FloatField(
        default=1.0,
        help_text='Configured multiplier applied to base points',
    )
    calculated_points = models.IntegerField(
        help_text='Points after multiplying base points: round(base_points * multiplier)',
    )
    per_pr_cap = models.IntegerField(
        null=True,
        blank=True,
        help_text='Per-PR point cap from EventConfig (if enabled)',
    )
    points_after_pr_cap = models.IntegerField(
        help_text='Calculated points capped at per_pr_cap',
    )
    daily_points_cap = models.IntegerField(
        help_text='Daily points cap in effect at evaluation',
    )
    daily_points_before = models.IntegerField(
        default=0,
        help_text='Points already earned by participant on this date before this PR',
    )
    daily_allowance_remaining = models.IntegerField(
        default=0,
        help_text='Remaining daily point allowance before this PR',
    )
    cap_applied = models.CharField(
        max_length=100,
        default='Not reached',
        help_text='Description of cap applied: Not reached, Daily limit, Daily contribution limit, Per-PR cap',
    )
    final_awarded_points = models.IntegerField(
        default=0,
        help_text='Actual points awarded to participant ledger balance',
    )
    farming_signals = models.JSONField(
        default=dict,
        blank=True,
        help_text='Farming pattern and velocity heuristics detected for admin review',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='Calculation timestamp',
    )

    class Meta:
        indexes = [
            models.Index(fields=['created_at'], name='scoring_created_at_idx'),
            models.Index(fields=['category'], name='scoring_category_idx'),
        ]

    def __str__(self):
        return f"Scoring for Contribution #{self.contribution_id}: {self.final_awarded_points} pts ({self.category_label}, {self.multiplier}x)"


class EventConfig(models.Model):
    """
    Singleton runtime config.
    PRD §15: Key fields: merge_concurrency, max_contributions_per_day, max_points_per_day,
    merge_paused, validation_paused, submissions_paused, leaderboard_frozen, event_status.
    """
    merge_concurrency = models.IntegerField(
        default=5,
        help_text='Maximum concurrent merge-bot operations',
    )
    max_contributions_per_day = models.IntegerField(
        default=5,
        help_text='Daily contribution credit cap per participant',
    )
    max_points_per_day = models.IntegerField(
        default=120,
        help_text='Daily points cap per participant (HackIT CommitRush rule: 120 points/day)',
    )
    per_pr_max_points = models.IntegerField(
        default=50,
        help_text='Maximum points allowed per single pull request (Master=50)',
    )
    category_multipliers = models.JSONField(
        default=dict,
        blank=True,
        help_text='Configurable multipliers by category (e.g. {"feature": 1.5, "bug": 1.0, "docs": 0.8})',
    )
    allow_partial_daily_points = models.BooleanField(
        default=False,
        help_text='Whether to award partial points up to remaining daily allowance (False: PR either earns full score or 0 if exceeding 120 cap)',
    )
    target_branch = models.CharField(
        max_length=100,
        default='main',
        help_text='Designated target branch for contributions (normally main)',
    )
    event_start_date = models.DateField(
        null=True,
        blank=True,
        help_text='Official event start date (IST)',
    )
    event_end_date = models.DateField(
        null=True,
        blank=True,
        help_text='Official event end date (IST)',
    )
    merge_paused = models.BooleanField(
        default=False,
        help_text='Emergency control: pause all merge queue operations',
    )
    validation_paused = models.BooleanField(
        default=False,
        help_text='Emergency control: pause contribution validation pipeline',
    )
    submissions_paused = models.BooleanField(
        default=False,
        help_text='Emergency control: pause accepting new webhook submissions',
    )
    leaderboard_frozen = models.BooleanField(
        default=False,
        help_text='Emergency control: freeze public leaderboard rankings',
    )
    leaderboard_frozen_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamp when leaderboard was frozen',
    )
    event_status = models.CharField(
        max_length=50,
        default='pending',
        help_text='Event status (e.g., pending, active, ended)',
    )

    def __str__(self):
        return f"EventConfig (Status: {self.event_status})"

    def get_category_multiplier(self, category_key: str) -> float:
        from core.categories import DEFAULT_CATEGORY_MULTIPLIERS
        key = (category_key or '').lower()
        if self.category_multipliers and key in self.category_multipliers:
            try:
                val = float(self.category_multipliers[key])
                if val > 0:
                    return val
            except (ValueError, TypeError):
                pass
        # If no custom multipliers are defined, default multiplier is 1.0 so difficulty values (5, 10, 20, 30, 50) are preserved
        if not self.category_multipliers:
            return 1.0
        return DEFAULT_CATEGORY_MULTIPLIERS.get(key, 1.0)

    def save(self, *args, **kwargs):
        self.pk = 1
        freeze_toggled = False
        if self.__class__.objects.filter(pk=1).exists():
            self._state.adding = False
            kwargs.pop('force_insert', None)
            existing = self.__class__.objects.filter(pk=1).values('leaderboard_frozen', 'leaderboard_frozen_at').first()
            if existing:
                if self.leaderboard_frozen and not existing['leaderboard_frozen']:
                    self.leaderboard_frozen_at = timezone.now()
                    freeze_toggled = True
                elif not self.leaderboard_frozen and existing['leaderboard_frozen']:
                    self.leaderboard_frozen_at = None
                    freeze_toggled = True
        else:
            if self.leaderboard_frozen and not self.leaderboard_frozen_at:
                self.leaderboard_frozen_at = timezone.now()
                freeze_toggled = True
        super().save(*args, **kwargs)

        if freeze_toggled:
            try:
                from core.leaderboard import invalidate_frozen_leaderboard_cache, invalidate_leaderboard_cache
                invalidate_frozen_leaderboard_cache()
                invalidate_leaderboard_cache()
            except Exception:
                pass

    def delete(self, *args, **kwargs):
        raise IntegrityError("The EventConfig singleton instance cannot be deleted.")

    @classmethod
    def get_solo(cls):
        """
        Retrieve or initialize the singleton configuration row with primary key 1.
        """
        from core.categories import DEFAULT_CATEGORY_MULTIPLIERS
        obj, _ = cls.objects.get_or_create(
            pk=1,
            defaults={
                'merge_concurrency': 5,
                'max_contributions_per_day': 5,
                'max_points_per_day': 500,
                'per_pr_max_points': 100,
                'category_multipliers': DEFAULT_CATEGORY_MULTIPLIERS,
                'allow_partial_daily_points': True,
                'merge_paused': False,
                'validation_paused': False,
                'submissions_paused': False,
                'leaderboard_frozen': False,
                'leaderboard_frozen_at': None,
                'event_status': 'pending',
            },
        )
        return obj

    @classmethod
    def load(cls):
        """
        Alias for get_solo().
        """
        return cls.get_solo()


@receiver(pre_delete, sender=EventConfig)
def prevent_event_config_deletion(sender, instance, **kwargs):
    raise IntegrityError("The EventConfig singleton instance cannot be deleted.")



class WebhookEvent(models.Model):
    """
    Idempotency + audit log for inbound webhooks.
    PRD §15: Key fields: delivery_id (unique), event_type, payload (JSONB),
    processed_at, processing_error.
    """
    delivery_id = models.CharField(
        max_length=255,
        unique=True,
        help_text='GitHub X-GitHub-Delivery header identifier',
    )
    event_type = models.CharField(
        max_length=100,
        help_text='GitHub event type (e.g., pull_request, issues)',
    )
    payload = models.JSONField(
        help_text='Raw webhook JSON payload from GitHub',
    )
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Timestamp when asynchronous processing completed',
    )
    processing_error = models.TextField(
        blank=True,
        default='',
        help_text='Error details if processing failed',
    )

    def __str__(self):
        return f"Webhook {self.event_type} ({self.delivery_id})"


class AuditLog(models.Model):
    """
    Admin/system action trail.
    PRD §15: Key fields: actor (nullable=system), action, target_type,
    target_id, details (JSONB), created_at.
    """
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        help_text='User who performed action, or null if automated system action',
    )
    action = models.CharField(
        max_length=255,
        help_text='Action identifier (e.g., admin_point_adjustment, force_merge)',
    )
    target_type = models.CharField(
        max_length=100,
        help_text='Target entity type (e.g., Contribution, Participant)',
    )
    target_id = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Target entity identifier',
    )
    details = models.JSONField(
        default=dict,
        blank=True,
        help_text='Structured metadata describing changes or context',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='Audit log timestamp',
    )

    class Meta:
        indexes = [
            models.Index(fields=['target_type', 'target_id'], name='auditlog_target_idx'),
        ]

    def __str__(self):
        actor_name = self.actor.username if self.actor else 'SYSTEM'
        return f"[{self.created_at}] {actor_name} -> {self.action} on {self.target_type}:{self.target_id}"
