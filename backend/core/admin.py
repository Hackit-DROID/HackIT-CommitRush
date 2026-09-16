import logging
from django.contrib import admin, messages
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.db.models import Count

from core.models import (
    Participant,
    Project,
    Issue,
    IssueLabel,
    PullRequest,
    Contribution,
    PointTransaction,
    DailyContributionUsage,
    EventConfig,
    WebhookEvent,
    AuditLog,
)
from core.audit import log_audit_event
from core.points import award_points_for_contribution
from core.state_machine import transition_contribution
from core.tasks import sync_repository_task, validate_contribution_task

logger = logging.getLogger(__name__)


# =============================================================================
# M8-T1: Participant Admin
# =============================================================================

@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'github_username',
        'github_id',
        'total_points',
        'merged_count',
        'is_suspended',
        'flagged_activity_count',
        'user',
    )
    list_filter = ('is_suspended',)
    search_fields = (
        'github_username',
        'github_id',
        'user__username',
        'user__email',
    )
    readonly_fields = (
        'github_id',
        'total_points',
        'merged_count',
        'avatar_preview',
        'flagged_activity_count',
    )
    fieldsets = (
        ('Identity', {
            'fields': ('user', 'github_id', 'github_username', 'avatar_url', 'avatar_preview'),
        }),
        ('Status & Standing', {
            'fields': ('is_suspended', 'total_points', 'merged_count', 'flagged_activity_count'),
        }),
    )
    actions = ['suspend_participants', 'unsuspend_participants']

    def avatar_preview(self, obj):
        if obj.avatar_url:
            return format_html('<img src="{}" width="40" height="40" style="border-radius: 50%;" />', obj.avatar_url)
        return "-"
    avatar_preview.short_description = "Avatar Preview"

    def flagged_activity_count(self, obj):
        count = obj.contributions.filter(status='FLAGGED').count()
        if count > 0:
            return format_html('<b style="color: #ef4444;">{} flagged</b>', count)
        return "0"
    flagged_activity_count.short_description = "Flagged PRs"

    @admin.action(description="Suspend selected participants (blocks points, records activity)")
    def suspend_participants(self, request, queryset):
        updated = 0
        for participant in queryset:
            if not participant.is_suspended:
                participant.is_suspended = True
                participant.save(update_fields=['is_suspended'])
                log_audit_event(
                    actor=request.user,
                    action='participant_suspended',
                    target_type='Participant',
                    target_id=participant.id,
                    details={'github_username': participant.github_username, 'reason': 'Admin action via Django Admin'},
                )
                updated += 1
        self.message_user(request, f"Successfully suspended {updated} participant(s).", messages.SUCCESS)

    @admin.action(description="Unsuspend selected participants")
    def unsuspend_participants(self, request, queryset):
        updated = 0
        for participant in queryset:
            if participant.is_suspended:
                participant.is_suspended = False
                participant.save(update_fields=['is_suspended'])
                log_audit_event(
                    actor=request.user,
                    action='participant_unsuspended',
                    target_type='Participant',
                    target_id=participant.id,
                    details={'github_username': participant.github_username, 'reason': 'Admin action via Django Admin'},
                )
                updated += 1
        self.message_user(request, f"Successfully unsuspended {updated} participant(s).", messages.SUCCESS)

    def save_model(self, request, obj, form, change):
        if change and 'is_suspended' in form.changed_data:
            action = 'participant_suspended' if obj.is_suspended else 'participant_unsuspended'
            log_audit_event(
                actor=request.user,
                action=action,
                target_type='Participant',
                target_id=obj.id,
                details={'github_username': obj.github_username, 'source': 'admin_form_edit'},
            )
        super().save_model(request, obj, form, change)


