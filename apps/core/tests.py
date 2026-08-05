"""Stability-pass smoke tests — one per fixed bug."""
from datetime import timedelta
from io import BytesIO

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.accounts.models import Address
from apps.collections.models import CollectionItem
from apps.core.models import State
from apps.enforcement.models import Strike
from apps.enforcement.services import enforce_deterministic_policies
from apps.favorites.models import Favorite
from apps.listings.models import Listing
from apps.orders.models import Order


def png_upload(name='listing.png'):
    buf = BytesIO()
    Image.new('RGB', (300, 300), 'white').save(buf, 'PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


def make_listing(seller, **kwargs):
    defaults = {
        'listing_type': 'auction',
        'title': 'Test 1942 License',
        'description': 'A test listing.',
        'county': 'Adams',
        'condition_grade': 'good',
        'status': 'active',
        'starting_price': 20,
        'auction_end': timezone.now() + timedelta(days=7),
        'featured_image': png_upload(),
    }
    defaults.update(kwargs)
    return Listing.objects.create(seller=seller, **defaults)


def give_address(user):
    address = Address.objects.create(
        user=user, full_name=user.username, line1='1 Main St', city='Harrisburg',
        state='PA', postal_code='17101', country='US', is_default=True,
    )
    profile = user.profile
    profile.shipping_address = address
    profile.save(update_fields=['shipping_address'])
    return address


class StabilityPassTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user('seller', password='pw')
        cls.buyer = User.objects.create_user('buyer', password='pw')
        for user in (cls.seller, cls.buyer):
            profile = user.profile
            profile.email_verified = True   # messaging gate requirement
            profile.save(update_fields=['email_verified'])
        State.objects.get_or_create(code='PA', defaults={
            'name': 'Pennsylvania', 'slug': 'pennsylvania', 'is_primary_default': True,
        })

    def test_profile_page_of_other_user_renders_with_message_button(self):
        """Was: NoReverseMatch ('messaging:compose') on any other user's profile."""
        self.client.force_login(self.buyer)
        resp = self.client.get(reverse('accounts:profile', args=[self.seller.username]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'messaging/start' if 'messaging/start' in resp.content.decode() else 'recipient_id')

    def test_message_seller_flow_renders_conversation(self):
        """Was: TemplateSyntaxError ('with' received '==') on the conversation page."""
        listing = make_listing(self.seller)
        self.client.force_login(self.buyer)
        resp = self.client.post(
            reverse('messaging:start'),
            {'recipient_id': self.seller.pk, 'listing_id': listing.pk, 'conversation_type': 'auction'},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'message-thread')

    def test_collection_item_detail_is_clickable_route(self):
        """Was: no detail route for collection items."""
        item = CollectionItem.objects.create(owner=self.seller, title='1942 Adams', is_public=True)
        resp = self.client.get(reverse('collections:item_detail', args=[item.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '1942 Adams')
        # private items stay private
        secret = CollectionItem.objects.create(owner=self.seller, title='Secret', is_public=False)
        self.assertEqual(
            self.client.get(reverse('collections:item_detail', args=[secret.pk])).status_code, 404,
        )

    def test_favorites_render_as_cards_with_links(self):
        """Was: plain text that didn't look clickable."""
        listing = make_listing(self.seller)
        item = CollectionItem.objects.create(owner=self.seller, title='Fav item', is_public=True)
        Favorite.objects.create(user=self.buyer, listing=listing)
        Favorite.objects.create(user=self.buyer, collection_item=item)
        self.client.force_login(self.buyer)
        resp = self.client.get(reverse('favorites:list'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, reverse('listings:detail', args=[listing.pk]))
        self.assertContains(resp, reverse('collections:item_detail', args=[item.pk]))
        self.assertContains(resp, 'Unfavorite')

    def test_phone_readiness_item_has_no_dead_link(self):
        """Was: 'Verify phone' linked to a page with no phone verification."""
        self.client.force_login(self.buyer)
        resp = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Phone verified')
        self.assertNotContains(resp, 'Verify phone')

    def test_favicon_and_the_prefixed_nav(self):
        resp = self.client.get(reverse('home'))
        self.assertContains(resp, 'favicon')   # manifest storage hashes the filename
        self.assertContains(resp, 'The Auction House')
        self.assertContains(resp, 'The General Store')
        self.assertContains(resp, 'The Trading Block')

    def test_scheduled_listing_blocked_without_seller_address(self):
        """A listing may not go active while its seller has no default address."""
        listing = make_listing(
            self.seller, status='scheduled', scheduled_at=timezone.now() - timedelta(minutes=5),
        )
        call_command('activate_scheduled_listings')
        listing.refresh_from_db()
        self.assertEqual(listing.status, 'pending')

        give_address(self.seller)
        listing.status = 'scheduled'
        listing.save(update_fields=['status'])
        call_command('activate_scheduled_listings')
        listing.refresh_from_db()
        self.assertEqual(listing.status, 'active')

    def test_buyer_not_struck_when_seller_missing_address(self):
        """The non-payment strike must never fire for a seller-side shipping gap."""
        listing = make_listing(self.seller)
        order = Order.objects.create(
            buyer=self.buyer, seller=self.seller, listing=listing,
            order_type='auction', status='pending_payment', item_amount=25, total_amount=25,
        )
        Order.objects.filter(pk=order.pk).update(created_at=timezone.now() - timedelta(days=5))

        enforce_deterministic_policies()
        self.assertFalse(Strike.objects.filter(user=self.buyer, reason='non_payment').exists())

        give_address(self.seller)
        enforce_deterministic_policies()
        self.assertTrue(Strike.objects.filter(user=self.buyer, reason='non_payment').exists())
