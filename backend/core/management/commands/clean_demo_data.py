from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import models, transaction

from core.leaderboard import invalidate_frozen_leaderboard_cache, invalidate_leaderboard_cache
from core.models import (
    Contribution,
    DailyContributionUsage,
    Issue,
    Participant,
    PointTransaction,
    Project,
    PullRequest,
)

User = get_user_model()

DEMO_USERNAMES = [
    'sarah_dev',
    'alex_builder',
    'marcus_k',
    'elena_rust',
    'dev_dave',
    'priya_code',
    'lucas_g',
    'zack_hacker',
]

DEMO_GITHUB_IDS = [9001, 9002, 9003, 9004, 9005, 9006, 9007, 9008]


class Command(BaseCommand):
    help = (
        'Removes all mock demo participants, demo pull requests, demo contributions, '
        'and demo point transactions from the database in preparation for production deployment, '
        'while strictly preserving all real GitHub issues and tracked repositories.'
    )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Starting demo data cleanup..."))

        with transaction.atomic():
            # 1. Identify demo participants
            participants = Participant.objects.filter(
                models.Q(user__username__in=DEMO_USERNAMES)
                | models.Q(github_id__in=DEMO_GITHUB_IDS)
                | models.Q(github_username__in=DEMO_USERNAMES)
            )
            p_count = participants.count()
            p_usernames = list(participants.values_list('github_username', flat=True))

            # 2. Identify demo users
            users = User.objects.filter(username__in=DEMO_USERNAMES)
            u_count = users.count()

            # 3. Pull requests associated with demo participants
            demo_prs = PullRequest.objects.filter(
                models.Q(author_participant__in=participants)
                | models.Q(author_github_id__in=DEMO_GITHUB_IDS)
            )
            pr_count = demo_prs.count()

            # 4. Contributions associated with demo participants
            demo_contribs = Contribution.objects.filter(
                models.Q(participant__in=participants)
                | models.Q(pull_request__in=demo_prs)
            )
            contrib_count = demo_contribs.count()

            # 5. Point transactions
            demo_ptx = PointTransaction.objects.filter(
                models.Q(participant__in=participants)
                | models.Q(contribution__in=demo_contribs)
            )
            ptx_count = demo_ptx.count()

            # 6. Daily usage records
            demo_usages = DailyContributionUsage.objects.filter(participant__in=participants)
            usage_count = demo_usages.count()

            # Execute deletes in correct dependency order
            demo_ptx.delete()
            demo_usages.delete()
            demo_contribs.delete()
            demo_prs.delete()
            participants.delete()
            users.delete()

            # 7. Reset status on mock demo issues if they were closed by demo PRs
            # (Do not touch real repo issues)
            real_drive_repo = 'Hackit-DROID/Open-Source-Contribution-Drive'
            demo_issues_reopened = Issue.objects.exclude(project__full_name=real_drive_repo).filter(status='closed').update(status='open')

            # 8. Invalidate caches
            invalidate_leaderboard_cache()
            invalidate_frozen_leaderboard_cache()
            cache.clear()

        self.stdout.write(self.style.SUCCESS(
            f"Successfully cleaned up demo data:\n"
            f"  - Participants removed: {p_count} ({', '.join(p_usernames)})\n"
            f"  - Users removed: {u_count}\n"
            f"  - Pull requests removed: {pr_count}\n"
            f"  - Contributions removed: {contrib_count}\n"
            f"  - Point transactions removed: {ptx_count}\n"
            f"  - Daily usage records removed: {usage_count}\n"
            f"  - Demo issues reset to open: {demo_issues_reopened}\n"
            f"  - Cache cleared and invalidated.\n"
            f"Current DB state:\n"
            f"  - Total Issues: {Issue.objects.count()} (untouched)\n"
            f"  - Total Projects: {Project.objects.count()} (untouched)\n"
            f"  - Total Participants: {Participant.objects.count()}\n"
            f"  - Total Users: {User.objects.count()}\n"
            f"  - Total PRs: {PullRequest.objects.count()}\n"
            f"  - Total Contributions: {Contribution.objects.count()}"
        ))