# =============================================================================
# M8-T1: Project Admin
# =============================================================================

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'full_name',
        'language',
        'is_enabled',
        'issues_count',
        'contributions_count',
    )
    list_filter = ('is_enabled', 'language')
    search_fields = ('full_name', 'owner', 'name', 'language')
    readonly_fields = ('github_repo_id', 'issues_count', 'contributions_count')
    fieldsets = (
        ('Repository Details', {
            'fields': ('github_repo_id', 'owner', 'name', 'full_name', 'language', 'description'),
        }),
        ('Settings & Stats', {
            'fields': ('is_enabled', 'issues_count', 'contributions_count'),
        }),
    )
    actions = ['enable_projects', 'disable_projects', 'sync_projects_now']

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _issue_count=Count('issues', distinct=True),
            _pr_count=Count('pull_requests', distinct=True),
        )

    def issues_count(self, obj):
        return getattr(obj, '_issue_count', obj.issues.count())
    issues_count.short_description = "Issues"
    issues_count.admin_order_field = '_issue_count'

    def contributions_count(self, obj):
        return getattr(obj, '_pr_count', obj.pull_requests.count())
    contributions_count.short_description = "PRs Tracked"
    contributions_count.admin_order_field = '_pr_count'

    @admin.action(description="Enable selected projects for event submissions")
    def enable_projects(self, request, queryset):
        count = 0
        for project in queryset:
            if not project.is_enabled:
                project.is_enabled = True
                project.save(update_fields=['is_enabled'])
                log_audit_event(
                    actor=request.user,
                    action='project_enabled',
                    target_type='Project',
                    target_id=project.id,
                    details={'full_name': project.full_name},
                )
                count += 1
        self.message_user(request, f"Enabled {count} project(s).", messages.SUCCESS)

    @admin.action(description="Disable selected projects (stops new submissions)")
    def disable_projects(self, request, queryset):
        count = 0
        for project in queryset:
            if project.is_enabled:
                project.is_enabled = False
                project.save(update_fields=['is_enabled'])
                log_audit_event(
                    actor=request.user,
                    action='project_disabled',
                    target_type='Project',
                    target_id=project.id,
                    details={'full_name': project.full_name},
                )
                count += 1
        self.message_user(request, f"Disabled {count} project(s).", messages.SUCCESS)

    @admin.action(description="Sync selected projects from GitHub now (enqueues Celery task)")
    def sync_projects_now(self, request, queryset):
        enqueued = 0
        for project in queryset:
            sync_repository_task.delay(project.full_name)
            log_audit_event(
                actor=request.user,
                action='project_sync_triggered',
                target_type='Project',
                target_id=project.id,
                details={'full_name': project.full_name, 'queue': 'sync'},
            )
            enqueued += 1
        self.message_user(
            request,
            f"Enqueued background GitHub sync for {enqueued} repository/repositories on the 'sync' queue.",
            messages.INFO,
        )

    def save_model(self, request, obj, form, change):
        if change and 'is_enabled' in form.changed_data:
            action = 'project_enabled' if obj.is_enabled else 'project_disabled'
            log_audit_event(
                actor=request.user,
                action=action,
                target_type='Project',
                target_id=obj.id,
                details={'full_name': obj.full_name, 'source': 'admin_form_edit'},
            )
        super().save_model(request, obj, form, change)


# =============================================================================
# M8-T1: Issue Admin
# =============================================================================

