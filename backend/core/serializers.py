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
            'retry_count',
            'flagged_reason',
            'approved_at',
            'merged_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields
