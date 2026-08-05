"""
seed_demo — creates showcase listings and collection items for local demos.

All data is owned by the __keystonebid_demo__ system user and prefixed with
[DEMO] in every title.  Run remove_demo to wipe it cleanly.

Usage:
    python manage.py seed_demo
    python manage.py seed_demo --reset   # remove then re-seed
"""

import random
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.collections.models import CollectionItem, CollectionItemImage
from apps.core.models import GeographicUnit, LicenseType, State
from apps.listings.models import Listing

DEMO_USERNAME = '__keystonebid_demo__'
DEMO_EMAIL = 'demo@keystonebid.internal'
DEMO_PREFIX = '[DEMO] '

# ── Catalogue data ────────────────────────────────────────────────────────────
# Each entry: (title_suffix, year, county_name, condition, description_snippet)
COLLECTION_DATA = [
    ('1941 Resident Hunting License – Chester Co.',         1941, 'Chester',    'very_good',
     'Button and stub both present. Minor edge foxing, color still vibrant.'),
    ('1955 Resident Hunting & Fishing Combination – Lancaster Co.', 1955, 'Lancaster', 'excellent',
     'Combination button intact. Clean pin, faint crease at fold.'),
    ('1962 Junior Resident Hunting License – York Co.',    1962, 'York',       'good',
     'Junior pin. Light soiling on back. Full readable stub.'),
    ('1971 Resident Hunting License – Dauphin Co.',        1971, 'Dauphin',    'mint',
     'Uncirculated. Original pin sharp, no tarnish. Rare find.'),
    ('1978 Non-Resident Hunting License – Cumberland Co.', 1978, 'Cumberland', 'fair',
     'Non-resident button present. Moderate wear consistent with age.'),
]

LISTING_DATA = [
    # (title_suffix, year, county_name, listing_type, condition, description, price_info)
    # price_info keys vary by type: starting_price / buy_now_price / trade_notes
    ('1935 Resident Hunting License – Bucks Co.', 1935, 'Bucks', 'auction', 'excellent',
     'A stunning early Depression-era button. Both button and stub survive in excellent '
     'condition with bright original lithography. Rare to find intact at this age.',
     {'starting_price': '18.00'}),

    ('1948 Resident Combination License – Monroe Co.', 1948, 'Monroe', 'auction', 'very_good',
     'Post-war hunting & fishing combination. Full stub, original pin. Light aging on '
     'the stub edges, button retains full color.',
     {'starting_price': '12.00', 'reserve_price': '25.00'}),

    ('1967 Resident Hunting License – Pike Co.', 1967, 'Pike', 'buy_now', 'good',
     'Mid-century license, complete with stub and button. Typical light foxing on stub. '
     'A solid addition to any Pennsylvania collection.',
     {'buy_now_price': '22.00'}),

    ('1983 Resident Hunting License – Centre Co.', 1983, 'Centre', 'buy_now', 'mint',
     'Near-mint 1980s license. Full stub, no fading, pin retains its point. '
     'Ideal for someone building a run of Centre County issues.',
     {'buy_now_price': '15.00'}),

    ('1958 Resident Hunting License – Lycoming Co.', 1958, 'Lycoming', 'trade', 'very_good',
     'Late-50s button in very good shape. Slight patina on the pin, stub is clean. '
     'Open to trades for other 1950s Pennsylvania hunting or fishing licenses.',
     {'trade_notes': 'Looking for other 1950s Pennsylvania licenses, particularly fishing or combination.'}),
]

LISTING_IMAGES = [
    'listings/test_listing_image_001.png',
    'listings/test_listing_image_002.png',
    'listings/test_listing_image_003.png',
    'listings/test_listing_image_004.png',
    'listings/test_listing_image_005.png',
]

COLLECTION_IMAGES = [
    'collections/test_collection_image_001.png',
    'collections/test_collection_image_002.png',
    'collections/test_collection_image_003.png',
    'collections/test_collection_image_004.png',
    'collections/test_collection_image_005.png',
]