@admin.register(Issue)
class IssueAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'number',
        'title',
        'project',
        'points',
        'difficulty',
        'category',
        'status',
        'is_featured',
    )
    list_filter = ('status', 'difficulty', 'category', 'is_featured', 'project')
    search_fields = ('title', 'number', 'project__full_name', 'github_issue_id')
    raw_id_fields = ('project',)
    filter_horizontal = ('labels',)
    readonly_fields = ('github_issue_id', 'number', 'created_by_github_id', 'created_at')
    fieldsets = (
        ('GitHub Authoritative Metadata', {
            'fields': ('github_issue_id', 'project', 'number', 'title', 'created_by_github_id', 'created_at', 'labels'),
        }),
        ('CommitRush Configuration', {
            'fields': ('points', 'difficulty', 'category', 'status', 'is_featured'),
        }),
    )
    actions = [
        'enable_issues',
        'disable_issues',
        'mark_as_invalid',
        'feature_issues',
        'unfeature_issues',
        'sync_parent_projects_now',
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('project')

    @admin.action(description="Enable selected issues ('open')")
    def enable_issues(self, request, queryset):
        updated = 0
        for issue in queryset:
            if issue.status != 'open':
                old_status = issue.status
                issue.status = 'open'
                issue.save(update_fields=['status'])
                log_audit_event(
                    actor=request.user,
                    action='issue_enabled',
                    target_type='Issue',
                    target_id=issue.id,
                    details={'title': issue.title, 'old_status': old_status, 'new_status': 'open'},
                )
                updated += 1
        self.message_user(request, f"Enabled {updated} issue(s).", messages.SUCCESS)

    @admin.action(description="Disable selected issues ('disabled')")
    def disable_issues(self, request, queryset):
        updated = 0
        for issue in queryset:
            if issue.status != 'disabled':
                old_status = issue.status
                issue.status = 'disabled'
                issue.save(update_fields=['status'])
                log_audit_event(
                    actor=request.user,
                    action='issue_disabled',
                    target_type='Issue',
                    target_id=issue.id,
                    details={'title': issue.title, 'old_status': old_status, 'new_status': 'disabled'},
                )
                updated += 1
        self.message_user(request, f"Disabled {updated} issue(s).", messages.SUCCESS)

    @admin.action(description="Mark selected issues as invalid (excludes from discovery)")
    def mark_as_invalid(self, request, queryset):
        updated = 0
        for issue in queryset:
            if issue.status != 'disabled':
                old_status = issue.status
                issue.status = 'disabled'
                issue.save(update_fields=['status'])
                log_audit_event(
                    actor=request.user,
                    action='issue_marked_invalid',
                    target_type='Issue',
                    target_id=issue.id,
                    details={'title': issue.title, 'old_status': old_status, 'new_status': 'disabled'},
                )
                updated += 1
        self.message_user(request, f"Marked {updated} issue(s) as invalid/disabled.", messages.SUCCESS)

    @admin.action(description="Feature selected issues")
    def feature_issues(self, request, queryset):
        updated = 0
        for issue in queryset:
            if not issue.is_featured:
                issue.is_featured = True
                issue.save(update_fields=['is_featured'])
                log_audit_event(
                    actor=request.user,
                    action='issue_featured',
                    target_type='Issue',
                    target_id=issue.id,
                    details={'title': issue.title},
                )
                updated += 1
        self.message_user(request, f"Featured {updated} issue(s).", messages.SUCCESS)

    @admin.action(description="Unfeature selected issues")
    def unfeature_issues(self, request, queryset):
        updated = 0
        for issue in queryset:
            if issue.is_featured:
                issue.is_featured = False
                issue.save(update_fields=['is_featured'])
                log_audit_event(
                    actor=request.user,
                    action='issue_unfeatured',
                    target_type='Issue',
                    target_id=issue.id,
                    details={'title': issue.title},
                )
                updated += 1
        self.message_user(request, f"Unfeatured {updated} issue(s).", messages.SUCCESS)

    @admin.action(description="Sync parent projects from GitHub now (enqueues Celery sync task)")
    def sync_parent_projects_now(self, request, queryset):
        project_names = set(queryset.values_list('project__full_name', flat=True))
        for full_name in project_names:
            if full_name:
                sync_repository_task.delay(full_name)
                log_audit_event(
                    actor=request.user,
                    action='project_sync_triggered',
                    target_type='Project',
                    target_id=full_name,
                    details={'full_name': full_name, 'source': 'issue_admin_sync'},
                )
        self.message_user(
            request,
            f"Enqueued GitHub sync for {len(project_names)} distinct repository/repositories.",
            messages.INFO,
        )

    def save_model(self, request, obj, form, change):
        if change:
            changes = {}
            for field in ['points', 'difficulty', 'category', 'status', 'is_featured']:
                if field in form.changed_data:
                    changes[field] = {
                        'old': form.initial.get(field),
                        'new': getattr(obj, field),
                    }
            if changes:
                log_audit_event(
                    actor=request.user,
                    action='issue_customized',
                    target_type='Issue',
                    target_id=obj.id,
                    details={'title': obj.title, 'changes': changes},
                )
        super().save_model(request, obj, form, change)


# =============================================================================
# Supplementary Model Admins (Labels, Pull Requests)
# =============================================================================

@admin.register(IssueLabel)
class IssueLabelAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'color_tag')
    search_fields = ('name',)

    def color_tag(self, obj):
        if obj.color:
            return format_html(
                '<span style="background-color: #{}; color: #fff; padding: 2px 6px; border-radius: 4px;">#{}</span>',
                obj.color.lstrip('#'),
                obj.color.lstrip('#'),
            )
        return "-"
    color_tag.short_description = "Color"


