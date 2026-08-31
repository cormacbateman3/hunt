"""The door — and the Terms acceptance behind it.

Enforcement is only fair if you can say what somebody agreed to, so the
acceptance is recorded against a version rather than a boolean. That is the
part worth testing hardest: a strike issued under version 1.3 against a
member who joined under 1.1 is not something you could defend.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.forms import UserRegistrationForm
from apps.core.models import State, TermsAcceptance, TermsVersion


class TermsBase(TestCase):
    def setUp(self):
        self.pa, _ = State.objects.get_or_create(
            code='PA', defaults={'name': 'Pennsylvania', 'slug': 'pa-auth',
                                 'is_primary_default': True})

    def _publish(self, version='1.2', **kwargs):
        return TermsVersion.objects.create(
            version=version,
            summary=kwargs.pop(
                'summary',
                'Describe items honestly, no mystery lots, ship within the '
                'handling window, and settle disagreements between yourselves first.'),
            effective_from=kwargs.pop('effective_from', timezone.now()),
            **kwargs)

    def _registration(self, **overrides):
        data = {
            'username': 'newcomer',
            'email': 'newcomer@example.com',
            'password1': 'a-long-enough-passphrase',
            'password2': 'a-long-enough-passphrase',
            'home_state': str(self.pa.pk),
        }
        data.update(overrides)
        return data


class TermsVersionTests(TermsBase):
    def test_nothing_published_means_no_current_version(self):
        """A form that shows "version 1.0" against no record would be worse
        than one that shows no version at all."""
        self.assertIsNone(TermsVersion.current())

    def test_the_current_version_is_the_newest_already_in_force(self):
        self._publish('1.1', effective_from=timezone.now() - timezone.timedelta(days=30))
        live = self._publish('1.2')
        self._publish('2.0', effective_from=timezone.now() + timezone.timedelta(days=30))
        self.assertEqual(TermsVersion.current(), live)


class RegistrationTermsTests(TermsBase):
    def test_with_no_version_published_the_checkbox_is_not_shown(self):
        form = UserRegistrationForm()
        self.assertNotIn('accept_terms', form.fields)

        resp = self.client.get(reverse('accounts:register'))
        self.assertNotContains(resp, 'accept_terms')

    def test_with_a_version_published_you_have_to_agree(self):
        self._publish()
        form = UserRegistrationForm(data=self._registration())
        self.assertFalse(form.is_valid())
        self.assertIn('accept_terms', form.errors)

    def test_agreeing_records_which_version(self):
        terms = self._publish('1.2')
        form = UserRegistrationForm(data=self._registration(accept_terms='on'))
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()

        acceptance = TermsAcceptance.objects.get(user=user)
        self.assertEqual(acceptance.terms, terms)
        self.assertEqual(acceptance.context, 'registration')

    def test_the_label_names_the_version(self):
        self._publish('1.2')
        form = UserRegistrationForm()
        self.assertIn('version 1.2', form.fields['accept_terms'].label)

    def test_the_summary_is_shown_beside_the_box(self):
        """A collector who reads that line knows what they signed."""
        self._publish()
        html = self.client.get(reverse('accounts:register')).content.decode()
        self.assertIn('no mystery lots', html)

    def test_a_version_that_somebody_accepted_cannot_be_deleted(self):
        terms = self._publish()
        user = User.objects.create_user('tv_user')
        TermsAcceptance.objects.create(user=user, terms=terms)

        from django.db.models import ProtectedError
        with self.assertRaises(ProtectedError):
            terms.delete()

    def test_nobody_accepts_the_same_version_twice(self):
        terms = self._publish()
        user = User.objects.create_user('tv_twice')
        TermsAcceptance.objects.create(user=user, terms=terms)
        TermsAcceptance.objects.get_or_create(user=user, terms=terms)
        self.assertEqual(TermsAcceptance.objects.filter(user=user).count(), 1)


class RegistrationHomeStateTests(TermsBase):
    """10.21: home state is the one thing the whole site personalises on,
    so the door asks for it — and only for it, never the county."""

    def test_home_state_is_required(self):
        form = UserRegistrationForm(data=self._registration(home_state=''))
        self.assertFalse(form.is_valid())
        self.assertIn('home_state', form.errors)

    def test_joining_records_where_home_is(self):
        form = UserRegistrationForm(data=self._registration())
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.profile.home_state, self.pa)

    def test_federal_is_not_a_place_anybody_lives(self):
        State.objects.get_or_create(
            code='FD', defaults={'name': 'Federal', 'slug': 'fd-auth'})
        form = UserRegistrationForm()
        self.assertNotIn(
            'FD', [state.code for state in form.fields['home_state'].queryset])

    def test_the_door_asks_for_it_and_says_why(self):
        html = self.client.get(reverse('accounts:register')).content.decode()
        self.assertIn('Home state', html)
        self.assertIn('Choose your state', html)
        self.assertIn('Filters and new records open on your state', html)

    def test_leaving_it_blank_fails_on_the_page_not_in_the_void(self):
        resp = self.client.post(
            reverse('accounts:register'), self._registration(home_state=''))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Say which state is home')
        self.assertFalse(User.objects.filter(username='newcomer').exists())

    def test_the_whole_door_works_end_to_end(self):
        resp = self.client.post(
            reverse('accounts:register'), self._registration())
        self.assertRedirects(resp, reverse('accounts:login'))
        user = User.objects.get(username='newcomer')
        self.assertEqual(user.profile.home_state, self.pa)


class AuthPageTests(TermsBase):
    def test_the_navigation_comes_off_both_doors(self):
        """Four zone links on a sign-in page are just noise."""
        for url in (reverse('accounts:login'), reverse('accounts:register')):
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                self.assertNotIn('kb-topbar', html)
                self.assertIn('au-form-no', html)

    def test_a_real_address_and_a_promise_of_a_real_reply(self):
        """Auth is where older users get stranded, and a dead end here costs
        the member entirely."""
        html = self.client.get(reverse('accounts:login')).content.decode()
        self.assertIn('help@keystonebid.com', html)
        self.assertIn('a person will answer', html)

    def test_the_password_rules_are_a_checklist_not_a_paragraph(self):
        html = self.client.get(reverse('accounts:register')).content.decode()
        self.assertIn('au-rules', html)
        self.assertIn('At least 10 characters', html)

    def test_the_gates_are_named_before_you_hit_them(self):
        """Discovering the rules at the moment you try to list something is
        what makes them feel arbitrary."""
        html = self.client.get(reverse('accounts:register')).content.decode()
        self.assertIn('An address to sell, a phone number to trade', html)

    def test_the_figures_are_counted_not_invented(self):
        resp = self.client.get(reverse('accounts:register'))
        stats = resp.context['stats']
        self.assertEqual(stats['listings'], 0)
        self.assertEqual(stats['collectors'], User.objects.filter(is_active=True).count())


class SettingsRoomTests(TestCase):
    """Six stacked cards became ten named rooms. What matters is that each
    one is reachable, names itself, and loads only its own work."""

    @classmethod
    def setUpTestData(cls):
        cls.member = User.objects.create_user('st_member', password='pw')

    def setUp(self):
        self.client.force_login(self.member)

    def test_every_room_renders(self):
        from apps.accounts.settings_rooms import ROOMS
        for key, (label, _blurb) in ROOMS.items():
            with self.subTest(room=key):
                resp = self.client.get(reverse('accounts:profile_edit'), {'room': key})
                self.assertEqual(resp.status_code, 200)
                # Labels carry an ampersand and the template escapes it.
                self.assertContains(resp, label.replace('&', '&amp;'))

    def test_an_unknown_room_lands_somewhere_useful(self):
        """A bookmark to a renamed room should not be an error page."""
        resp = self.client.get(reverse('accounts:profile_edit'), {'room': 'nonsense'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['room'], 'profile')

    def test_the_four_groups_are_all_in_the_rail(self):
        html = self.client.get(reverse('accounts:profile_edit')).content.decode()
        for group in ('Me', 'Hunting', 'Selling', 'Account'):
            self.assertIn(f'>{group}</h2>', html)

    def test_a_room_loads_only_its_own_work(self):
        """Building all ten every time is how a settings page ends up doing
        thirty queries to show one text field."""
        profile = self.client.get(reverse('accounts:profile_edit'), {'room': 'profile'})
        self.assertNotIn('blocked_users', profile.context)
        self.assertNotIn('addresses', profile.context)

        privacy = self.client.get(reverse('accounts:profile_edit'), {'room': 'privacy'})
        self.assertIn('blocked_users', privacy.context)

    def test_the_county_is_picked_not_typed(self):
        from apps.core.models import GeographicUnit, State
        pa, _ = State.objects.get_or_create(
            code='PA', defaults={'name': 'Pennsylvania', 'slug': 'pa',
                                 'is_primary_default': True})
        lycoming = GeographicUnit.objects.create(state=pa, name='Lycoming', slug='st-lyc')

        resp = self.client.post(reverse('accounts:profile_edit'), {
            'display_name': 'Ray Miller', 'bio': '', 'showcase_layout': 'case',
            'home_state': pa.pk, 'home_county': lycoming.pk,
        })
        self.assertEqual(resp.status_code, 302)
        self.member.profile.refresh_from_db()
        self.assertEqual(self.member.profile.home_county, lycoming)

    def test_the_county_list_follows_the_state(self):
        """10.22: switch Maryland to Pennsylvania and the county list
        follows. The server half always worked (the test below proves a
        posted pair saves); this locks the browser half the room never
        had — the cascade script, wired to the two real fields."""
        html = self.client.get(
            reverse('accounts:profile_edit'), {'room': 'profile'}).content.decode()
        self.assertIn('/api/geo-units/', html)
        self.assertIn("getElementById('id_home_state')", html)
        self.assertIn("getElementById('id_home_county')", html)

    def test_the_cascade_api_answers_the_scripts_exact_question(self):
        """The script asks by pk — the id the state <option> carries."""
        from apps.core.models import GeographicUnit, State
        pa, _ = State.objects.get_or_create(
            code='PA', defaults={'name': 'Pennsylvania', 'slug': 'pa3',
                                 'is_primary_default': True})
        lycoming = GeographicUnit.objects.create(
            state=pa, name='Lycoming', slug='st-lyc-api')
        resp = self.client.get('/api/geo-units/', {'state': pa.pk})
        names = [unit['name'] for unit in resp.json()['results']]
        self.assertIn('Lycoming', names)

    def test_a_county_from_the_wrong_state_is_refused(self):
        from apps.core.models import GeographicUnit, State
        pa, _ = State.objects.get_or_create(
            code='PA', defaults={'name': 'Pennsylvania', 'slug': 'pa2',
                                 'is_primary_default': True})
        md, _ = State.objects.get_or_create(
            code='MD', defaults={'name': 'Maryland', 'slug': 'md'})
        baltimore = GeographicUnit.objects.create(state=md, name='Baltimore', slug='st-balt')

        resp = self.client.post(reverse('accounts:profile_edit'), {
            'display_name': '', 'bio': '', 'showcase_layout': 'case',
            'home_state': pa.pk, 'home_county': baltimore.pk,
        })
        self.assertEqual(resp.status_code, 200)
        self.member.profile.refresh_from_db()
        self.assertIsNone(self.member.profile.home_county)
