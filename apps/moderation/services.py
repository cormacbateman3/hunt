"""The scan itself — tiers, verdicts, and what reaches a human.

The rules of the house:
- The scanner reviews AFTER delivery; it never blocks a send.
- It only FINDS; humans DECIDE. Nothing here hides, restricts, or bans.
- Claude may talk the system out of a low-severity flag (banter read in
  context), but an URGENT hit from any tier always reaches a human —
  the model is a filter for noise, never a veto on the serious.
"""

import logging
import re
from datetime import timedelta

from django.db.models import F, Q
from django.utils import timezone

from apps.messaging.models import Message

from . import providers
from .models import MessageScan, ModerationEvent, ModerationSettings, WatchTerm

logger = logging.getLogger(__name__)


def get_settings():
    obj = ModerationSettings.objects.order_by('id').first()
    return obj or ModerationSettings()


# ── Tier 1: watch terms ─────────────────────────────────────────────────

def match_terms(text):
    """[(term, category, severity)] for every active watch-term hit."""
    hits = []
    lowered = text.lower()
    for term in WatchTerm.objects.filter(active=True):
        try:
            if term.is_regex:
                if re.search(term.term, text, re.IGNORECASE):
                    hits.append((term.term, term.category, term.severity))
            elif term.term.lower() in lowered:
                hits.append((term.term, term.category, term.severity))
        except re.error:
            logger.warning('watch term %s is not valid regex; skipping', term.pk)
    return hits


# ── Tier 2: the classifier ──────────────────────────────────────────────

def classify(text, config):
    """(flagged_categories, urgent_categories, scores|None)."""
    result = providers.openai_moderation(text)
    if result is None:
        return [], [], None
    watched = config.watched()
    urgent = config.urgent()
    scores = result['scores'] or {}
    flagged = [c for c in watched if scores.get(c, 0) >= config.flag_threshold]
    paged = [c for c in urgent
             if c in flagged and scores.get(c, 0) >= config.urgent_threshold]
    return flagged, paged, scores


# ── Tier 3: Claude reads the thread ─────────────────────────────────────

def _transcript(message, config):
    context = (
        Message.objects.filter(conversation=message.conversation)
        .select_related('sender')
        .order_by('-created_at')[:config.escalation_context_messages]
    )
    lines = [
        f'{m.sender.username}: {m.body}'
        for m in reversed(list(context))
    ]
    marker = f'>>> The flagged message is the one from {message.sender.username}: "{message.body[:400]}"'
    return '\n'.join(lines) + '\n\n' + marker


def escalate(message, config):
    """Claude's in-context verdict, or None when unavailable."""
    return providers.claude_escalation(
        _transcript(message, config), config.escalation_model,
    )


# ── The scan of one message ─────────────────────────────────────────────

def scan_message(message, config=None):
    """Run the tiers over one message and record what a human should see.

    Returns the MessageScan — one row per message (OneToOne). A scan that
    ended 'skipped' (classifier unreachable, scanning switched off) is
    redone in place on a later sweep: skipped means "not yet", never
    "never". Clean and flagged are settled and are not rescanned.
    """
    config = config or get_settings()
    existing = MessageScan.objects.filter(message=message).first()
    if existing and existing.status != 'skipped':
        return existing

    scan = existing or MessageScan(message=message)

    if not config.scanning_enabled:
        scan.status = 'skipped'
        scan.save()
        return scan

    term_hits = match_terms(message.body)
    term_urgent = any(sev == 'urgent' for _t, _c, sev in term_hits)

    flagged_cats, urgent_cats, scores = [], [], None
    if config.use_classifier:
        flagged_cats, urgent_cats, scores = classify(message.body, config)

    is_urgent = term_urgent or bool(urgent_cats)
    is_flagged = bool(term_hits) or bool(flagged_cats)

    scan.matched_terms = [
        {'term': t, 'category': c, 'severity': s} for t, c, s in term_hits
    ]
    scan.classifier_scores = scores

    if not is_flagged:
        scan.status = 'clean' if (scores is not None or not config.use_classifier) else 'skipped'
        scan.save()
        return scan

    # Flagged. Claude may clear LOW-severity noise in context; an urgent
    # hit always reaches a human regardless of what the model thinks.
    verdict = None
    if config.use_escalation:
        verdict = escalate(message, config)
        scan.escalation_verdict = verdict
    if not is_urgent and verdict is not None and not verdict.get('concern'):
        scan.status = 'clean'
        scan.save()
        return scan

    scan.status = 'flagged'
    scan.save()

    severity = 'urgent' if (
        is_urgent or (verdict or {}).get('severity') == 'urgent'
    ) else 'review'
    category = (
        (verdict or {}).get('category')
        or (urgent_cats[0] if urgent_cats else '')
        or (flagged_cats[0] if flagged_cats else '')
        or (term_hits[0][1] if term_hits else '')
    )
    summary = (verdict or {}).get('rationale') or _plain_summary(term_hits, flagged_cats, scores)

    event = ModerationEvent.objects.create(
        conversation=message.conversation,
        message=message,
        source='escalation' if verdict else ('term' if term_hits else 'classifier'),
        severity=severity,
        category=category,
        summary=summary,
    )
    if severity == 'urgent':
        notify_staff(event)

    heated_check(message.conversation, config)
    return scan


