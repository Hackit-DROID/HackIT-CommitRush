import datetime
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import (
    AuditLog,
    Contribution,
    DailyContributionUsage,
    EventConfig,
    Issue,
    IssueLabel,
    Participant,
    PointTransaction,
    Project,
    PullRequest,
    WebhookEvent,
)

User = get_user_model()


class Command(BaseCommand):
    help = 'Seeds realistic sample data for local frontend/backend preview and testing.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding CommitRush local demo data..."))

        # 1. Ensure Superuser / Admin
        admin_user, _ = User.objects.get_or_create(
            username='admin',
            defaults={'email': 'admin@commitrush.dev', 'is_staff': True, 'is_superuser': True},
        )
        admin_user.set_password('admin')
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.save()

        # 2. Event Config
        now = timezone.now()
        config = EventConfig.get_solo()
        config.event_status = 'active'
        config.event_start = now - datetime.timedelta(days=2)
        config.event_end = now + datetime.timedelta(days=5)
        config.registration_start = now - datetime.timedelta(days=10)
        config.registration_end = now + datetime.timedelta(days=4)
        config.max_contributions_per_day = 10
        config.max_points_per_day = 1000
        config.merge_concurrency = 6
        config.submissions_paused = False
        config.validation_paused = False
        config.merge_paused = False
        config.leaderboard_frozen = False
        config.save()

        # 3. Projects
        projects_data = [
            {
                'github_repo_id': 10101,
                'owner': 'hackit-org',
                'name': 'gateway-service',
                'full_name': 'hackit-org/gateway-service',
                'description': 'High throughput async API reverse proxy and load balancer in Go.',
                'language': 'Go',
                'is_enabled': True,
            },
            {
                'github_repo_id': 10102,
                'owner': 'hackit-org',
                'name': 'analytics-engine',
                'full_name': 'hackit-org/analytics-engine',
                'description': 'Real-time telemetry event streaming and window aggregation pipeline in Python.',
                'language': 'Python',
                'is_enabled': True,
            },
            {
                'github_repo_id': 10103,
                'owner': 'hackit-org',
                'name': 'commitrush-frontend',
                'full_name': 'hackit-org/commitrush-frontend',
                'description': 'Modern reactive dashboard with Tailwind CSS and TanStack Query.',
                'language': 'TypeScript',
                'is_enabled': True,
            },
            {
                'github_repo_id': 10104,
                'owner': 'hackit-org',
                'name': 'auth-agent',
                'full_name': 'hackit-org/auth-agent',
                'description': 'Zero-trust OAuth2/OIDC token verification sidecar written in Rust.',
                'language': 'Rust',
                'is_enabled': True,
            },
            {
                'github_repo_id': 10105,
                'owner': 'hackit-org',
                'name': 'cache-mesh',
                'full_name': 'hackit-org/cache-mesh',
                'description': 'Distributed in-memory consistent hashing cache nodes in C++.',
                'language': 'C++',
                'is_enabled': True,
            },
        ]

        projects = {}
        for pdata in projects_data:
            p, _ = Project.objects.update_or_create(
                github_repo_id=pdata['github_repo_id'],
                defaults=pdata,
            )
            projects[p.name] = p

        # 4. Labels
        labels_data = [
            ('good-first-issue', '7057ff'),
            ('help-wanted', '008672'),
            ('bug', 'd73a4a'),
            ('enhancement', 'a2eeef'),
            ('performance', 'e4e669'),
            ('security', 'b60205'),
            ('documentation', '0075ca'),
        ]
        labels = {}
        for name, color in labels_data:
            lbl, _ = IssueLabel.objects.get_or_create(name=name, defaults={'color': color})
            labels[name] = lbl

        # 5. Issues
        issues_data = [
            # Gateway Service (Go)
            {
                'project': projects['gateway-service'],
                'github_issue_id': 201,
                'number': 1,
                'title': 'Add Prometheus metrics exporter endpoint',
                'points': 50,
                'difficulty': 'beginner',
                'category': 'networking',
                'status': 'closed',
                'labels': ['good-first-issue', 'enhancement'],
            },
            {
                'project': projects['gateway-service'],
                'github_issue_id': 202,
                'number': 2,
                'title': 'Implement token bucket rate limiter middleware',
                'points': 100,
                'difficulty': 'intermediate',
                'category': 'networking',
                'status': 'open',
                'labels': ['enhancement', 'performance'],
            },
            {
                'project': projects['gateway-service'],
                'github_issue_id': 203,
                'number': 3,
                'title': 'Fix memory leak in websocket connection pool',
                'points': 150,
                'difficulty': 'advanced',
                'category': 'networking',
                'status': 'open',
                'labels': ['bug', 'performance'],
            },
            # Analytics Engine (Python)
            {
                'project': projects['analytics-engine'],
                'github_issue_id': 301,
                'number': 10,
                'title': 'Add parquet export for daily aggregation buckets',
                'points': 50,
                'difficulty': 'beginner',
                'category': 'backend',
                'status': 'closed',
                'labels': ['good-first-issue', 'enhancement'],
            },
            {
                'project': projects['analytics-engine'],
                'github_issue_id': 302,
                'number': 11,
                'title': 'Optimize composite database indexes on time-series telemetry',
                'points': 100,
                'difficulty': 'intermediate',
                'category': 'database',
                'status': 'closed',
                'labels': ['performance'],
            },
            {
                'project': projects['analytics-engine'],
                'github_issue_id': 303,
                'number': 12,
                'title': 'Implement sliding window quantile estimation',
                'points': 150,
                'difficulty': 'advanced',
                'category': 'backend',
                'status': 'open',
                'labels': ['enhancement'],
            },
            # CommitRush Frontend (TypeScript)
            {
                'project': projects['commitrush-frontend'],
                'github_issue_id': 401,
                'number': 21,
                'title': 'Add keyboard navigation shortcuts for issue search',
                'points': 25,
                'difficulty': 'beginner',
                'category': 'frontend',
                'status': 'closed',
                'labels': ['good-first-issue', 'enhancement'],
            },
            {
                'project': projects['commitrush-frontend'],
                'github_issue_id': 402,
                'number': 22,
                'title': 'Implement dark mode theme toggle with persistent local storage',
                'points': 50,
                'difficulty': 'beginner',
                'category': 'frontend',
                'status': 'closed',
                'labels': ['enhancement'],
            },
            {
                'project': projects['commitrush-frontend'],
                'github_issue_id': 403,
                'number': 23,
                'title': 'Build interactive points timeline area chart',
                'points': 100,
                'difficulty': 'intermediate',
                'category': 'frontend',
                'status': 'open',
                'labels': ['enhancement', 'help-wanted'],
            },
            # Auth Agent (Rust)
            {
                'project': projects['auth-agent'],
                'github_issue_id': 501,
                'number': 31,
                'title': 'Add constant-time signature comparison helper',
                'points': 100,
                'difficulty': 'intermediate',
                'category': 'security',
                'status': 'closed',
                'labels': ['security', 'bug'],
            },
            {
                'project': projects['auth-agent'],
                'github_issue_id': 502,
                'number': 32,
                'title': 'Implement automated JWKS cache rotation with exponential backoff',
                'points': 150,
                'difficulty': 'advanced',
                'category': 'security',
                'status': 'open',
                'labels': ['security', 'enhancement'],
            },
            # Cache Mesh (C++)
            {
                'project': projects['cache-mesh'],
                'github_issue_id': 601,
                'number': 41,
                'title': 'Implement Murmur3 128-bit hashing for cache ring',
                'points': 100,
                'difficulty': 'intermediate',
                'category': 'database',
                'status': 'closed',
                'labels': ['performance', 'enhancement'],
            },
        ]

        issues = {}
        for idata in issues_data:
            lbl_keys = idata.pop('labels', [])
            iss, _ = Issue.objects.update_or_create(
                github_issue_id=idata['github_issue_id'],
                defaults=idata,
            )
            for lk in lbl_keys:
                if lk in labels:
                    iss.labels.add(labels[lk])
            issues[iss.number] = iss

        # 6. Participants
        participants_data = [
            ('sarah_dev', 'Sarah Chen', 'sarah@example.com', 9001, 'https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=150&auto=format&fit=crop&q=80'),
            ('alex_builder', 'Alex Rivera', 'alex@example.com', 9002, 'https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=150&auto=format&fit=crop&q=80'),
            ('marcus_k', 'Marcus Klein', 'marcus@example.com', 9003, 'https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=150&auto=format&fit=crop&q=80'),
            ('elena_rust', 'Elena Rostova', 'elena@example.com', 9004, 'https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=150&auto=format&fit=crop&q=80'),
            ('dev_dave', 'David Kim', 'david@example.com', 9005, 'https://images.unsplash.com/photo-1522075469751-3a6694fb2f61?w=150&auto=format&fit=crop&q=80'),
            ('priya_code', 'Priya Sharma', 'priya@example.com', 9006, 'https://images.unsplash.com/photo-1517841905240-472988babdf9?w=150&auto=format&fit=crop&q=80'),
            ('lucas_g', 'Lucas Garcia', 'lucas@example.com', 9007, 'https://images.unsplash.com/photo-1492562080023-ab3db95bfbce?w=150&auto=format&fit=crop&q=80'),
            ('zack_hacker', 'Zack Taylor', 'zack@example.com', 9008, 'https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=150&auto=format&fit=crop&q=80'),
        ]

        participants = {}
        for gh_user, full_name, email, gh_id, avatar in participants_data:
            u, _ = User.objects.get_or_create(
                username=gh_user,
                defaults={'email': email, 'first_name': full_name.split()[0], 'last_name': full_name.split()[-1]},
            )
            u.set_password('password123')
            u.save()

            p, _ = Participant.objects.update_or_create(
                github_id=gh_id,
                defaults={
                    'user': u,
                    'github_username': gh_user,
                    'avatar_url': avatar,
                    'total_points': 0,
                    'merged_count': 0,
                    'is_suspended': False,
                },
            )
            participants[gh_user] = p

        # 7. Pull Requests, Contributions & Points
        contributions_seed = [
            # Sarah (Rank #1: 350 pts, 4 merged)
            {
                'participant': participants['sarah_dev'],
                'issue': issues[10], # 50 pts
                'pr_num': 101,
                'status': 'MERGED',
                'points': 50,
                'created_hours_ago': 40,
                'merged_hours_ago': 38,
            },
            {
                'participant': participants['sarah_dev'],
                'issue': issues[11], # 100 pts
                'pr_num': 102,
                'status': 'MERGED',
                'points': 100,
                'created_hours_ago': 28,
                'merged_hours_ago': 26,
            },
            {
                'participant': participants['sarah_dev'],
                'issue': issues[31], # 100 pts
                'pr_num': 103,
                'status': 'MERGED',
                'points': 100,
                'created_hours_ago': 14,
                'merged_hours_ago': 12,
            },
            {
                'participant': participants['sarah_dev'],
                'issue': issues[41], # 100 pts
                'pr_num': 104,
                'status': 'MERGED',
                'points': 100,
                'created_hours_ago': 5,
                'merged_hours_ago': 3,
            },

            # Alex (Rank #2: 225 pts, 4 merged)
            {
                'participant': participants['alex_builder'],
                'issue': issues[1], # 50 pts
                'pr_num': 201,
                'status': 'MERGED',
                'points': 50,
                'created_hours_ago': 36,
                'merged_hours_ago': 34,
            },
            {
                'participant': participants['alex_builder'],
                'issue': issues[21], # 25 pts
                'pr_num': 202,
                'status': 'MERGED',
                'points': 25,
                'created_hours_ago': 24,
                'merged_hours_ago': 22,
            },
            {
                'participant': participants['alex_builder'],
                'issue': issues[31], # 100 pts
                'pr_num': 203,
                'status': 'MERGED',
                'points': 100,
                'created_hours_ago': 12,
                'merged_hours_ago': 10,
            },
            {
                'participant': participants['alex_builder'],
                'issue': issues[22], # 50 pts
                'pr_num': 204,
                'status': 'MERGED',
                'points': 50,
                'created_hours_ago': 6,
                'merged_hours_ago': 4,
            },

            # Elena (Rank #3: 200 pts, 2 merged)
            {
                'participant': participants['elena_rust'],
                'issue': issues[31], # 100 pts
                'pr_num': 301,
                'status': 'MERGED',
                'points': 100,
                'created_hours_ago': 30,
                'merged_hours_ago': 28,
            },
            {
                'participant': participants['elena_rust'],
                'issue': issues[41], # 100 pts
                'pr_num': 302,
                'status': 'MERGED',
                'points': 100,
                'created_hours_ago': 8,
                'merged_hours_ago': 6,
            },

            # Marcus (Rank #4: 150 pts, 2 merged)
            {
                'participant': participants['marcus_k'],
                'issue': issues[1], # 50 pts
                'pr_num': 401,
                'status': 'MERGED',
                'points': 50,
                'created_hours_ago': 20,
                'merged_hours_ago': 18,
            },
            {
                'participant': participants['marcus_k'],
                'issue': issues[11], # 100 pts
                'pr_num': 402,
                'status': 'MERGED',
                'points': 100,
                'created_hours_ago': 10,
                'merged_hours_ago': 8,
            },

            # Priya (Rank #5: 100 pts, 1 merged)
            {
                'participant': participants['priya_code'],
                'issue': issues[11], # 100 pts
                'pr_num': 501,
                'status': 'MERGED',
                'points': 100,
                'created_hours_ago': 16,
                'merged_hours_ago': 14,
            },

            # David (Rank #6: 50 pts, 1 merged)
            {
                'participant': participants['dev_dave'],
                'issue': issues[22], # 50 pts
                'pr_num': 601,
                'status': 'MERGED',
                'points': 50,
                'created_hours_ago': 18,
                'merged_hours_ago': 15,
            },

            # Active In-Flight Contributions (for trackers & Ops Panel)
            {
                'participant': participants['sarah_dev'],
                'issue': issues[2], # Gateway Rate Limiter
                'pr_num': 105,
                'status': 'UNDER_REVIEW',
                'points': 100,
                'created_hours_ago': 1,
            },
            {
                'participant': participants['alex_builder'],
                'issue': issues[23], # Frontend Area Chart
                'pr_num': 205,
                'status': 'APPROVED',
                'points': 100,
                'created_hours_ago': 2,
            },
            {
                'participant': participants['zack_hacker'],
                'issue': issues[3], # Gateway memory leak
                'pr_num': 701,
                'status': 'FLAGGED',
                'points': 150,
                'created_hours_ago': 3,
            },
            {
                'participant': participants['lucas_g'],
                'issue': issues[12], # Sliding window
                'pr_num': 801,
                'status': 'RETRY',
                'points': 150,
                'created_hours_ago': 4,
            },
        ]

        pr_counter = 8000
        for cdata in contributions_seed:
            pr_counter += 1
            part = cdata['participant']
            iss = cdata['issue']
            st = cdata['status']
            pts = cdata['points']

            created_time = now - datetime.timedelta(hours=cdata['created_hours_ago'])
            merged_time = (
                now - datetime.timedelta(hours=cdata['merged_hours_ago'])
                if 'merged_hours_ago' in cdata
                else None
            )

            pr, _ = PullRequest.objects.update_or_create(
                github_pr_id=pr_counter,
                defaults={
                    'repo': iss.project,
                    'number': cdata['pr_num'],
                    'author_github_id': part.github_id,
                    'author_participant': part,
                    'head_sha': f"sha_{pr_counter}_{cdata['pr_num']}",
                    'merged': (st == 'MERGED'),
                    'merged_at': merged_time,
                },
            )

            contrib, _ = Contribution.objects.update_or_create(
                pull_request=pr,
                defaults={
                    'participant': part,
                    'issue': iss,
                    'status': st,
                    'approved_at': merged_time or (now - datetime.timedelta(minutes=30) if st == 'APPROVED' else None),
                    'merged_at': merged_time,
                    'flagged_reason': 'Automated heuristics detected abnormal diff ratio' if st == 'FLAGGED' else '',
                    'created_at': created_time,
                },
            )

            if st == 'MERGED':
                PointTransaction.objects.update_or_create(
                    contribution=contrib,
                    defaults={
                        'participant': part,
                        'points': pts,
                        'status': 'AWARDED',
                        'reason': f"Points awarded for merged PR #{cdata['pr_num']} on Issue #{iss.number}",
                    },
                )

        # Recalculate participant points & merged counts accurately
        for p in Participant.objects.all():
            awarded = PointTransaction.objects.filter(participant=p, status='AWARDED')
            total = sum(t.points for t in awarded)
            m_count = awarded.count()
            p.total_points = total
            p.merged_count = m_count
            p.save(update_fields=['total_points', 'merged_count'])

        # 8. Sample Audit Logs
        AuditLog.objects.get_or_create(
            actor=admin_user,
            action='event_configured',
            target_type='EventConfig',
            target_id=str(config.id),
            details={'message': 'Event configured with active status and daily limits.'},
        )
        AuditLog.objects.get_or_create(
            actor=admin_user,
            action='project_synced',
            target_type='Project',
            target_id=str(projects['gateway-service'].id),
            details={'repo': 'hackit-org/gateway-service', 'synced_issues': 3},
        )

        self.stdout.write(self.style.SUCCESS(
            f"Successfully seeded CommitRush demo data!\n"
            f"- Projects: {Project.objects.count()}\n"
            f"- Issues: {Issue.objects.count()}\n"
            f"- Participants: {Participant.objects.count()}\n"
            f"- Contributions: {Contribution.objects.count()}\n"
            f"- Point Transactions: {PointTransaction.objects.count()}\n"
            f"- Admin Superuser: admin / admin\n"
            f"- Demo Participant: sarah_dev / password123"
        ))
