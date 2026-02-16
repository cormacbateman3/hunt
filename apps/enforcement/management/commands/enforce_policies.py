from django.core.management.base import BaseCommand
from apps.enforcement.services import enforce_deterministic_policies, refresh_all_account_restrictions


class Command(BaseCommand):
    help = 'Apply deterministic Alpha enforcement rules and issue strikes where due.'

    def handle(self, *args, **options):
        created = enforce_deterministic_policies()
        refreshed = refresh_all_account_restrictions()
        self.stdout.write(
            self.style.SUCCESS(
                f'Enforcement run complete. strikes_created={created} restrictions_refreshed={refreshed}'
            )
        )
