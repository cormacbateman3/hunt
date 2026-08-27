"""The ledger's voice — the reviewed lines and the facts they may cite."""

from django.contrib.auth.models import User
from django.test import TestCase

from apps.collections.models import CollectionItem
from apps.core.models import GeographicUnit, State

from .ledger import era_fact, line_bank, line_bank_json, line_facts
from .models import PrefillJob
from .services import job_state


class TheBankTests(TestCase):
    def test_the_bank_reads_and_keeps_its_registers(self):
        bank = line_bank()
        for key in ('bench', 'object', 'lookup', 'closing', 'winks',
                    'winks_held', 'still_reading', 'reduced_motion'):
            self.assertIn(key, bank)
        self.assertTrue(len(bank['bench']) >= 4)

    def test_the_page_never_receives_the_held_winks(self):
        # The red lines are written but held for the owner's call (4d).
        shipped = line_bank_json()
        self.assertNotIn('winks_held', shipped)
        self.assertNotIn('meatloaf', shipped)
        self.assertIn('bench', shipped)

    def test_an_exact_year_beats_its_decade(self):
        self.assertIn('1943', era_fact(1943))
        self.assertIn('Depression', era_fact(1934))
        self.assertEqual(era_fact(None), '')
        self.assertEqual(era_fact('not-a-year'), '')


class TheFactsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('lf_user', password='pw')
        cls.pa, _ = State.objects.get_or_create(
            code='PA',
            defaults={'name': 'Pennsylvania', 'slug': 'pennsylvania',
                      'min_license_year': 1913},
        )
        cls.lycoming, _ = GeographicUnit.objects.get_or_create(
            state=cls.pa, name='Lycoming',
            defaults={'unit_type': 'County', 'fips_code': '42081'},
        )

    def _job(self, fields):
        return PrefillJob(user=self.user, status='complete',
                          resolved_payload={'fields': fields})

    def test_facts_cover_the_lines_that_cite_them(self):
        CollectionItem.objects.create(owner=self.user, title='One', county=self.lycoming, state=self.pa)
        other = User.objects.create_user('lf_other', password='pw')
        CollectionItem.objects.create(owner=other, title='Two', county=self.lycoming, state=self.pa)

        job = self._job({
            'license_year': {'value': 1943, 'tier': 'high'},
            'geographic_unit': {'value': self.lycoming.pk, 'tier': 'high'},
        })
        facts = line_facts(job)
        self.assertIn('wartime', facts['era_fact'])
        self.assertEqual(facts['county_name'], 'Lycoming')
        self.assertEqual(facts['my_county_count'], 1)
        self.assertEqual(facts['site_count'], 2)
        self.assertEqual(facts['unit_label'], 'County')

    def test_a_thin_read_gets_no_facts_and_no_crash(self):
        self.assertEqual(line_facts(self._job({})), {})
        empty = PrefillJob(user=self.user, status='complete', resolved_payload=None)
        self.assertEqual(line_facts(empty), {})

    def test_the_polling_contract_carries_the_facts(self):
        job = PrefillJob.objects.create(
            user=self.user, image='prefill/x.png', status='complete',
            resolved_payload={'fields': {'license_year': {'value': 1918}}},
        )
        state = job_state(job)
        self.assertEqual(state['status'], 'complete')
        self.assertIn('1918', state['line_facts']['era_fact'])


class TheResumeTests(TestCase):
    """A failed submit reloads the page, but the read already happened —
    resume_state_json hands the job back so the ledger settles in again
    instead of vanishing with the reload."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('rs_user', password='pw')
        cls.other = User.objects.create_user('rs_other', password='pw')
        cls.job = PrefillJob.objects.create(
            user=cls.user, image='prefill/x.png', status='complete',
            resolved_payload={'fields': {'license_year': {'value': 1939, 'tier': 'high'}}},
        )

    def _request(self, user, job_id):
        from django.test import RequestFactory
        request = RequestFactory().post('/x/', {'prefill_job_id': job_id})
        request.user = user
        return request

    def test_the_owners_completed_job_comes_back(self):
        from .services import resume_state_json
        state = resume_state_json(self._request(self.user, str(self.job.pk)))
        self.assertIn('"status": "complete"', state)
        self.assertIn('1939', state)

    def test_somebody_elses_job_does_not(self):
        from .services import resume_state_json
        self.assertEqual(resume_state_json(self._request(self.other, str(self.job.pk))), 'null')

    def test_garbage_ids_are_null(self):
        from .services import resume_state_json
        self.assertEqual(resume_state_json(self._request(self.user, 'DROP TABLE')), 'null')


class TheCheckFlagTests(TestCase):
    """4e's row treatment: amber (the ✓/× pair) is for matches at or just
    above the floor, second-pass rescues, and inferences. High and medium
    otherwise render green — the server decides, because only it knows
    the floors."""

    def _payload(self, **field):
        from .services import _annotate_checks
        data = {'value': 3, 'name': 'Resident', 'score': 100, 'conf': 0.9,
                'tier': 'high', 'inferred': False}
        data.update(field)
        payload = {'fields': {'residency': data}}
        return _annotate_checks(payload)['fields']['residency']

    def test_a_clean_medium_match_is_not_flagged(self):
        marked = self._payload(tier='medium', conf=0.7)
        self.assertFalse(marked['check'])

    def test_a_near_floor_match_asks_for_a_look(self):
        from prefill import core
        floor = getattr(core, 'FUZZY_FLOOR', 80)
        marked = self._payload(score=floor + 2)
        self.assertTrue(marked['check'])

    def test_second_pass_and_inference_ask_for_a_look(self):
        self.assertTrue(self._payload(second_pass=True)['check'])
        self.assertTrue(self._payload(inferred=True)['check'])

    def test_addon_items_are_marked_one_by_one(self):
        from .services import _annotate_checks
        payload = {'fields': {'addon_type': {'items': [
            {'value': 1, 'name': 'Turkey Tag', 'score': 100, 'tier': 'high'},
            {'value': 2, 'name': 'Bear Tag', 'score': 100, 'tier': 'high',
             'second_pass': True},
        ]}}}
        items = _annotate_checks(payload)['fields']['addon_type']['items']
        self.assertFalse(items[0]['check'])
        self.assertTrue(items[1]['check'])

    def test_an_empty_read_is_left_alone(self):
        from .services import _annotate_checks
        payload = {'fields': {'residency': {'value': None, 'source_text': 'RES?'}}}
        marked = _annotate_checks(payload)['fields']['residency']
        self.assertNotIn('check', marked)