class Command(BaseCommand):
    help = 'Seed demo listings and collection items for local showcase.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Remove existing demo data before seeding.',
        )

    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write('Removing existing demo data first…')
            _remove_demo_data(self.stdout)

        demo_user = _get_or_create_demo_user(self.stdout)
        pa = State.objects.filter(code='PA').first()
        if not pa:
            self.stderr.write('Pennsylvania state not found — run seed_states first.')
            return

        county_map = {
            gu.name: gu
            for gu in GeographicUnit.objects.filter(state=pa)
        }
        all_license_types = list(LicenseType.objects.filter(state=pa))
        if not all_license_types:
            all_license_types = list(LicenseType.objects.all())

        # ── Collection items ──────────────────────────────────────────────────
        collection_items = []
        for idx, (title_suffix, year, county_name, condition, desc) in enumerate(COLLECTION_DATA):
            title = f'{DEMO_PREFIX}{title_suffix}'
            if CollectionItem.objects.filter(title=title, owner=demo_user).exists():
                self.stdout.write(f'  skip (exists): {title}')
                collection_items.append(CollectionItem.objects.get(title=title, owner=demo_user))
                continue

            county_ref = county_map.get(county_name)
            item = CollectionItem.objects.create(
                owner=demo_user,
                title=title,
                description=desc,
                license_year=year,
                state=pa,
                county=county_ref,
                condition_grade=condition,
                is_public=True,
                trade_eligible=True,
                resident_status='resident',
            )
            if all_license_types:
                item.license_types.set(random.sample(all_license_types, min(2, len(all_license_types))))

            CollectionItemImage.objects.create(
                collection_item=item,
                image=COLLECTION_IMAGES[idx],
                sort_order=0,
            )
            collection_items.append(item)
            self.stdout.write(f'  created collection item: {title}')

        # ── Listings ──────────────────────────────────────────────────────────
        trade_collection_item = collection_items[-1] if collection_items else None

        for idx, (title_suffix, year, county_name, ltype, condition, desc, price_info) in enumerate(LISTING_DATA):
            title = f'{DEMO_PREFIX}{title_suffix}'
            if Listing.objects.filter(title=title, seller=demo_user).exists():
                self.stdout.write(f'  skip (exists): {title}')
                continue

            county_ref = county_map.get(county_name)
            auction_end = timezone.now() + timedelta(days=7) if ltype == 'auction' else None

            listing = Listing(
                seller=demo_user,
                title=title,
                description=desc,
                license_year=year,
                state=pa,
                county=county_name,
                county_ref=county_ref,
                listing_type=ltype,
                condition_grade=condition,
                status='active',
                featured_image=LISTING_IMAGES[idx],
                resident_status='resident',
                auction_end=auction_end,
                auto_relist=False,
            )

            if ltype == 'auction':
                listing.starting_price = price_info.get('starting_price', '10.00')
                listing.reserve_price = price_info.get('reserve_price')
            elif ltype == 'buy_now':
                listing.buy_now_price = price_info.get('buy_now_price', '20.00')
            elif ltype == 'trade':
                listing.trade_notes = price_info.get('trade_notes', '')
                listing.allow_cash = True
                listing.source_collection_item = trade_collection_item

            listing.save()

            if all_license_types:
                listing.license_types.set(random.sample(all_license_types, min(2, len(all_license_types))))

            self.stdout.write(f'  created listing ({ltype}): {title}')

        self.stdout.write(self.style.SUCCESS(
            f'Demo seed complete. '
            f'Seller account: {DEMO_USERNAME} / password: demo1234'
        ))


def _get_or_create_demo_user(stdout):
    user, created = User.objects.get_or_create(
        username=DEMO_USERNAME,
        defaults={
            'email': DEMO_EMAIL,
            'first_name': 'Demo',
            'last_name': 'Seeder',
            'is_active': True,
        },
    )
    if created:
        user.set_password('demo1234')
        user.save()
        stdout.write(f'Created demo user: {DEMO_USERNAME}')
    else:
        stdout.write(f'Using existing demo user: {DEMO_USERNAME}')

    # Demo listings must be fully sellable: without a default shipping address a
    # buyer gets blocked at payment for a seller-side gap.
    from apps.accounts.models import Address
    profile = user.profile
    if not profile.shipping_address_id:
        address, _ = Address.objects.get_or_create(
            user=user,
            line1='2001 Elmerton Ave',
            defaults={
                'full_name': 'Demo Seeder',
                'city': 'Harrisburg',
                'state': 'PA',
                'postal_code': '17110',
                'country': 'US',
                'is_default': True,
            },
        )
        profile.shipping_address = address
        stdout.write('Added default shipping address for demo user.')
    if not profile.email_verified or not profile.phone_verified:
        profile.email_verified = True
        profile.phone_verified = True
    profile.save()
    return user


def _remove_demo_data(stdout):
    try:
        demo_user = User.objects.get(username=DEMO_USERNAME)
    except User.DoesNotExist:
        stdout.write('No demo user found — nothing to remove.')
        return

    listing_qs = Listing.objects.filter(
        seller=demo_user,
        title__startswith=DEMO_PREFIX,
    )
    n_listings = listing_qs.count()
    listing_qs.delete()

    item_qs = CollectionItem.objects.filter(
        owner=demo_user,
        title__startswith=DEMO_PREFIX,
    )
    n_items = item_qs.count()
    item_qs.delete()

    stdout.write(f'Removed {n_listings} listings and {n_items} collection items.')
