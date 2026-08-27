"""The watcher, held to its own rules.

The system only finds; humans decide. Claude may clear low-severity
noise in context, but an urgent hit from any tier always reaches a
human. Nothing here ever blocks a send.
"""

from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from apps.messaging import services as messaging_services
from apps.messaging.models import Conversation, Message
from apps.moderation import services
from apps.moderation.models import (
    MessageScan,
    ModerationEvent,
    ModerationSettings,
    WatchTerm,
)
from apps.notifications.models import Notification


class ModerationBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        def verified(name, staff=False):
            user = User.objects.create_user(name, password='pw', is_staff=staff)
            profile = user.profile
            profile.email_verified = True
            profile.save(update_fields=['email_verified'])
            return user

        cls.walt = verified('mod_walt')
        cls.john = verified('mod_john')
        cls.admin = verified('mod_admin', staff=True)
        cls.config = ModerationSettings.objects.create()

    def setUp(self):
        cache.clear()

    def _thread(self):
        conv, _ = messaging_services.start_conversation(self.walt, self.john)
        return conv

    def _message(self, body, sender=None, conv=None):
        conv = conv or self._thread()
        return Message.objects.create(
            conversation=conv, sender=sender or self.walt, body=body)


class WatchTermTests(ModerationBase):
    def test_a_friendly_insult_is_nobodys_business(self):
        with patch.object(services.providers, 'openai_moderation', return_value=None):
            scan = services.scan_message(self._message("you're an idiot, love it"))
        self.assertNotEqual(scan.status, 'flagged')
        self.assertEqual(ModerationEvent.objects.count(), 0)

    def test_age_disclosure_pages_staff(self):
        with patch.object(services.providers, 'openai_moderation', return_value=None), \
             patch.object(services.providers, 'claude_escalation', return_value=None):
            scan = services.scan_message(self._message("i'm 13 btw"))
        self.assertEqual(scan.status, 'flagged')
        event = ModerationEvent.objects.get()
        self.assertEqual(event.severity, 'urgent')
        self.assertEqual(event.category, 'grooming')
        self.assertTrue(Notification.objects.filter(
            user=self.admin, notification_type='moderation_urgent').exists())

    def test_a_direct_threat_pages_staff(self):
        with patch.object(services.providers, 'openai_moderation', return_value=None), \
             patch.object(services.providers, 'claude_escalation', return_value=None):
            services.scan_message(self._message('I will find you and hurt you'))
        self.assertEqual(
            ModerationEvent.objects.filter(severity='urgent', category='threat').count(), 1)

    def test_fee_avoidance_talk_is_left_alone(self):
        with patch.object(services.providers, 'openai_moderation', return_value=None):
            scan = services.scan_message(self._message(
                'want to do this one off the platform and skip the fee?'))
        self.assertNotEqual(scan.status, 'flagged')
        self.assertEqual(ModerationEvent.objects.count(), 0)


class ClassifierTests(ModerationBase):
    def _scores(self, **scores):
        return {'categories': {}, 'scores': scores}

    def test_a_harassment_score_flags_for_review(self):
        with patch.object(services.providers, 'openai_moderation',
                          return_value=self._scores(harassment=0.55)), \
             patch.object(services.providers, 'claude_escalation', return_value=None):
            scan = services.scan_message(self._message('some borderline message'))
        self.assertEqual(scan.status, 'flagged')
        event = ModerationEvent.objects.get()
        self.assertEqual(event.severity, 'review')

    def test_an_urgent_category_over_threshold_pages(self):
        with patch.object(services.providers, 'openai_moderation',
                          return_value=self._scores(**{'sexual/minors': 0.95})), \
             patch.object(services.providers, 'claude_escalation', return_value=None):
            services.scan_message(self._message('...'))
        self.assertTrue(ModerationEvent.objects.filter(severity='urgent').exists())

    def test_no_key_means_skipped_never_silently_clean(self):
        with patch.object(services.providers, 'openai_moderation', return_value=None):
            scan = services.scan_message(self._message('a perfectly plain message'))
        self.assertEqual(scan.status, 'skipped')


class EscalationTests(ModerationBase):
    def test_claude_may_clear_low_severity_banter(self):
        verdict = {'concern': False, 'severity': 'review',
                   'category': '', 'rationale': 'Two friends ribbing each other.'}
        with patch.object(services.providers, 'openai_moderation',
                          return_value={'categories': {}, 'scores': {'harassment': 0.5}}), \
             patch.object(services.providers, 'claude_escalation', return_value=verdict):
            scan = services.scan_message(self._message('shut up you old goat, see you Saturday'))
        self.assertEqual(scan.status, 'clean')
        self.assertEqual(ModerationEvent.objects.count(), 0)

    def test_claude_can_never_veto_an_urgent_hit(self):
        verdict = {'concern': False, 'severity': 'review',
                   'category': '', 'rationale': 'Probably nothing.'}
        with patch.object(services.providers, 'openai_moderation', return_value=None), \
             patch.object(services.providers, 'claude_escalation', return_value=verdict):
            scan = services.scan_message(self._message("i'm 13 btw"))
        self.assertEqual(scan.status, 'flagged')
        self.assertTrue(ModerationEvent.objects.filter(severity='urgent').exists())

    def test_claudes_rationale_becomes_the_summary(self):
        verdict = {'concern': True, 'severity': 'review', 'category': 'harassment',
                   'rationale': 'Sustained hostility aimed at one person.'}
        with patch.object(services.providers, 'openai_moderation',
                          return_value={'categories': {}, 'scores': {'harassment': 0.6}}), \
             patch.object(services.providers, 'claude_escalation', return_value=verdict):
            services.scan_message(self._message('...'))
        event = ModerationEvent.objects.get()
        self.assertEqual(event.summary, 'Sustained hostility aimed at one person.')
        self.assertEqual(event.source, 'escalation')


