"""10.8 collection-form parity tests: year bounds + addon dimension clearing."""
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from apps.collections.forms import CollectionItemForm
from apps.collections.models import CollectionItem
from apps.core.models import LicenseType, State


class CollectionItemFormTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user('keeper', password='pw')
        cls.pa, _ = State.objects.get_or_create(
            code='PA', defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                                 'min_license_year': 1913, 'is_primary_default': True})
        if cls.pa.min_license_year is None:
            cls.pa.min_license_year = 1913
            cls.pa.save(update_fields=['min_license_year'])
        cls.federal, _ = State.objects.get_or_create(
            code='FD', defaults={'name': 'Federal', 'slug': 'federal', 'min_license_year': 1934})
        cls.turkey = LicenseType.objects.create(
            state=cls.pa, name='Turkey Tag', category='addon_type', slug='c-pa-turkey-tag')
        cls.residency = LicenseType.objects.create(
            state=cls.pa, name='Resident', category='residency', slug='c-pa-resident')

    def _data(self, **overrides):
        data = {
            'item_kind': 'license', 'title': 'A license', 'state': str(self.pa.pk),
            'license_year': '1942', 'condition_grade': 'good', 'colors': ['red'],
            'resident_status': 'unknown',
        }
        data.update(overrides)
        return data

    def test_year_below_state_minimum_rejected(self):
        form = CollectionItemForm(data=self._data(license_year='1899'), user=self.owner)
        self.assertFalse(form.is_valid())
        self.assertIn('license_year', form.errors)
        self.assertIn('1913', ' '.join(form.errors['license_year']))

    def test_absolute_floor_guards_null_min_state(self):
        # Federal now has a 1934 floor; a sub-floor year is rejected, not saved.
        form = CollectionItemForm(data=self._data(state=str(self.federal.pk), license_year='850'),
                                  user=self.owner)
        self.assertFalse(form.is_valid())
        self.assertIn('license_year', form.errors)

    def test_year_widget_carries_state_bounds(self):
        form = CollectionItemForm(user=self.owner, initial={'state': self.pa.pk})
        attrs = form.fields['license_year'].widget.attrs
        self.assertEqual(attrs['min'], 1913)
        self.assertEqual(attrs['max'], timezone.now().year - 25)

    def test_addon_kind_clears_hidden_base_dimensions(self):
        form = CollectionItemForm(
            data=self._data(item_kind='addon', residency=str(self.residency.pk),
                            addon_type=[str(self.turkey.pk)]),
            instance=CollectionItem(owner=self.owner), user=self.owner)
        self.assertTrue(form.is_valid(), form.errors)
        item = form.save()
        self.assertFalse(item.license_types.filter(category='residency').exists())
        self.assertTrue(item.license_types.filter(name='Turkey Tag').exists())
