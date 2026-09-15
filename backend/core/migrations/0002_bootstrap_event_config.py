# Generated for M1-T4 EventConfig singleton bootstrap

from django.db import migrations


def bootstrap_event_config_migration(apps, schema_editor):
    EventConfig = apps.get_model('core', 'EventConfig')
    EventConfig.objects.get_or_create(
        pk=1,
        defaults={
            'merge_concurrency': 5,
            'max_contributions_per_day': 5,
            'max_points_per_day': 500,
            'merge_paused': False,
            'validation_paused': False,
            'submissions_paused': False,
            'leaderboard_frozen': False,
            'event_status': 'pending',
        },
    )


def reverse_bootstrap_event_config(apps, schema_editor):
    # No-op on rollback: deleting runtime config risks loss of event state
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            code=bootstrap_event_config_migration,
            reverse_code=reverse_bootstrap_event_config,
        ),
    ]