@admin.register(PullRequest)
class PullRequestAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'number',
        'repo',
        'author_github_id',
        'author_participant',
        'merged',
        'merged_at',
    )
    list_filter = ('merged', 'repo')
    search_fields = ('number', 'repo__full_name', 'author_github_id')
    raw_id_fields = ('repo', 'author_participant')
    readonly_fields = (
        'github_pr_id',
        'number',
        'repo',
        'author_github_id',
        'author_participant',
        'merged',
        'merged_at',
        'head_sha',
    )


# =============================================================================
# M8-T2: Contribution Admin
# =============================================================================

@admin.register(Contribution)
class ContributionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'participant_display',
        'project_display',
        'issue_display',
        'pull_request_display',
        'status_badge',
        'sub_status',
        'is_priority',
        'retry_count',
        'approved_at',
        'merged_at',
        'created_at',
    )
    list_filter = (
        'status',
        'sub_status',
        'is_priority',
        'created_at',
        'pull_request__repo',
    )
    search_fields = (
        'participant__github_username',
        'issue__title',
        'issue__number',
        'pull_request__number',
        'pull_request__repo__full_name',
        'flagged_reason',
    )
    raw_id_fields = ('participant', 'issue', 'pull_request')
    readonly_fields = (
        'participant',
        'issue',
        'pull_request',
        'locked_at',
        'approved_at',
        'merged_at',
        'created_at',
        'updated_at',
        'audit_trail',
    )
    fieldsets = (
        ('Contribution Information', {
            'fields': ('participant', 'issue', 'pull_request', 'status', 'sub_status', 'is_priority'),
        }),
        ('Execution & Timestamps', {
            'fields': ('retry_count', 'flagged_reason', 'locked_at', 'approved_at', 'merged_at', 'created_at', 'updated_at'),
        }),
        ('Audit History', {
            'fields': ('audit_trail',),
        }),
    )
    actions = [
        'retry_contributions',
        'flag_contributions',
        'reject_contributions',
        'manually_approve_contributions',
        'force_merge_contributions',
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'participant',
            'issue',
            'pull_request__repo',
        )

    def participant_display(self, obj):
        return obj.participant.github_username
    participant_display.short_description = "Participant"
    participant_display.admin_order_field = 'participant__github_username'

    def project_display(self, obj):
        return obj.pull_request.repo.full_name if obj.pull_request and obj.pull_request.repo else "-"
    project_display.short_description = "Project"

    def issue_display(self, obj):
        return f"#{obj.issue.number} ({obj.issue.points} pts)"
    issue_display.short_description = "Issue"

    def pull_request_display(self, obj):
        return f"PR #{obj.pull_request.number}"
    pull_request_display.short_description = "Pull Request"

    def status_badge(self, obj):
        colors = {
            'PENDING': '#64748b',
            'QUEUED': '#3b82f6',
            'UNDER_REVIEW': '#eab308',
            'APPROVED': '#10b981',
            'MERGING': '#8b5cf6',
            'MERGED': '#059669',
            'REJECTED': '#ef4444',
            'FLAGGED': '#f97316',
            'RETRY': '#f59e0b',
        }
        color = colors.get(obj.status, '#64748b')
        return format_html(
            '<span style="background-color: {}; color: #fff; padding: 2px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;">{}</span>',
            color,
            obj.status,
        )
    status_badge.short_description = "Status"
    status_badge.admin_order_field = 'status'

    def audit_trail(self, obj):
        if not obj or not obj.id:
            return "No audit history."
        logs = AuditLog.objects.filter(
            target_type='Contribution',
            target_id=str(obj.id),
        ).select_related('actor').order_by('-created_at')
        if not logs.exists():
            return "No audit log entries recorded."

        rows = []
        for log in logs:
            actor_name = log.actor.username if log.actor else "System"
            time_str = log.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')
            details_str = str(log.details) if log.details else "-"
            rows.append(
                f"<tr>"
                f"<td style='padding: 6px; border: 1px solid #e5e7eb;'>{time_str}</td>"
                f"<td style='padding: 6px; border: 1px solid #e5e7eb;'><b>{actor_name}</b></td>"
                f"<td style='padding: 6px; border: 1px solid #e5e7eb;'><code>{log.action}</code></td>"
                f"<td style='padding: 6px; border: 1px solid #e5e7eb;'>{details_str}</td>"
                f"</tr>"
            )
        html = (
            f"<table style='width: 100%; border-collapse: collapse; font-size: 12px;'>"
            f"<thead><tr style='background: #f9fafb; text-align: left;'>"
            f"<th style='padding: 6px; border: 1px solid #e5e7eb;'>Timestamp</th>"
            f"<th style='padding: 6px; border: 1px solid #e5e7eb;'>Actor</th>"
            f"<th style='padding: 6px; border: 1px solid #e5e7eb;'>Action</th>"
            f"<th style='padding: 6px; border: 1px solid #e5e7eb;'>Details</th>"
            f"</tr></thead>"
            f"<tbody>{''.join(rows)}</tbody>"
            f"</table>"
        )
        return mark_safe(html)
    audit_trail.short_description = "Audit Trail"

    @admin.action(description="Retry selected contributions (transition & re-enqueue validation)")
    def retry_contributions(self, request, queryset):
        success = 0
        for c in queryset:
            old_status = c.status
            try:
                if old_status in ('RETRY', 'FLAGGED'):
                    transition_contribution(c, 'UNDER_REVIEW', actor=request.user, reason="Admin retry action")
                validate_contribution_task.delay(c.id)
                log_audit_event(
                    actor=request.user,
                    action='admin_retry_contribution',
                    target_type='Contribution',
                    target_id=c.id,
                    details={'from_status': old_status, 'to_status': 'UNDER_REVIEW', 'source': 'admin_action'},
                )
                success += 1
            except Exception as e:
                self.message_user(request, f"Failed to retry Contribution {c.id}: {e}", messages.ERROR)
        if success > 0:
            self.message_user(request, f"Successfully re-enqueued {success} contribution(s) for validation.", messages.SUCCESS)

    @admin.action(description="Flag selected contributions for administrative review")
    def flag_contributions(self, request, queryset):
        success = 0
        for c in queryset:
            old_status = c.status
            if old_status in ('MERGED', 'REJECTED'):
                continue
            try:
                transition_contribution(c, 'FLAGGED', actor=request.user, reason="Admin manual flag override")
                log_audit_event(
                    actor=request.user,
                    action='admin_flag_contribution',
                    target_type='Contribution',
                    target_id=c.id,
                    details={'from_status': old_status, 'to_status': 'FLAGGED', 'source': 'admin_action'},
                )
                success += 1
            except Exception as e:
                self.message_user(request, f"Failed to flag Contribution {c.id}: {e}", messages.ERROR)
        if success > 0:
            self.message_user(request, f"Successfully flagged {success} contribution(s).", messages.SUCCESS)

    @admin.action(description="Reject selected contributions")
    def reject_contributions(self, request, queryset):
        success = 0
        for c in queryset:
            old_status = c.status
            if old_status == 'REJECTED':
                continue
            try:
                transition_contribution(c, 'REJECTED', actor=request.user, reason="Admin manual reject override")
                log_audit_event(
                    actor=request.user,
                    action='admin_reject_contribution',
                    target_type='Contribution',
                    target_id=c.id,
                    details={'from_status': old_status, 'to_status': 'REJECTED', 'source': 'admin_action'},
                )
                success += 1
            except Exception as e:
                self.message_user(request, f"Failed to reject Contribution {c.id}: {e}", messages.ERROR)
        if success > 0:
            self.message_user(request, f"Successfully rejected {success} contribution(s).", messages.SUCCESS)

    @admin.action(description="Manually approve selected contributions (for merge queue)")
    def manually_approve_contributions(self, request, queryset):
        success = 0
        for c in queryset:
            old_status = c.status
            try:
                transition_contribution(c, 'APPROVED', actor=request.user, reason="Admin manual approval override")
                log_audit_event(
                    actor=request.user,
                    action='admin_approve_contribution',
                    target_type='Contribution',
                    target_id=c.id,
                    details={'from_status': old_status, 'to_status': 'APPROVED', 'source': 'admin_action'},
                )
                success += 1
            except Exception as e:
                self.message_user(request, f"Failed to approve Contribution {c.id}: {e}", messages.ERROR)
        if success > 0:
            self.message_user(request, f"Successfully approved {success} contribution(s).", messages.SUCCESS)

    @admin.action(description="Force-transition selected contributions to MERGED (awards points)")
    def force_merge_contributions(self, request, queryset):
        success = 0
        for c in queryset:
            old_status = c.status
            if old_status == 'MERGED':
                self.message_user(request, f"Contribution {c.id} is already MERGED.", messages.WARNING)
                continue
            try:
                transition_contribution(c, 'MERGED', actor=request.user, reason="Admin force-merge override")
                award_result = award_points_for_contribution(c.id)
                log_audit_event(
                    actor=request.user,
                    action='admin_force_merge',
                    target_type='Contribution',
                    target_id=c.id,
                    details={
                        'from_status': old_status,
                        'to_status': 'MERGED',
                        'award_result': award_result,
                        'source': 'admin_action',
                    },
                )
                success += 1
            except Exception as e:
                self.message_user(request, f"Failed to force-merge Contribution {c.id}: {e}", messages.ERROR)
        if success > 0:
            self.message_user(request, f"Successfully force-merged {success} contribution(s).", messages.SUCCESS)


