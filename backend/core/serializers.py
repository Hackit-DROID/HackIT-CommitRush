from rest_framework import serializers
from core.models import Project, Issue, IssueLabel, Contribution, Participant, PullRequest


class ProjectListSerializer(serializers.ModelSerializer):
    """
    Public serializer for listing tracked repositories (M3-T1).
    """
    class Meta:
        model = Project
        fields = [
            'id',
            'github_repo_id',
            'owner',
            'name',
            'full_name',
            'language',
            'is_enabled',
            'description',
        ]
        read_only_fields = fields


class ProjectDetailSerializer(serializers.ModelSerializer):
    """
    Public serializer for detailed project metadata, issue counts,
    and contribution activity metrics (M3-T2).
    """
    issue_count = serializers.SerializerMethodField()
    open_issue_count = serializers.SerializerMethodField()
    contribution_activity = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            'id',
            'github_repo_id',
            'owner',
            'name',
            'full_name',
            'language',
            'is_enabled',
            'description',
            'issue_count',
            'open_issue_count',
            'contribution_activity',
        ]
        read_only_fields = fields

    def get_issue_count(self, obj: Project) -> int:
        return obj.issues.count()

    def get_open_issue_count(self, obj: Project) -> int:
        return obj.issues.filter(status='open').count()

    def get_contribution_activity(self, obj: Project) -> dict:
        total = Contribution.objects.filter(issue__project=obj).count()
        merged = Contribution.objects.filter(issue__project=obj, status='MERGED').count()
        in_progress = Contribution.objects.filter(
            issue__project=obj,
            status__in=['PENDING', 'QUEUED', 'UNDER_REVIEW', 'APPROVED', 'MERGING']
        ).count()
        return {
            'total_contributions': total,
            'merged_contributions': merged,
            'in_progress_contributions': in_progress,
        }


class IssueListSerializer(serializers.ModelSerializer):
    """
    Public serializer for listing tracked issues (M3-T3).
    Includes canonical github_url, github_number, created_at, and label names per PRD §16.
    """
    project = serializers.CharField(source='project.full_name', read_only=True)
    github_number = serializers.IntegerField(source='number', read_only=True)
    labels = serializers.SerializerMethodField()
    github_url = serializers.SerializerMethodField()

    class Meta:
        model = Issue
        fields = [
            'id',
            'title',
            'project',
            'github_number',
            'points',
            'difficulty',
            'category',
            'status',
            'is_featured',
            'labels',
            'github_url',
            'created_at',
        ]
        read_only_fields = fields

    def get_labels(self, obj: Issue) -> list[str]:
        return [label.name for label in obj.labels.all()]

    def get_github_url(self, obj: Issue) -> str:
        return f"https://github.com/{obj.project.full_name}/issues/{obj.number}"


