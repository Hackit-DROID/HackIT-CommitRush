from django.core.management.base import BaseCommand
from core.bootstrap import bootstrap_event_config


class Command(BaseCommand):
    help = "Bootstrap and ensure the EventConfig singleton instance exists with canonical defaults."

    def handle(self, *args, **options):
        config = bootstrap_event_config()
        self.stdout.write(
            self.style.SUCCESS(
                f"EventConfig singleton initialized successfully (ID: {config.pk}, Status: {config.event_status})."
            )
        )
