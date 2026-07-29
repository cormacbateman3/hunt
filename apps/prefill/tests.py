from io import BytesIO
from unittest import mock

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from apps.accounts.models import Address
from apps.core.models import ItemCategory, LicenseType, State
from apps.listings.models import Listing
from apps.prefill import services
from apps.prefill.models import PrefillCorrection, PrefillJob

FAKE_RAW = {
    'item_kind': 'license',
    'state_name_or_abbrev': 'PENNA.',
    'license_year': 1969,
    'addon_type': ['Turkey Tag'],
    'raw_text_transcription': 'PENNA. RESIDENT HUNTING 1969 TURKEY TAG',
    'per_field_confidence': {'state_name_or_abbrev': 0.95, 'license_year': 0.95, 'addon_type': 0.9},
    'inferred_fields': [],
    'dominant_colors': [],
}


def fake_extract(fh, client):
    return {'raw': dict(FAKE_RAW), 'cost_usd': 0.004, 'latency_ms': 42.0, 'prompt_version': 'testhash'}


def png_upload(name='test.png', size=(300, 300)):
    buf = BytesIO()
    Image.new('RGB', size, 'white').save(buf, 'PNG')
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/png')


class PrefillApiTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('collector', password='pw')
        pa, _ = State.objects.get_or_create(
            code='PA', defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                                 'min_license_year': 1913, 'is_primary_default': True},
        )
        if pa.min_license_year is None:
            pa.min_license_year = 1913
            pa.save(update_fields=['min_license_year'])
        LicenseType.objects.create(state=pa, name='Turkey Tag', category='addon_type',
                                   slug='pa-addontype-turkey-tag', target_species='Turkey',
                                   instrument='tag', last_year=2011)
        ItemCategory.objects.get_or_create(slug='licenses-permits', defaults={
            'department': 'Sporting Antiques', 'name': 'Licenses & Permits', 'sort_order': 1})

    def setUp(self):
        self.client.force_login(self.user)

    def _create(self):
        with mock.patch.object(services.core, 'extract', fake_extract), \
             mock.patch.object(services.core, 'get_client', return_value=object()):
            return self.client.post(
                reverse('prefill:create_job'),
                {'image': png_upload(), 'source_form': 'collection'},
            )

    def test_job_completes_with_tiered_payload(self):
        resp = self._create()
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['status'], 'complete')
        payload = data['payload']
        self.assertEqual(payload['item_kind'], 'license')
        self.assertEqual(payload['fields']['state']['name'], 'Pennsylvania')
        addon = payload['fields']['addon_type']['items'][0]
        self.assertEqual(addon['name'], 'Turkey Tag')
        self.assertEqual(addon['tier'], 'high')
        job = PrefillJob.objects.get(pk=data['job_id'])
        self.assertEqual(job.prompt_version, 'testhash')
        self.assertEqual(job.status, 'complete')

    def test_status_endpoint_is_owner_only(self):
        resp = self._create()
        job_id = resp.json()['job_id']
        other = User.objects.create_user('rival', password='pw')
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse('prefill:job_status', args=[job_id])).status_code, 404)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('prefill:job_status', args=[job_id])).status_code, 200)

    def test_requires_auth(self):
        self.client.logout()
        resp = self.client.post(reverse('prefill:create_job'), {'image': png_upload()})
        self.assertEqual(resp.status_code, 401)

    def test_rejects_tiny_and_nonimage_uploads(self):
        resp = self.client.post(reverse('prefill:create_job'),
                                {'image': png_upload(size=(50, 50))})
        self.assertEqual(resp.status_code, 400)
        bad = SimpleUploadedFile('x.png', b'not an image', content_type='image/png')
        resp = self.client.post(reverse('prefill:create_job'), {'image': bad})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(PrefillJob.objects.count(), 0)

    @override_settings(PREFILL_RATE_PER_HOUR=2)
    def test_hourly_rate_limit(self):
        self._create()
        self._create()
        resp = self._create()
        self.assertEqual(resp.status_code, 400)
        self.assertIn('limit', resp.json()['error'].lower())

    def test_corrections_logged_and_job_linked(self):
        job_id = self._create().json()['job_id']
        resp = self.client.post(
            reverse('prefill:job_corrections', args=[job_id]),
            data='{"corrections": [{"field_name": "state", "suggested_value": 1, '
                 '"final_value": 1, "tier": "high", "was_accepted": true}]}',
            content_type='application/json',
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['logged'], 1)
        correction = PrefillCorrection.objects.get()
        self.assertEqual(correction.field_name, 'state')
        self.assertTrue(correction.was_accepted)

    @override_settings(PREFILL_BACKEND='lambda')
    def test_lambda_backend_fails_cleanly_until_wired(self):
        resp = self._create()
        self.assertEqual(resp.json()['status'], 'failed')
        self.assertIn('10.19', resp.json()['error'])


class PrefillWiringRenderTests(TestCase):
    """KBPrefill's field config is template-generated. Checkbox groups have no
    id_for_label in Django 5, so wiring one as a sel-based kind renders
    `sel: '#'` — and that invalid selector aborted init before the upload
    listener attached (the "prefill never fires" bug). Render each wired page
    through its real view and pin the config."""

    @classmethod
    def setUpTestData(cls):
        cls.seller = User.objects.create_user('wiring', password='pw')
        address = Address.objects.create(
            user=cls.seller, full_name='Wiring Seller', line1='1 Elm St',
            city='Erie', state='PA', postal_code='16501', is_default=True)
        profile = cls.seller.profile
        profile.shipping_address = address
        profile.save(update_fields=['shipping_address'])
        State.objects.get_or_create(
            code='PA', defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                                 'min_license_year': 1913, 'is_primary_default': True})

    def setUp(self):
        self.client.force_login(self.seller)

    def assertPrefillWiringValid(self, resp):
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('KBPrefill.init', html)
        self.assertNotIn("sel: '#'", html)
        self.assertIn("colors: { kind: 'checklist', name: 'colors' }", html)

    def test_listing_create_details_page(self):
        resp = self.client.get(reverse('listings:create'), {'listing_type': 'buy_now'})
        self.assertPrefillWiringValid(resp)

    def test_listing_edit_page(self):
        listing = Listing.objects.create(
            seller=self.seller, listing_type='buy_now', title='Wiring check',
            description='x', condition_grade='good', status='active')
        resp = self.client.get(reverse('listings:edit', args=[listing.pk]))
        self.assertPrefillWiringValid(resp)

    def test_collection_item_create_page(self):
        resp = self.client.get(reverse('collections:create'))
        self.assertPrefillWiringValid(resp)