class HeatedThreadTests(ModerationBase):
    def test_both_sides_flagged_surfaces_the_thread_once(self):
        conv = self._thread()
        verdict = {'concern': True, 'severity': 'review',
                   'category': 'heated', 'rationale': 'Escalating.'}
        with patch.object(services.providers, 'openai_moderation',
                          return_value={'categories': {}, 'scores': {'harassment': 0.6}}), \
             patch.object(services.providers, 'claude_escalation', return_value=verdict):
            services.scan_message(self._message('you are a liar', self.walt, conv))
            services.scan_message(self._message('you are a crook', self.john, conv))
            services.scan_message(self._message('everyone should know', self.walt, conv))
        heated = ModerationEvent.objects.filter(source='heated')
        self.assertEqual(heated.count(), 1)
        self.assertIn('a genuine fight', heated.get().summary)

    def test_one_sided_hostility_surfaces_as_sustained(self):
        """One person piling on is not a fight, but it is not nothing —
        the rollup names the shape so a reviewer sees it at a glance
        (each message already made its own per-message event)."""
        conv = self._thread()
        verdict = {'concern': True, 'severity': 'review',
                   'category': 'harassment', 'rationale': 'Hostile.'}
        with patch.object(services.providers, 'openai_moderation',
                          return_value={'categories': {}, 'scores': {'harassment': 0.6}}), \
             patch.object(services.providers, 'claude_escalation', return_value=verdict):
            for text in ('one', 'two', 'three', 'four'):
                services.scan_message(self._message(text, self.walt, conv))
        heated = ModerationEvent.objects.filter(source='heated')
        self.assertEqual(heated.count(), 1)
        self.assertIn('sustained hostility', heated.get().summary)


class SweepTests(ModerationBase):
    def test_a_settled_scan_leaves_the_queue(self):
        self._message('first')
        with patch.object(services.providers, 'openai_moderation',
                          return_value={'categories': {}, 'scores': {}}):
            counts = services.scan_pending(config=self.config)
            self.assertEqual(counts['scanned'], 1)
            counts = services.scan_pending(config=self.config)
            self.assertEqual(counts['scanned'], 0)

    def test_the_master_switch_really_switches(self):
        self.config.scanning_enabled = False
        self.config.save(update_fields=['scanning_enabled'])
        scan = services.scan_message(self._message('anything'), services.get_settings())
        self.assertEqual(scan.status, 'skipped')
        self.assertEqual(ModerationEvent.objects.count(), 0)


class SkippedRetriesTests(ModerationBase):
    """Skipped means "not yet", never "never". The owner's live test found
    the hole: OpenAI answered 429 on every call, all seven scans recorded
    'skipped' — and nothing would ever have come back for them."""

    def test_a_skipped_scan_is_redone_when_the_classifier_returns(self):
        msg = self._message('a slur the watch terms never listed')
        with patch.object(services.providers, 'openai_moderation', return_value=None):
            first = services.scan_message(msg, self.config)
        self.assertEqual(first.status, 'skipped')

        with patch.object(services.providers, 'openai_moderation',
                          return_value={'categories': {}, 'scores': {'harassment': 0.55}}), \
             patch.object(services.providers, 'claude_escalation', return_value=None):
            counts = services.scan_pending(config=self.config)

        self.assertEqual(counts, {'scanned': 1, 'flagged': 1})
        # Redone in place — still one row per message.
        self.assertEqual(MessageScan.objects.count(), 1)
        self.assertEqual(MessageScan.objects.get().status, 'flagged')
        self.assertTrue(ModerationEvent.objects.exists())

    def test_settled_scans_are_never_rescanned(self):
        self._message('a perfectly plain message')
        with patch.object(services.providers, 'openai_moderation',
                          return_value={'categories': {}, 'scores': {}}) as classifier:
            services.scan_pending(config=self.config)
            services.scan_pending(config=self.config)
        self.assertEqual(classifier.call_count, 1)

    def test_retries_never_starve_a_fresh_message_of_its_first_pass(self):
        """The watch-term tier works with no key at all — a provider
        outage backing up retries must not delay a new message's first
        look. Never-scanned goes first; retries take the leftovers."""
        old = self._message('old and skipped')
        with patch.object(services.providers, 'openai_moderation', return_value=None):
            services.scan_message(old, self.config)
        fresh = self._message('fresh, never scanned')

        with patch.object(services.providers, 'openai_moderation', return_value=None):
            services.scan_pending(limit=1, config=self.config)
        self.assertTrue(MessageScan.objects.filter(message=fresh).exists())
