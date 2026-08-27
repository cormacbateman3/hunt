"""The two external reads — kept in one file so swapping either is a
one-file change.

Both fail SOFT: a missing key or a network error returns None and the
caller records the scan as skipped/failed rather than blocking anything.
The scanner reviews after delivery; it is never in the send path.
"""

import json
import logging
from functools import lru_cache
from pathlib import Path

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

OPENAI_MODERATION_URL = 'https://api.openai.com/v1/moderations'
CONFIG_DIR = Path(__file__).resolve().parent / 'config'


def openai_moderation(text):
    """Score one message with OpenAI's free moderation endpoint.

    Returns {'categories': {...bool}, 'scores': {...float}} or None when
    the key is absent or the call fails.
    """
    api_key = getattr(settings, 'OPENAI_API_KEY', '')
    if not api_key:
        return None
    try:
        response = requests.post(
            OPENAI_MODERATION_URL,
            headers={'Authorization': f'Bearer {api_key}'},
            json={'model': 'omni-moderation-latest', 'input': text[:8000]},
            timeout=20,
        )
        if response.status_code != 200:
            # The body says WHY (billing not set up, real rate limit…) —
            # the status line alone sent us hunting once already.
            logger.warning('moderation classifier failed: HTTP %s — %s',
                           response.status_code, response.text[:300])
            return None
        result = response.json()['results'][0]
        return {
            'categories': result.get('categories', {}),
            'scores': result.get('category_scores', {}),
        }
    except Exception as err:
        logger.warning('moderation classifier failed: %s', err)
        return None


@lru_cache(maxsize=1)
def escalation_prompt():
    """The intent-judgment prompt lives in a reviewed file, not in code —
    same rule as the prefill prompts (externalize-model-prompts)."""
    return (CONFIG_DIR / 'escalation_prompt.md').read_text(encoding='utf-8')


def claude_escalation(transcript, model):
    """Ask Claude whether a flagged thread is a real concern, in context.

    Returns {'concern': bool, 'severity': 'review'|'urgent',
    'category': str, 'rationale': str} or None on any failure.
    """
    try:
        import anthropic
    except ImportError:
        logger.warning('anthropic package unavailable; escalation skipped')
        return None
    # A dedicated key for this workload (best practice: one key per
    # process, so a leak or a rotation touches one thing and the console
    # shows who spent what). Falls back to the shared key so nothing
    # breaks while only one exists.
    import os
    api_key = (
        getattr(settings, 'ANTHROPIC_MODERATION_API_KEY', '')
        or os.getenv('ANTHROPIC_MODERATION_API_KEY')
        or getattr(settings, 'ANTHROPIC_API_KEY', '')
        or os.getenv('ANTHROPIC_API_KEY')
    )
    if not api_key:
        return None
    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=300,
            system=escalation_prompt(),
            messages=[{'role': 'user', 'content': transcript}],
        )
        raw = response.content[0].text.strip()
        # The prompt demands bare JSON; tolerate a fenced block anyway.
        if raw.startswith('```'):
            raw = raw.strip('`')
            raw = raw[raw.index('{'):raw.rindex('}') + 1]
        verdict = json.loads(raw)
        if not isinstance(verdict.get('concern'), bool):
            return None
        verdict.setdefault('severity', 'review')
        verdict.setdefault('category', '')
        verdict.setdefault('rationale', '')
        return verdict
    except Exception as err:
        logger.warning('moderation escalation failed: %s', err)
        return None
