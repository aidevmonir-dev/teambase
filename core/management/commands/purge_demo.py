from django.core.management.base import BaseCommand

from core.demo import purge_expired


class Command(BaseCommand):
    help = "Delete demo accounts and their organisations older than DEMO_RETENTION_HOURS. Safe to run from cron."

    def handle(self, *args, **options):
        self.stdout.write(f"Deleted {purge_expired()} demo organisations.")