@admin.register(PointTransaction)
class PointTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'participant',
        'contribution',
        'points',
        'status',
        'reason',
        'created_at',
    )
    list_filter = ('status', 'created_at')
    search_fields = ('participant__github_username', 'reason', 'contribution__id')
    raw_id_fields = ('participant', 'contribution')
    readonly_fields = (
        'participant',
        'contribution',
        'points',
        'status',
        'reason',
        'created_at',
    )


@admin.register(DailyContributionUsage)
class DailyContributionUsageAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'participant',
        'date',
        'contributions_count',
        'points_count',
    )
    list_filter = ('date',)
    search_fields = ('participant__github_username',)
    raw_id_fields = ('participant',)


# =============================================================================
# M8-T3: EventConfig Admin Panel (Singleton runtime controls)
# =============================================================================

from django import forms
from django.core.exceptions import ValidationError


class EventConfigAdminForm(forms.ModelForm):
    class Meta:
        model = EventConfig
        fields = '__all__'

    def clean_merge_concurrency(self):
        val = self.cleaned_data.get('merge_concurrency')
        if val is None or val < 1:
            raise ValidationError("Merge concurrency must be at least 1.")
        return val

    def clean_max_contributions_per_day(self):
        val = self.cleaned_data.get('max_contributions_per_day')
        if val is None or val < 0:
            raise ValidationError("Max contributions per day cannot be negative.")
        return val

    def clean_max_points_per_day(self):
        val = self.cleaned_data.get('max_points_per_day')
        if val is None or val < 0:
            raise ValidationError("Max points per day cannot be negative.")
        return val


