"""Questions on a listing — the public thread, and its one house rule.

Turn 9b's shape: answers sit indented under their questions with the seller
marked in brass, an unanswered question is visibly waiting, and **price talk
goes to the offer, not the thread**. "Would you take $150" in public
undercuts the listing for everyone reading it, so it is hidden at the moment
it is asked, with a one-line explanation and a link to the right place —
kinder than a Flag button, and it teaches the norm once instead of
moderating it forever. The asker still sees their own question, marked
Hidden, so nothing vanishes without a word.
"""

import re
import statistics
from datetime import timedelta

from django.db.models import Q

from .models import ListingQuestion

# What counts as price talk: a dollar figure, a written-out amount, or the
# stock haggling openers. Deliberately narrow — a question about a printed
# fee can trip it, but the asker sees why and can rephrase without the
# number, which costs less than a public thread full of side-deals.
PRICE_TALK = re.compile(
    r'\$\s*\d'
    r'|\b\d+\s*(?:dollars|bucks)\b'
    r'|\bwould you take\b'
    r'|\bwill you take\b'
    r'|\bbest offer\b'
    r'|\blowest (?:you|price)\b',
    re.IGNORECASE,
)


def is_price_talk(text):
    return bool(PRICE_TALK.search(text or ''))


def visible_questions(listing, viewer):
    """The thread as this viewer is allowed to see it.

    Everyone gets the public entries. A hidden question renders only to the
    person who asked it — the seller is not teased with price talk either.
    Oldest first, so the thread reads down into the ask box.
    """
    rows = listing.questions.select_related('asker')
    if viewer is not None and viewer.is_authenticated:
        rows = rows.filter(~Q(moderation_state='hidden') | Q(asker=viewer))
    else:
        rows = rows.exclude(moderation_state='hidden')
    return rows.order_by('created_at')


def asked_count(listing):
    """The public count — hidden questions are not part of the record."""
    return listing.questions.exclude(moderation_state='hidden').count()


# Below three answers the phrase is a guess wearing a number's confidence.
HABIT_MIN = 3


def answer_habit(seller):
    """"Answers within the day" — the seller's median, said as a habit.

    Returns '' when there isn't enough history, or when the honest phrase
    would be a warning rather than a habit; the thread simply says nothing,
    which is quieter than saying something damning.
    """
    deltas = [
        row.answered_at - row.created_at
        for row in ListingQuestion.objects.filter(
            listing__seller=seller, answered_at__isnull=False,
        ).only('created_at', 'answered_at')
    ]
    if len(deltas) < HABIT_MIN:
        return ''
    median = statistics.median(deltas)
    if median <= timedelta(hours=1):
        return 'answers within the hour'
    if median <= timedelta(hours=24):
        return 'answers within the day'
    if median <= timedelta(hours=72):
        return 'answers within a couple of days'
    return ''
