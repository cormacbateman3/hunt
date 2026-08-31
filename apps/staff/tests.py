"""The staff desk — the first rooms of Pass 11.

What matters: the door only opens for staff, the tiles are true counts,
the queue's two verbs record who decided, and the scan reader shows the
classifier's scores against the SAME thresholds the watcher enforces —
the bars must always agree with what the system would have done.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from apps.messaging import services as messaging_services
from apps.messaging.models import Message
from apps.moderation.models import (
    MessageScan,
    ModerationEvent,
    ModerationSettings,
)
from apps.staff.views import _score_rows


class StaffBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        def verified(name, staff=False):
            user = User.objects.create_user(name, password='pw', is_staff=staff)
            profile = user.profile
            profile.email_verified = True
            profile.save(update_fields=['email_verified'])
            return user

        cls.walt = verified('sd_walt')
        cls.john = verified('sd_john')
        cls.mod = verified('sd_mod', staff=True)
        cls.config = ModerationSettings.objects.create()
        conv, _ = messaging_services.start_conversation(cls.walt, cls.john)
        cls.conv = conv
        cls.message = Message.objects.create(
            conversation=conv, sender=cls.walt, body='you little creep, watch yourself')

    def setUp(self):
        self.client.force_login(self.mod)

    def _event(self, **overrides):
        fields = dict(
            conversation=self.conv, message=self.message, source='classifier',
            severity='review', category='harassment',
            summary='harassment scored 0.62', status='open')
        fields.update(overrides)
        return ModerationEvent.objects.create(**fields)

    def _scan(self, **overrides):
        fields = dict(
            message=self.message, status='flagged',
            classifier_scores={'harassment': 0.62, 'hate': 0.08,
                               'harassment/threatening': 0.91, 'sexual': 0.03},
            matched_terms=[{'term': 'watch yourself', 'category': 'threat',
                            'severity': 'review'}],
            escalation_verdict={'concern': True, 'severity': 'review',
                                'category': 'harassment',
                                'rationale': 'Sustained hostility aimed at one person.'})
        fields.update(overrides)
        return MessageScan.objects.create(**fields)


class TheDoorTests(StaffBase):
    def test_members_and_strangers_are_turned_away(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('staff:desk')).status_code, 302)
        self.client.force_login(self.walt)
        self.assertEqual(self.client.get(reverse('staff:desk')).status_code, 302)

    def test_staff_walk_in(self):
        resp = self.client.get(reverse('staff:desk'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Backtag')
        self.assertContains(resp, 'Django admin')


class TheDeskTests(StaffBase):
    def test_the_tiles_are_true_counts(self):
        self._event(severity='urgent')
        self._event()
        resp = self.client.get(reverse('staff:desk'))
        tiles = {tile['label']: tile['count'] for tile in resp.context['tiles']}
        self.assertEqual(tiles['Urgent moderation'], 1)
        self.assertEqual(tiles['Moderation queue'], 2)

    def test_urgent_findings_lead_the_preview(self):
        review = self._event()
        urgent = self._event(severity='urgent')
        resp = self.client.get(reverse('staff:desk'))
        preview = resp.context['preview']
        self.assertEqual(preview[0].pk, urgent.pk)
        self.assertIn(review.pk, [event.pk for event in preview])


class TheQueueTests(StaffBase):
    def test_resolving_records_who_decided(self):
        event = self._event()
        resp = self.client.post(
            reverse('staff:event_action', args=[event.pk]),
            {'action': 'resolved', 'next': reverse('staff:moderation')})
        self.assertEqual(resp.status_code, 302)
        event.refresh_from_db()
        self.assertEqual(event.status, 'resolved')
        self.assertEqual(event.resolved_by, self.mod)
        self.assertIsNotNone(event.resolved_at)

    def test_a_decided_row_cannot_be_decided_again(self):
        event = self._event(status='dismissed')
        self.client.post(reverse('staff:event_action', args=[event.pk]),
                         {'action': 'resolved'})
        event.refresh_from_db()
        self.assertEqual(event.status, 'dismissed')

    def test_the_open_view_floats_urgent_on_top(self):
        self._event()
        urgent = self._event(severity='urgent')
        resp = self.client.get(reverse('staff:moderation'))
        self.assertEqual(resp.context['rows'][0].pk, urgent.pk)

    def test_members_cannot_work_the_queue(self):
        event = self._event()
        self.client.force_login(self.walt)
        self.client.post(reverse('staff:event_action', args=[event.pk]),
                         {'action': 'resolved'})
        event.refresh_from_db()
        self.assertEqual(event.status, 'open')


class TheScanReaderTests(StaffBase):
    def test_the_bars_carry_the_scores_and_the_house_thresholds(self):
        self._scan()
        resp = self.client.get(reverse('staff:scan', args=[self.message.pk]))
        html = resp.content.decode()
        self.assertIn('0.91', html)
        self.assertIn('0.62', html)
        self.assertIn('harassment/threatening', html)
        # The ticks are the settings — defaults 0.4 and 0.8.
        self.assertIn('left: 40.0%', html)
        self.assertIn('left: 80.0%', html)

    def test_the_tones_agree_with_what_the_watcher_would_do(self):
        """The bar colours must never disagree with the scan logic."""
        rows = {row['category']: row
                for row in _score_rows(self._scan(), self.config)}
        # 0.91 in an urgent category over the urgent threshold.
        self.assertEqual(rows['harassment/threatening']['tone'], 'urgent')
        # 0.62 in a watched category over the flag threshold.
        self.assertEqual(rows['harassment']['tone'], 'flagged')
        # Watched but under the line.
        self.assertEqual(rows['hate']['tone'], 'watched')
        # Scored but deliberately not watched — plain adult 'sexual'.
        self.assertEqual(rows['sexual']['tone'], 'quiet')
        self.assertFalse(rows['sexual']['watched'])

    def test_the_loudest_score_reads_first(self):
        rows = _score_rows(self._scan(), self.config)
        self.assertEqual(rows[0]['category'], 'harassment/threatening')

    def test_claudes_read_is_shown_in_its_own_words(self):
        self._scan()
        resp = self.client.get(reverse('staff:scan', args=[self.message.pk]))
        self.assertContains(resp, 'Saw a real concern')
        self.assertContains(resp, 'Sustained hostility aimed at one person.')

    def test_a_clearing_read_wears_green(self):
        self._scan(escalation_verdict={
            'concern': False, 'severity': 'review', 'category': '',
            'rationale': 'Two friends ribbing each other.'})
        resp = self.client.get(reverse('staff:scan', args=[self.message.pk]))
        self.assertContains(resp, 'cleared')
        self.assertContains(resp, 'Two friends ribbing each other.')

    def test_an_unasked_claude_is_said_plainly(self):
        self._scan(escalation_verdict=None)
        resp = self.client.get(reverse('staff:scan', args=[self.message.pk]))
        self.assertContains(resp, 'wasn&rsquo;t asked')

    def test_the_tripped_terms_are_chips(self):
        self._scan()
        resp = self.client.get(reverse('staff:scan', args=[self.message.pk]))
        self.assertContains(resp, 'watch yourself')

    def test_hiding_is_reversible_and_never_deletes(self):
        self._scan()
        self.client.post(reverse('staff:message_action', args=[self.message.pk]),
                         {'action': 'hide'})
        self.message.refresh_from_db()
        self.assertEqual(self.message.moderation_state, 'hidden')
        self.assertFalse(self.message.is_deleted)

        self.client.post(reverse('staff:message_action', args=[self.message.pk]),
                         {'action': 'restore'})
        self.message.refresh_from_db()
        self.assertEqual(self.message.moderation_state, 'ok')

    def test_the_thread_around_it_is_on_the_page(self):
        Message.objects.create(conversation=self.conv, sender=self.john,
                               body='leave me alone, I mean it')
        self._scan()
        resp = self.client.get(reverse('staff:scan', args=[self.message.pk]))
        self.assertContains(resp, 'leave me alone, I mean it')