@admin.register(EventConfig)
class EventConfigAdmin(admin.ModelAdmin):
    form = EventConfigAdminForm
    list_display = (
        'id',
        'event_status',
        'merge_concurrency',
        'max_contributions_per_day',
        'max_points_per_day',
        'submissions_paused_badge',
        'validation_paused_badge',
        'merge_paused_badge',
        'leaderboard_frozen_badge',
    )
    readonly_fields = ('leaderboard_frozen_at',)
    fieldsets = (
        ('Event Lifecycle', {
            'fields': ('event_status',),
            'description': 'Main event status (e.g., pending, active, ended).',
        }),
        ('Daily Limits & Capacities', {
            'fields': ('max_contributions_per_day', 'max_points_per_day', 'merge_concurrency'),
            'description': 'Configure daily participant quotas and merge worker concurrency limits.',
        }),
        ('⚠️ Emergency Pipeline Controls', {
            'fields': (
                'submissions_paused',
                'validation_paused',
                'merge_paused',
                'leaderboard_frozen',
                'leaderboard_frozen_at',
            ),
            'description': 'Live runtime emergency switches. Takes effect immediately without service restart.',
        }),
    )

    def has_add_permission(self, request):
        if EventConfig.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        return False

    def submissions_paused_badge(self, obj):
        if obj.submissions_paused:
            return mark_safe('<span style="background: #ef4444; color: #fff; padding: 2px 6px; border-radius: 4px; font-weight: bold;">PAUSED</span>')
        return mark_safe('<span style="color: #10b981;">Active</span>')
    submissions_paused_badge.short_description = "Submissions"

    def validation_paused_badge(self, obj):
        if obj.validation_paused:
            return mark_safe('<span style="background: #ef4444; color: #fff; padding: 2px 6px; border-radius: 4px; font-weight: bold;">PAUSED</span>')
        return mark_safe('<span style="color: #10b981;">Active</span>')
    validation_paused_badge.short_description = "Validation"

    def merge_paused_badge(self, obj):
        if obj.merge_paused:
            return mark_safe('<span style="background: #ef4444; color: #fff; padding: 2px 6px; border-radius: 4px; font-weight: bold;">PAUSED</span>')
        return mark_safe('<span style="color: #10b981;">Active</span>')
    merge_paused_badge.short_description = "Merging"

    def leaderboard_frozen_badge(self, obj):
        if obj.leaderboard_frozen:
            return mark_safe('<span style="background: #3b82f6; color: #fff; padding: 2px 6px; border-radius: 4px; font-weight: bold;">FROZEN</span>')
        return mark_safe('<span style="color: #10b981;">Live</span>')
    leaderboard_frozen_badge.short_description = "Leaderboard"

    def save_model(self, request, obj, form, change):
        if change:
            changes = {}
            for field in form.changed_data:
                changes[field] = {
                    'old': form.initial.get(field),
                    'new': getattr(obj, field),
                }
            if changes:
                log_audit_event(
                    actor=request.user,
                    action='event_config_updated',
                    target_type='EventConfig',
                    target_id='1',
                    details={'changes': changes, 'source': 'admin_form_edit'},
                )
        super().save_model(request, obj, form, change)


