from django.core.management.base import BaseCommand

from apps.core.management.commands.seed_geographic_units import Command as SeedGeographicUnitsCommand


class Command(BaseCommand):
    help = 'Legacy alias for seed_geographic_units'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('seed_counties is deprecated; running seed_geographic_units instead.'))
        SeedGeographicUnitsCommand().handle(*args, **options)
