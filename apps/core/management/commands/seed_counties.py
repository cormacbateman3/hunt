from django.core.management.base import BaseCommand
from django.utils.text import slugify
from apps.core.models import County


PA_COUNTIES = [
    ('Adams', '001'),
    ('Allegheny', '003'),
    ('Armstrong', '005'),
    ('Beaver', '007'),
    ('Bedford', '009'),
    ('Berks', '011'),
    ('Blair', '013'),
    ('Bradford', '015'),
    ('Bucks', '017'),
    ('Butler', '019'),
    ('Cambria', '021'),
    ('Cameron', '023'),
    ('Carbon', '025'),
    ('Centre', '027'),
    ('Chester', '029'),
    ('Clarion', '031'),
    ('Clearfield', '033'),
    ('Clinton', '035'),
    ('Columbia', '037'),
    ('Crawford', '039'),
    ('Cumberland', '041'),
    ('Dauphin', '043'),
    ('Delaware', '045'),
    ('Elk', '047'),
    ('Erie', '049'),
    ('Fayette', '051'),
    ('Forest', '053'),
    ('Franklin', '055'),
    ('Fulton', '057'),
    ('Greene', '059'),
    ('Huntingdon', '061'),
    ('Indiana', '063'),
    ('Jefferson', '065'),
    ('Juniata', '067'),
    ('Lackawanna', '069'),
    ('Lancaster', '071'),
    ('Lawrence', '073'),
    ('Lebanon', '075'),
    ('Lehigh', '077'),
    ('Luzerne', '079'),
    ('Lycoming', '081'),
    ('McKean', '083'),
    ('Mercer', '085'),
    ('Mifflin', '087'),
    ('Monroe', '089'),
    ('Montgomery', '091'),
    ('Montour', '093'),
    ('Northampton', '095'),
    ('Northumberland', '097'),
    ('Perry', '099'),
    ('Philadelphia', '101'),
    ('Pike', '103'),
    ('Potter', '105'),
    ('Schuylkill', '107'),
    ('Snyder', '109'),
    ('Somerset', '111'),
    ('Sullivan', '113'),
    ('Susquehanna', '115'),
    ('Tioga', '117'),
    ('Union', '119'),
    ('Venango', '121'),
    ('Warren', '123'),
    ('Washington', '125'),
    ('Wayne', '127'),
    ('Westmoreland', '129'),
    ('Wyoming', '131'),
    ('York', '133'),
]


class Command(BaseCommand):
    help = 'Seed Pennsylvania counties reference data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete existing counties before seeding.',
        )

    def handle(self, *args, **options):
        if options['reset']:
            deleted, _ = County.objects.all().delete()
            self.stdout.write(self.style.WARNING(f'Deleted {deleted} existing county records.'))

        created = 0
        updated = 0
        for name, fips_code in PA_COUNTIES:
            _, is_created = County.objects.update_or_create(
                name=name,
                defaults={
                    'state': 'PA',
                    'fips_code': fips_code,
                    'slug': slugify(name),
                },
            )
            if is_created:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'County seed complete. created={created} updated={updated} total={County.objects.count()}'
            )
        )