def _plain_summary(term_hits, flagged_cats, scores):
    parts = []
    if term_hits:
        parts.append('watch terms: ' + ', '.join(t for t, _c, _s in term_hits))
    if flagged_cats:
        scored = ', '.join(
            f'{c} {scores.get(c, 0):.2f}' if scores else c for c in flagged_cats
        )
        parts.append('classifier: ' + scored)
    return '; '.join(parts)


# ── The heated-thread check ─────────────────────────────────────────────

def heated_check(conversation, config=None):
    """Surface a thread that has turned ugly — mutually OR one-sidedly.

    Each flagged message already made its own event; this is the
    thread-level rollup so a reviewer sees the shape at a glance. Two
    shapes count: a genuine fight (both sides flagged in the window) and
    sustained hostility (one sender, same window — the pile-on the
    per-message events show only one drip at a time). One open rollup
    per thread; re-checks refresh nothing.
    """
    config = config or get_settings()
    if ModerationEvent.objects.filter(
        conversation=conversation, source='heated', status='open',
    ).exists():
        return None

    window_start = timezone.now() - timedelta(hours=config.heated_window_hours)
    flagged = (
        MessageScan.objects.filter(
            message__conversation=conversation,
            status='flagged',
            message__created_at__gte=window_start,
        )
        .select_related('message')
    )
    count = flagged.count()
    if count < config.heated_message_count:
        return None
    senders = {scan.message.sender_id for scan in flagged}
    if len(senders) >= 2:
        summary = (f'{count} flagged messages from both sides in '
                   f'{config.heated_window_hours}h — a genuine fight.')
    else:
        summary = (f'{count} flagged messages from one side in '
                   f'{config.heated_window_hours}h — sustained hostility.')
    return ModerationEvent.objects.create(
        conversation=conversation,
        source='heated',
        severity='review',
        category='heated',
        summary=summary,
    )


# ── Staff notification and the sweep ────────────────────────────────────

def notify_staff(event):
    """An urgent finding pages every staff account, in-app."""
    from django.contrib.auth.models import User

    from apps.notifications.services import create_notification

    for staff in User.objects.filter(is_staff=True, is_active=True):
        create_notification(
            user=staff,
            notification_type='moderation_urgent',
            message=(f'Moderation: urgent {event.category or event.source} '
                     f'finding in conversation #{event.conversation_id}.'),
            link_url=f'/admin/moderation/moderationevent/{event.pk}/change/',
            dedupe_window_hours=0,
        )


def scan_pending(limit=None, config=None):
    """Scan every message not yet settled: never scanned, or skipped.

    Absence of a MessageScan row IS the queue — no signals, no enqueue
    step, nothing for the messaging app to know about. Skipped scans
    (classifier was unreachable) re-enter the queue BEHIND the
    never-scanned, so a provider outage can back up retries without ever
    starving a fresh message of its first pass — the watch-term tier
    works with no key at all and must see everything once, promptly.
    """
    config = config or get_settings()
    pending = (
        Message.objects.filter(is_deleted=False)
        .filter(Q(scan__isnull=True) | Q(scan__status='skipped'))
        .select_related('conversation', 'sender')
        .order_by(F('scan__pk').asc(nulls_first=True), 'created_at')
    )
    batch = pending[:limit or config.scan_batch_size]
    counts = {'scanned': 0, 'flagged': 0}
    for message in batch:
        scan = scan_message(message, config)
        counts['scanned'] += 1
        if scan.status == 'flagged':
            counts['flagged'] += 1
    return counts
