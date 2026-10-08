"""Tracking we can trust — shared by orders and trades.

Two rules, both from the 2026-10-06 audit (W1.1):

1. **The webhook is a nudge, not a witness.** Shippo does not sign its
   webhooks, so a post is only ever a reason to go and ask Shippo's tracking
   API what the parcel is actually doing. A forged or replayed "DELIVERED"
   can at most cause a lookup.
2. **A typed-in tracking number must exist.** A member's own postage is
   checked with the carrier before it moves anything, so an invented number
   can't stop the non-shipment clock.
"""

import hmac

from django.conf import settings

from .providers.shippo import ShippoClient, ShippoError

# Display name → Shippo carrier token. Shipment.carrier keeps whatever the
# member or Shippo called it; the token is worked out at call time.
CARRIER_TOKENS = {
    'usps': 'usps',
    'ups': 'ups',
    'fedex': 'fedex',
    'fed ex': 'fedex',
    'dhl': 'dhl_express',
    'dhl express': 'dhl_express',
    'dhl_express': 'dhl_express',
    # Shippo's test tracking numbers (SHIPPO_TRANSIT etc.); only answers
    # under a test API key.
    'shippo': 'shippo',
}

CARRIER_CHOICES = [('USPS', 'USPS'), ('UPS', 'UPS'), ('FedEx', 'FedEx'), ('DHL', 'DHL')]

# Shippo's tracking codes that say something real. UNKNOWN (or no status at
# all) means the carrier has never seen the number; it must not move a parcel.
KNOWN_TRACKING_CODES = {
    'PRE_TRANSIT', 'TRANSIT', 'OUT_FOR_DELIVERY', 'DELIVERED', 'RETURNED', 'FAILURE',
}


def carrier_token(carrier):
    return CARRIER_TOKENS.get((carrier or '').strip().lower())


def fetch_tracking(carrier, tracking_number):
    """Ask Shippo about a parcel. Returns (code, payload); code is None when
    the carrier doesn't know the number. Raises ShippoError on transport
    failure or an unsupported carrier."""
    token = carrier_token(carrier)
    if not token:
        raise ShippoError('We can follow USPS, UPS, FedEx and DHL parcels.')
    payload = ShippoClient().get_tracking_status(carrier=token, tracking_number=tracking_number)
    status = (payload.get('tracking_status') or {}).get('status')
    code = (status or '').upper()
    return (code if code in KNOWN_TRACKING_CODES else None), payload


def verify_member_tracking(carrier, tracking_number):
    """For a tracking number a member typed in. Returns (code, payload) for a
    number the carrier knows, else raises ShippoError with a plain message."""
    try:
        code, payload = fetch_tracking(carrier, tracking_number)
    except ShippoError as exc:
        if carrier_token(carrier) is None:
            raise
        raise ShippoError(
            "We couldn't check that tracking number just now. Please try again in a few minutes."
        ) from exc
    if code is None:
        raise ShippoError(
            f"{carrier} doesn't recognise that tracking number yet. Check it, or try again "
            "once the parcel has had its first scan."
        )
    return code, payload


def label_outcome(payload, fallback_carrier=''):
    """Read a Shippo label transaction (W1.27). Returns (ready, carrier).

    ``tracking_status`` on a transaction is a word ("UNKNOWN" until the first
    scan), not an object; reading it as a dict crashed *after* the label had
    been paid for, and the retry paid again. A label is only ready when Shippo
    says SUCCESS and hands back both a tracking number and a label to print —
    a QUEUED purchase is not a label yet.
    """
    status = payload.get('tracking_status')
    carrier = status.get('carrier') if isinstance(status, dict) else ''
    ready = (
        (payload.get('status') or '').upper() == 'SUCCESS'
        and bool(payload.get('tracking_number'))
        and bool(payload.get('label_url'))
    )
    return ready, (carrier or fallback_carrier)


LABEL_NOT_READY = ("Shippo is still preparing the label. Please don't buy another; "
                   "refresh the page in a few minutes, and if it still isn't here, write to us.")


def webhook_token_ok(request):
    """Shippo can't sign webhooks, so the registered URL carries a secret
    (?token=...). Fails closed when no token is configured."""
    expected = getattr(settings, 'SHIPPO_WEBHOOK_TOKEN', '') or ''
    supplied = request.GET.get('token', '') or ''
    if not expected:
        return False
    return hmac.compare_digest(expected.encode(), supplied.encode())


def tracking_numbers_in(payload):
    """The (tracking_number, carrier) pairs a webhook post mentions — and
    nothing else from it is believed."""
    data = payload.get('data') if isinstance(payload, dict) else None
    if isinstance(data, list):
        events = data
    elif isinstance(data, dict):
        events = [data]
    else:
        events = [payload] if isinstance(payload, dict) else []
    pairs = []
    for event in events:
        if not isinstance(event, dict):
            continue
        number = event.get('tracking_number') or event.get('tracking')
        if number:
            pairs.append((str(number), event.get('carrier') or event.get('carrier_code') or ''))
    return pairs