class IssueDetailSerializer(serializers.ModelSerializer):
    """
    Public serializer for issue detail view (M3-T4).
    Includes canonical github_url, github_number, project metadata, labels, and created_at per PRD §16.
    """
    project = serializers.CharField(source='project.full_name', read_only=True)
    project_id = serializers.IntegerField(source='project.id', read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    github_number = serializers.IntegerField(source='number', read_only=True)
    labels = serializers.SerializerMethodField()
    github_url = serializers.SerializerMethodField()

    class Meta:
        model = Issue
        fields = [
            'id',
            'github_issue_id',
            'title',
            'project',
            'project_id',
            'project_name',
            'github_number',
            'points',
            'difficulty',
            'category',
            'status',
            'is_featured',
            'labels',
            'github_url',
            'created_at',
        ]
        read_only_fields = fields

    def get_labels(self, obj: Issue) -> list[str]:
        return [label.name for label in obj.labels.all()]

    def get_github_url(self, obj: Issue) -> str:
        return f"https://github.com/{obj.project.full_name}/issues/{obj.number}"


class ContributionParticipantSerializer(serializers.ModelSerializer):
    """
    Nested serializer for participant info on contributions.
    """
    class Meta:
        model = Participant
        fields = [
            'id',
            'github_id',
            'github_username',
            'avatar_url',
        ]
        read_only_fields = fields


class ContributionIssueSerializer(serializers.ModelSerializer):
    """
    Nested serializer for issue info on contributions.
    """
    project = serializers.CharField(source='project.full_name', read_only=True)
    github_number = serializers.IntegerField(source='number', read_only=True)
    github_url = serializers.SerializerMethodField()

    class Meta:
        model = Issue
        fields = [
            'id',
            'github_issue_id',
            'title',
            'project',
            'github_number',
            'points',
            'difficulty',
            'category',
            'status',
            'github_url',
        ]
        read_only_fields = fields

    def get_github_url(self, obj: Issue) -> str:
        return f"https://github.com/{obj.project.full_name}/issues/{obj.number}"


class ContributionPullRequestSerializer(serializers.ModelSerializer):
    """
    Nested serializer for pull request info on contributions.
    """
    repo = serializers.CharField(source='repo.full_name', read_only=True)
    github_url = serializers.SerializerMethodField()

    class Meta:
        model = PullRequest
        fields = [
            'id',
            'github_pr_id',
            'number',
            'repo',
            'merged',
            'merged_at',
            'head_sha',
            'github_url',
        ]
        read_only_fields = fields

    def get_github_url(self, obj: PullRequest) -> str:
        return f"https://github.com/{obj.repo.full_name}/pull/{obj.number}"


class ContributionSerializer(serializers.ModelSerializer):
    """
    Serializer for Contribution detail and list views (PRD §16, Plan M5-T4).
    Includes nested participant, issue, and pull request information,
    state machine statuses, and retry/audit timestamps.
    """
    participant = ContributionParticipantSerializer(read_only=True)
    issue = ContributionIssueSerializer(read_only=True)
    pull_request = ContributionPullRequestSerializer(read_only=True)

    class Meta:
        model = Contribution
        fields = [
            'id',
            'participant',
            'issue',
            'pull_request',
            'status',
            'sub_status',
            'is_priority',
            'retry_count',
            'flagged_reason',
            'approved_at',
            'merged_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class AdminPointAdjustmentSerializer(serializers.Serializer):
    """
    Serializer for admin manual point adjustments (PRD §14, §16, Plan M6-T6).
    Validates participant existence, non-zero integer delta, and required reason.
    """
    participant_id = serializers.IntegerField(required=True, min_value=1)
    points = serializers.IntegerField(required=True)
    reason = serializers.CharField(required=True, min_length=1, max_length=1000)

    def validate_points(self, value: int) -> int:
        if value == 0:
            raise serializers.ValidationError("Point adjustment delta must be non-zero.")
        return value

    def validate_reason(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("A non-empty reason is required for manual point adjustments.")
        return cleaned

    def validate_participant_id(self, value: int) -> int:
        if not Participant.objects.filter(id=value).exists():
            raise serializers.ValidationError(f"Participant with ID {value} does not exist.")
        return value


# =============================================================================
# M7 Leaderboard, Dashboard & Public Profile Serializers (PRD §16, §19)
# =============================================================================

class LeaderboardEntrySerializer(serializers.Serializer):
    """
    Public serializer for individual leaderboard entries (PRD §8.6, §16, Plan M7-T1).
    """
    rank = serializers.IntegerField(read_only=True)
    participant_id = serializers.IntegerField(read_only=True)
    github_username = serializers.CharField(read_only=True)
    avatar_url = serializers.CharField(read_only=True, allow_null=True)
    total_points = serializers.IntegerField(read_only=True)
    merged_count = serializers.IntegerField(read_only=True)


class DailyUsageSerializer(serializers.Serializer):
    """
    Serializer for daily contribution and point usage (PRD §14, §16, Plan M7-T3).
    """
    date = serializers.DateField(read_only=True)
    contributions_count = serializers.IntegerField(read_only=True)
    max_contributions = serializers.IntegerField(read_only=True)
    points_count = serializers.IntegerField(read_only=True)
    max_points = serializers.IntegerField(read_only=True)


class DashboardSerializer(serializers.Serializer):
    """
    Aggregated participant dashboard serializer serving full state in 1 round trip (PRD §16, Plan M7-T3).
    """
    participant = ContributionParticipantSerializer(read_only=True)
    rank = serializers.IntegerField(read_only=True, allow_null=True)
    total_points = serializers.IntegerField(read_only=True)
    merged_count = serializers.IntegerField(read_only=True)
    daily_usage = DailyUsageSerializer(read_only=True)
    in_progress_contributions = ContributionSerializer(many=True, read_only=True)
    recent_activity = ContributionSerializer(many=True, read_only=True)


class PublicProfileStatsSerializer(serializers.Serializer):
    """
    Public aggregate contribution metrics for a participant profile (PRD §16, §19, Plan M7-T4).
    """
    total_contributions = serializers.IntegerField(read_only=True)
    merged_contributions = serializers.IntegerField(read_only=True)
    in_progress_contributions = serializers.IntegerField(read_only=True)
    rejected_contributions = serializers.IntegerField(read_only=True)


class PublicProfileContributionSerializer(serializers.Serializer):
    """
    Safe public serializer for a participant's merged contribution (PRD §16, §19, Plan M7-T4).
    Excludes private workflow metadata, audit reasons, or tokens.
    """
    id = serializers.IntegerField(read_only=True)
    project_name = serializers.CharField(read_only=True)
    issue_number = serializers.IntegerField(read_only=True)
    issue_title = serializers.CharField(read_only=True)
    points = serializers.IntegerField(read_only=True)
    merged_at = serializers.DateTimeField(read_only=True, allow_null=True)
    github_url = serializers.CharField(read_only=True)


class PublicProfileSerializer(serializers.Serializer):
    """
    Safe public contributor profile serializer (PRD §16, §19, Plan M7-T4).
    Whitelists only public contributor identity, rank, and aggregate metrics.
    """
    id = serializers.IntegerField(read_only=True)
    github_id = serializers.IntegerField(read_only=True)
    github_username = serializers.CharField(read_only=True)
    avatar_url = serializers.CharField(read_only=True, allow_null=True)
    total_points = serializers.IntegerField(read_only=True)
    merged_count = serializers.IntegerField(read_only=True)
    rank = serializers.IntegerField(read_only=True, allow_null=True)
    stats = PublicProfileStatsSerializer(read_only=True)
    recent_merged_contributions = PublicProfileContributionSerializer(many=True, read_only=True)


# =============================================================================
# M7-T5 Event Statistics Serializers (PRD §8.6, §16, §23)
# =============================================================================

class SystemStatusSerializer(serializers.Serializer):
    merge_paused = serializers.BooleanField(read_only=True)
    validation_paused = serializers.BooleanField(read_only=True)
    submissions_paused = serializers.BooleanField(read_only=True)
    leaderboard_frozen = serializers.BooleanField(read_only=True)


class StatsParticipantsSerializer(serializers.Serializer):
    total = serializers.IntegerField(read_only=True)
    active = serializers.IntegerField(read_only=True)


class StatsPullRequestsSerializer(serializers.Serializer):
    total = serializers.IntegerField(read_only=True)
    merged = serializers.IntegerField(read_only=True)


class StatsContributionsSerializer(serializers.Serializer):
    total = serializers.IntegerField(read_only=True)
    by_status = serializers.DictField(child=serializers.IntegerField(), read_only=True)


class StatsPointsSerializer(serializers.Serializer):
    total_awarded = serializers.IntegerField(read_only=True)
    points_past_hour = serializers.IntegerField(read_only=True)


class StatsRatesSerializer(serializers.Serializer):
    merges_past_hour = serializers.IntegerField(read_only=True)
    points_past_hour = serializers.IntegerField(read_only=True)


class EventStatsSerializer(serializers.Serializer):
    """
    Public aggregate event stats serializer (PRD §8.6, §16, §23, Plan M7-T5).
    """
    event_status = serializers.CharField(read_only=True)
    system_status = SystemStatusSerializer(read_only=True)
    participants = StatsParticipantsSerializer(read_only=True)
    pull_requests = StatsPullRequestsSerializer(read_only=True)
    contributions = StatsContributionsSerializer(read_only=True)
    points = StatsPointsSerializer(read_only=True)
    rates = StatsRatesSerializer(read_only=True)
    updated_at = serializers.CharField(read_only=True)

