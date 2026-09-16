from django.core.management.base import BaseCommand, CommandError

from core.github_sync import (
    GitHubClient,
    GitHubSyncError,
    GitHubResourceNotFoundError,
    GitHubAuthenticationError,
    GitHubRateLimitError,
    GitHubNetworkError,
    GitHubDataError,
    parse_repo_identifier,
    sync_repository_and_issues,
)
from core.tasks import sync_repository_task


class Command(BaseCommand):
    help = "Synchronize repository metadata and issues from GitHub REST API into the Project and Issue tables (M2-T1, M2-T2, M2-T3, M2-T4)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--repo',
            action='append',
            dest='repos',
            help="Repository to synchronize in 'owner/name' format (e.g., --repo owner/name). Can be specified multiple times.",
        )
        parser.add_argument(
            '--no-issues',
            action='store_true',
            dest='no_issues',
            default=False,
            help="Skip synchronizing repository issues (only sync repository metadata).",
        )
        parser.add_argument(
            '--async',
            action='store_true',
            dest='async_mode',
            default=False,
            help="Enqueue synchronization task to Celery 'sync' queue instead of running synchronously.",
        )

    def handle(self, *args, **options):
        repo_inputs = options.get('repos')
        sync_issues_flag = not options.get('no_issues', False)
        async_mode = options.get('async_mode', False)

        if not repo_inputs:
            raise CommandError("At least one repository must be specified using --repo owner/name.")

        if async_mode:
            enqueued_count = 0
            for repo_identifier in repo_inputs:
                try:
                    owner, repo = parse_repo_identifier(repo_identifier)
                except ValueError as e:
                    self.stderr.write(self.style.ERROR(f"Error: {str(e)}"))
                    continue

                task = sync_repository_task.delay(f"{owner}/{repo}", sync_issues=sync_issues_flag)
                enqueued_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Enqueued sync for '{owner}/{repo}' to Celery 'sync' queue (Task ID: {task.id})."
                    )
                )

            self.stdout.write(self.style.SUCCESS(f"Successfully enqueued {enqueued_count} repository sync task(s)."))
            return

        client = GitHubClient()
        success_repos = 0
        created_repos = 0
        updated_repos = 0
        total_issues_created = 0
        total_issues_updated = 0
        failed_repos = []

        for repo_identifier in repo_inputs:
            # Validate format
            try:
                owner, repo = parse_repo_identifier(repo_identifier)
            except ValueError as e:
                self.stderr.write(self.style.ERROR(f"Error: {str(e)}"))
                failed_repos.append(repo_identifier)
                continue

            self.stdout.write(f"Synchronizing repository '{owner}/{repo}'...")

            try:
                project, repo_created, issues_created, issues_updated = sync_repository_and_issues(
                    f"{owner}/{repo}",
                    client=client,
                    sync_issues_flag=sync_issues_flag,
                )
            except GitHubResourceNotFoundError as e:
                self.stderr.write(self.style.ERROR(f"Failed to synchronize '{owner}/{repo}': {str(e)}"))
                failed_repos.append(f"{owner}/{repo}")
            except GitHubAuthenticationError as e:
                self.stderr.write(self.style.ERROR(f"Authentication failure for '{owner}/{repo}': {str(e)}"))
                failed_repos.append(f"{owner}/{repo}")
            except GitHubRateLimitError as e:
                self.stderr.write(self.style.ERROR(f"Rate limit exceeded for '{owner}/{repo}': {str(e)}"))
                failed_repos.append(f"{owner}/{repo}")
            except GitHubNetworkError as e:
                self.stderr.write(self.style.ERROR(f"Network error for '{owner}/{repo}': {str(e)}"))
                failed_repos.append(f"{owner}/{repo}")
            except GitHubDataError as e:
                self.stderr.write(self.style.ERROR(f"Data error for '{owner}/{repo}': {str(e)}"))
                failed_repos.append(f"{owner}/{repo}")
            except GitHubSyncError as e:
                self.stderr.write(self.style.ERROR(f"Sync error for '{owner}/{repo}': {str(e)}"))
                failed_repos.append(f"{owner}/{repo}")
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Unexpected error for '{owner}/{repo}': {str(e)}"))
                failed_repos.append(f"{owner}/{repo}")
            else:
                success_repos += 1
                if repo_created:
                    created_repos += 1
                    status_text = "created"
                else:
                    updated_repos += 1
                    status_text = "updated"

                total_issues_created += issues_created
                total_issues_updated += issues_updated

                if sync_issues_flag:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Successfully {status_text} Project '{project.full_name}' (ID: {project.id}, GitHub ID: {project.github_repo_id}). "
                            f"Issues synced: {issues_created} created, {issues_updated} updated."
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Successfully {status_text} Project '{project.full_name}' (ID: {project.id}, GitHub ID: {project.github_repo_id})."
                        )
                    )

        summary_msg = (
            f"Sync complete. Repositories: {success_repos} ({created_repos} created, {updated_repos} updated), "
            f"Issues: {total_issues_created + total_issues_updated} ({total_issues_created} created, {total_issues_updated} updated), "
            f"Failed: {len(failed_repos)}."
        )
        if failed_repos:
            self.stderr.write(self.style.WARNING(summary_msg))
            raise CommandError(f"Synchronization failed for {len(failed_repos)} repository/repositories: {', '.join(failed_repos)}")

        self.stdout.write(self.style.SUCCESS(summary_msg))
