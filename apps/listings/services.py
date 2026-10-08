"""Listing business logic shared by views and management commands."""


def seller_shipping_ready(user) -> bool:
    """A listing may only be live when its seller has a default shipping address.

    This is the seller-side half of the checkout contract — enforced at every
    activation path (create view, scheduled go-live, auto-relist) so a buyer can
    never be blocked at payment by a seller-side gap.
    """
    profile = getattr(user, 'profile', None)
    return bool(profile and profile.shipping_address_id)


# W1.6 — the seller takes a listing down. The design's promise (6c): "You can
# cancel a lot until the first bid is in" and, for the Store, "take it down
# whenever". The piece stays on the seller's shelf; only the listing ends.
TAKE_DOWN_STATUSES = ('active', 'scheduled')


def take_down_refusal(listing, actor):
    """Why ``actor`` can't take ``listing`` down right now, or '' when they can.
    A sentence rather than a boolean, so every refusal says what it was."""
    from apps.offers.services import reserving_offer

    if actor.id != listing.seller_id:
        return 'Only the seller can take a listing down.'
    if listing.status == 'pending':
        return 'Someone is paying for it right now, so it stays up until that settles.'
    if listing.status not in TAKE_DOWN_STATUSES:
        return 'This listing is no longer on the market.'
    if listing.listing_type == 'auction' and listing.bids.exists():
        return 'It has bids, and bids stand, so the lot runs to its close.'
    if reserving_offer(listing):
        return 'You accepted an offer on it, so it stays up while the buyer pays.'
    return ''


def take_down_listing(listing, actor):
    """End the listing and close its open offers. Returns (ok, refusal)."""
    from django.db import transaction

    from apps.offers.services import close_offers_for_withdrawn_listing

    refusal = take_down_refusal(listing, actor)
    if refusal:
        return False, refusal
    with transaction.atomic():
        listing.status = 'cancelled'
        listing.save(update_fields=['status', 'updated_at'])
        close_offers_for_withdrawn_listing(listing)
    return True, ''
