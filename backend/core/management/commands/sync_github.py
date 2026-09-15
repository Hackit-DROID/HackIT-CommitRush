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
    sync_project,
)


class Command(BaseCommand):
    help = "Synchronize repository metadata from GitHub REST API into the Project table (M2-T1)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--repo',
            action='append',
            dest='repos',
            help="Repository to synchronize in 'owner/name' format (e.g., --repo owner/name). Can be specified multiple times.",
        )

    def handle(self, *args, **options):
        repo_inputs = options.get('repos')

        if not repo_inputs:
            raise CommandError("At least one repository must be specified using --repo owner/name.")

        client = GitHubClient()
        success_count = 0
        created_count = 0
        updated_count = 0
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
                repo_data = client.get_repository(owner, repo)
                project, created = sync_project(repo_data)
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
                success_count += 1
                if created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Successfully created Project '{project.full_name}' (ID: {project.id}, GitHub ID: {project.github_repo_id})."
                        )
                    )
                else:
                    updated_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Successfully updated Project '{project.full_name}' (ID: {project.id}, GitHub ID: {project.github_repo_id})."
                        )
                    )

        summary_msg = f"Sync complete. Success: {success_count} ({created_count} created, {updated_count} updated), Failed: {len(failed_repos)}."
        if failed_repos:
            self.stderr.write(self.style.WARNING(summary_msg))
            raise CommandError(f"Synchronization failed for {len(failed_repos)} repository/repositories: {', '.join(failed_repos)}")

        self.stdout.write(self.style.SUCCESS(summary_msg))
