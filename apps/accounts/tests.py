"""10.7 address-book tests: validation + the 'PA' suffix fix."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.accounts.forms import AddressForm


class AddressFormTests(TestCase):
    def _data(self, **overrides):
        data = {
            'full_name': 'Test User', 'line1': '1 Main St', 'line2': '',
            'city': 'Towson', 'state': 'MD', 'postal_code': '21204', 'phone': '',
        }
        data.update(overrides)
        return data

    def test_valid_address(self):
        self.assertTrue(AddressForm(self._data()).is_valid())

    def test_state_normalized_and_validated(self):
        form = AddressForm(self._data(state='md'))
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['state'], 'MD')
        self.assertFalse(AddressForm(self._data(state='Maryland')).is_valid())

    def test_zip_validated(self):
        self.assertTrue(AddressForm(self._data(postal_code='21204-1234')).is_valid())
        self.assertFalse(AddressForm(self._data(postal_code='2120')).is_valid())
        self.assertFalse(AddressForm(self._data(postal_code='ABCDE')).is_valid())


class LocationDisplayTests(TestCase):
    def test_profile_location_never_assumes_pa(self):
        """Was: 'Towson, MD' rendered as 'Towson, MD, PA'."""
        user = User.objects.create_user('marylander', password='pw')
        profile = user.profile
        profile.county = 'Towson, MD'
        profile.save(update_fields=['county'])
        resp = self.client.get(reverse('accounts:profile', args=[user.username]))
        self.assertContains(resp, 'Towson, MD')
        self.assertNotContains(resp, 'MD, PA')
