"""W1.18 — accepting a suggestion never guesses.

Prefill used to file every miss as a ``license_type`` suggestion, and the
admin's accept action fell back to ``addon_type`` for any field name it
didn't know. So accepting a mis-filed "Statewide" (a place) would have
created a universal add-on type called Statewide.
"""

from unittest import mock

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from apps.core.admin import accept_and_apply
from apps.core.models import LicenseType, ReferenceDataSuggestion


class AcceptSuggestionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_superuser('accept_staff', 'a@example.com', 'pw')

    def _accept(self, *suggestions):
        request = RequestFactory().post('/')
        request.user = self.staff
        modeladmin = mock.Mock()
        accept_and_apply(modeladmin, request,
                         ReferenceDataSuggestion.objects.filter(pk__in=[s.pk for s in suggestions]))
        for s in suggestions:
            s.refresh_from_db()
        return modeladmin.message_user.call_args[0][1]

    def _suggest(self, **kwargs):
        defaults = {'user': self.staff, 'suggestion_type': 'new_value',
                    'target_model': 'license_type', 'proposed_value': 'x'}
        defaults.update(kwargs)
        return ReferenceDataSuggestion.objects.create(**defaults)

    def test_a_place_filed_as_a_licence_type_is_left_for_a_person(self):
        s = self._suggest(field_name='geographic_unit', proposed_value='Statewide')
        message = self._accept(s)
        self.assertEqual(s.status, 'pending')
        self.assertFalse(LicenseType.objects.filter(name='Statewide').exists())
        self.assertIn('Left 1 pending', message)

    def test_a_real_category_still_becomes_a_value(self):
        s = self._suggest(field_name='duration', proposed_value='Season-long')
        self._accept(s)
        self.assertEqual(s.status, 'accepted')
        self.assertTrue(LicenseType.objects.filter(
            name='Season-long', category='duration', state=None).exists())

    def test_a_correction_with_nothing_to_apply_to_is_not_marked_accepted(self):
        s = self._suggest(target_model='state', field_name='name', target_id=None,
                          suggestion_type='correction')
        self._accept(s)
        self.assertEqual(s.status, 'pending')
