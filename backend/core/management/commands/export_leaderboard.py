"""
Management command to export the persistent, repository-friendly CommitRush leaderboard.
Generates JSON structure conforming to the event schema:
{
  "event": "HackIT CommitRush Open Source Contribution Drive",
  "timezone": "Asia/Kolkata",
  "daily_limit": 120,
  "participants": {
    "userA": { ... }
  }
}
"""

import json
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand
from core.leaderboard import generate_leaderboard_json


class Command(BaseCommand):
    help = "Export authoritative CommitRush leaderboard data to persistent JSON format."

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            '-o',
            type=str,
            default='leaderboard.json',
            help='Output file path for the exported JSON (default: leaderboard.json)',
        )
        parser.add_argument(
            '--stdout',
            action='store_true',
            help='Print JSON directly to standard output',
        )

    def handle(self, *args, **options):
        data = generate_leaderboard_json()
        json_content = json.dumps(data, indent=2)

        if options['stdout']:
            self.stdout.write(json_content)
            return

        out_path = Path(options['output'])
        if not out_path.is_absolute():
            # If relative, save relative to repository root or current working directory
            out_path = Path.cwd() / out_path

        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(json_content)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully exported leaderboard ({len(data.get('participants', {}))} participants) to {out_path}"
            )
        )