# =============================================================================
# WebhookEvent Admin
# =============================================================================

@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'delivery_id',
        'event_type',
        'processed_at',
        'has_error',
    )
    list_filter = ('event_type', 'processed_at')
    search_fields = ('delivery_id', 'event_type', 'processing_error')
    readonly_fields = (
        'delivery_id',
        'event_type',
        'payload',
        'processed_at',
        'processing_error',
    )

    def has_error(self, obj):
        if obj.processing_error:
            return mark_safe('<span style="color: #ef4444;">Error</span>')
        return mark_safe('<span style="color: #10b981;">OK</span>')
    has_error.short_description = "Status"


# =============================================================================
# M8-T4: AuditLog Admin View (Read-only, immutable audit trail)
# =============================================================================

import json


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'created_at',
        'actor_display',
        'action_badge',
        'target_type',
        'target_id',
        'details_summary',
    )
    list_filter = (
        'action',
        'target_type',
        'created_at',
    )
    search_fields = (
        'actor__username',
        'actor__email',
        'action',
        'target_type',
        'target_id',
    )
    ordering = ('-created_at',)
    readonly_fields = (
        'actor',
        'action',
        'target_type',
        'target_id',
        'details_formatted',
        'created_at',
    )
    fieldsets = (
        ('Audit Metadata', {
            'fields': ('created_at', 'actor', 'action', 'target_type', 'target_id'),
        }),
        ('Structured Context', {
            'fields': ('details_formatted',),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('actor')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return True

    def actor_display(self, obj):
        if obj.actor:
            return obj.actor.username
        return mark_safe('<i style="color: #64748b;">System / Automation</i>')
    actor_display.short_description = "Actor"
    actor_display.admin_order_field = 'actor__username'

    def action_badge(self, obj):
        return format_html(
            '<code style="background: #f1f5f9; color: #0f172a; padding: 2px 6px; border-radius: 4px; font-size: 11px;">{}</code>',
            obj.action,
        )
    action_badge.short_description = "Action"
    action_badge.admin_order_field = 'action'

    def details_summary(self, obj):
        if not obj.details:
            return "-"
        s = json.dumps(obj.details)
        if len(s) > 80:
            return s[:77] + "..."
        return s
    details_summary.short_description = "Details Summary"

    def details_formatted(self, obj):
        if not obj.details:
            return "-"
        formatted = json.dumps(obj.details, indent=2)
        return format_html(
            '<pre style="background: #1e293b; color: #f8fafc; padding: 12px; border-radius: 6px; font-size: 12px; overflow-x: auto;">{}</pre>',
            formatted,
        )
    details_formatted.short_description = "Structured Details (JSON)"



