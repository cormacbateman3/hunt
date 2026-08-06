"""issue_class — a property of the issue, not an attachment (Pass 8b).

A Special Issue turkey tag is both a Turkey Tag and a Special Issue. One
category holding both would force a collector to choose between two true
things, so the class of issue is its own taxonomy category and inherits
everything the other six already have: the form field, the Other flow, the
API grouping, the browse rail.
"""

import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.core.constants import FORM_LICENSE_TYPE_CATEGORIES
from apps.core.models import LicenseType, State


class IssueClassBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.pa, _ = State.objects.get_or_create(
            code='PA',
            defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                      'min_license_year': 1913},
        )
        cls.special, _ = LicenseType.objects.get_or_create(
            name='Special Issue', category='issue_class', state=None,
            defaults={'slug': 'universal-issueclass-special-issue'})
        cls.user = User.objects.create_user('ic_user')

    def _item_data(self, **extra):
        data = {
            'item_kind': 'license', 'title': 'T', 'description': '',
            'state': str(self.pa.pk), 'license_year': '1949',
            'resident_status': 'unknown', 'condition_grade': 'good',
            'shape': 'rectangle',
        }
        data.update(extra)
        return data


class IssueClassThreadsThroughTests(IssueClassBase):
    def test_it_is_one_of_the_form_categories(self):
        self.assertIn('issue_class', FORM_LICENSE_TYPE_CATEGORIES)

    def test_the_collection_form_saves_it_onto_the_piece(self):
        from apps.collections.forms import CollectionItemForm
        from apps.collections.models import CollectionItem
        form = CollectionItemForm(
            data=self._item_data(issue_class=str(self.special.pk)),
            instance=CollectionItem(owner=self.user), user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        item = form.save()
        self.assertEqual(
            item.primary_license_type_name('issue_class'), 'Special Issue')

    def test_the_listing_form_carries_the_same_field(self):
        from apps.listings.forms import ListingForm
        form = ListingForm(user=self.user)
        self.assertIn('issue_class', form.fields)
        self.assertIn('issue_class_other', form.fields)

    def test_the_api_serves_the_new_group(self):
        response = self.client.get(
            reverse('core:license_types_api'), {'state': self.pa.pk})
        payload = json.loads(response.content)
        names = [row['name'] for row in payload['results'].get('issue_class', [])]
        self.assertIn('Special Issue', names)

    def test_an_other_issue_class_files_a_suggestion(self):
        from apps.collections.forms import CollectionItemForm
        from apps.collections.models import CollectionItem
        from apps.core.models import ReferenceDataSuggestion
        other, _ = LicenseType.objects.get_or_create(
            name='Other', category='issue_class', state=None,
            defaults={'slug': 'universal-issueclass-other'})
        form = CollectionItemForm(
            data=self._item_data(
                issue_class=str(other.pk), issue_class_other='First Day of Issue'),
            instance=CollectionItem(owner=self.user), user=self.user)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.assertTrue(
            ReferenceDataSuggestion.objects.filter(
                field_name='issue_class', proposed_value='First Day of Issue',
            ).exists())
