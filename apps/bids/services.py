"""
Business logic for bidding system
"""
import logging
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.listings.models import Listing
from .models import Bid, ProxyMax
from apps.enforcement.services import enforce_capability
from apps.notifications.services import create_notification

logger = logging.getLogger(__name__)


def minimum_bid_for(listing):
    """Lowest acceptable next bid: the starting price for the first bid,
    current bid + seller-set increment after. Single source of truth for the
    detail page, the bid form, and place_bid."""
    increment = listing.bid_increment or Decimal('1')
    if increment <= 0:
        increment = Decimal('1')
    if listing.current_bid:
        return listing.current_bid + increment
    return listing.starting_price or increment


def _crown(listing, bidder, amount, is_proxy=False):
    """Write one visible price movement and make it the winning bid."""
    Bid.objects.filter(listing=listing, is_winning=True).update(is_winning=False)
    bid = Bid.objects.create(listing=listing, bidder=bidder, amount=amount,
                             is_winning=True, is_proxy=is_proxy)
    listing.current_bid = amount
    listing.save(update_fields=['current_bid'])
    return bid


def place_bid(listing, bidder, amount):
    """Place (or raise) a bidder's maximum — proxy bidding, the site's one
    auction mechanic.

    ``amount`` is the most the bidder will pay. The visible price only
    moves when someone pushes it: we answer on the leader's behalf one
    increment at a time, up to their maximum and never past it. Ties go
    to the earlier maximum. The winner pays the standing price at the
    close, not their maximum. (The eBay model, per the shop's charter —
    and the reason "outbidding yourself" stopped being possible: a higher
    number from the leader just raises their maximum.)

    Returns:
        tuple: (success: bool, message: str, level: 'success'|'warning'|'error')
    """

    if listing.listing_type != 'auction':
        return False, "Bids are only allowed on The Auction House listings", 'error'
    allowed, restriction_reason = enforce_capability(bidder, 'bid')
    if not allowed:
        return False, restriction_reason, 'error'

    # Validation that does not depend on locking first.
    if bidder == listing.seller:
        return False, "You cannot bid on your own listing", 'error'
    if not bidder.profile.email_verified:
        return False, (
            'To bid, your email must be verified. '
            f'<a href="{reverse("accounts:resend_verification")}">Resend verification email &rarr;</a>'
        ), 'error'

    # Serialize bid writes against the listing to avoid stale bid races.
    with transaction.atomic():
        locked = Listing.objects.select_for_update().get(pk=listing.pk)

        if not locked.is_active():
            return False, "This auction has ended", 'error'

        increment = locked.bid_increment or Decimal('1')
        if increment <= 0:
            increment = Decimal('1')
        reserve = locked.reserve_price
        leader_bid = (
            Bid.objects.filter(listing=locked, is_winning=True)
            .select_related('bidder')
            .first()
        )
        leader = leader_bid.bidder if leader_bid else None

        # ── The leader raising their own maximum ─────────────────────
        # The old mechanic let this create a real bid against yourself,
        # raising your own price for nobody. Now it only moves the
        # private ceiling — the visible price stays put, unless the new
        # maximum covers a reserve the old one didn't.
        if leader and leader.id == bidder.id:
            standing = ProxyMax.objects.filter(listing=locked, bidder=bidder).first()
            current_max = standing.max_amount if standing else leader_bid.amount
            if amount <= current_max:
                return False, (
                    f"Your maximum is already ${current_max:.2f} — "
                    "enter more than that to raise it."
                ), 'error'
            ProxyMax.objects.update_or_create(
                listing=locked, bidder=bidder, defaults={'max_amount': amount},
            )
            if reserve and locked.current_bid and locked.current_bid < reserve <= amount:
                _crown(locked, bidder, reserve, is_proxy=True)
                _maybe_extend(locked)
                return True, (
                    f"Maximum raised to ${amount:.2f}. That meets the reserve — "
                    f"you lead at ${reserve:.2f}."
                ), 'success'
            return True, (
                f"Maximum raised to ${amount:.2f}. You're still the high bidder "
                f"at ${locked.current_bid or leader_bid.amount:.2f} — the price only "
                "moves when somebody pushes it."
            ), 'success'

        # Seller-configured minimum increment (10.8); first bid meets the start price.
        minimum_bid = minimum_bid_for(locked)
        if amount < minimum_bid:
            if locked.current_bid:
                return False, (
                    f"Your maximum must be at least ${minimum_bid:.2f} "
                    f"(current bid ${locked.current_bid:.2f} + ${increment:.2f} increment)"
                ), 'error'
            return False, (
                f"Your maximum must be at least ${minimum_bid:.2f} — "
                "the starting price for this auction"
            ), 'error'

        ProxyMax.objects.update_or_create(
            listing=locked, bidder=bidder, defaults={'max_amount': amount},
        )

        # ── The opening bid stands at the start price ────────────────
        if not leader_bid:
            price = locked.starting_price or increment
            if reserve and amount >= reserve:
                # Covering the reserve moves the price straight to it —
                # the sale can actually happen, which serves both sides.
                price = max(price, reserve)
            _crown(locked, bidder, price)
            extended = _maybe_extend(locked)
            return True, (
                f"You're the opening bidder at ${price:.2f}. "
                f"We'll bid for you up to ${amount:.2f}."
                + (' The clock reset — two more minutes.' if extended else '')
            ), 'success'

        leader_standing = ProxyMax.objects.filter(listing=locked, bidder=leader).first()
        leader_max = leader_standing.max_amount if leader_standing else leader_bid.amount

        # ── Challenger beats the standing maximum ────────────────────
        if amount > leader_max:
            price = min(leader_max + increment, amount)
            if reserve and amount >= reserve:
                price = max(price, min(reserve, amount))
            _crown(locked, bidder, price)
            extended = _maybe_extend(locked)
            create_notification(
                user=leader,
                notification_type='outbid',
                message=(
                    f'You have been outbid on "{locked.title}". '
                    f'Current bid: ${price}'
                ),
                link_url=f'/listings/{locked.pk}/',
            )
            return True, (
                f"You're the high bidder at ${price:.2f} "
                f"(your maximum: ${amount:.2f})."
                + (' The clock reset — two more minutes.' if extended else '')
            ), 'success'

        # ── The standing maximum answers; ties keep the earlier hand ─
        price = leader_max if amount == leader_max else min(amount + increment, leader_max)
        Bid.objects.create(listing=locked, bidder=bidder, amount=amount, is_winning=False)
        _crown(locked, leader, price, is_proxy=True)
        extended = _maybe_extend(locked)
        return True, (
            f"The high bidder's maximum covers ${amount:.2f} — the price moved to "
            f"${price:.2f} and you're not ahead. Raise your maximum to take it."
            + (' The clock reset — two more minutes.' if extended else '')
        ), 'warning'


# Soft close: any bid inside the final window resets the clock to the
# window (the Bring-a-Trailer shape — "a bid in the last two minutes
# gives everyone two more minutes"). Unbounded in spirit, per the
# owner's call (2026-08-26): every reset demands new money on a binding
# bid, so a war converges on its own. The cap is a backstop against
# pathology only — at the 2-minute window, 100 resets is over three
# hours of continuous bidding, which no honest lot will ever see.
SOFT_CLOSE_WINDOW = timedelta(minutes=2)
SOFT_CLOSE_CAP = 100


def _maybe_extend(listing):
    """Reset the clock if this bid landed inside the closing window.

    Called inside place_bid's lock, after the price (or a ceiling that
    matters) moved. Sniping buys nothing: the room always gets time to
    answer.
    """
    now = timezone.now()
    if not listing.auction_end or listing.auction_end <= now:
        return False
    if listing.auction_end - now > SOFT_CLOSE_WINDOW:
        return False
    if listing.auction_extensions >= SOFT_CLOSE_CAP:
        return False
    listing.auction_end = now + SOFT_CLOSE_WINDOW
    listing.auction_extensions += 1
    listing.save(update_fields=['auction_end', 'auction_extensions', 'updated_at'])
    return True


def close_auction(listing):
    """Close one ended auction — the single authority on what a close means.

    Idempotent and row-locked, so cron, a page view, and the polling
    endpoint can all call it without stepping on each other. Cron remains
    the sweeper for lots nobody is watching; anyone actually looking gets
    the close the moment they look (dev has no cron at all, which is how
    an ended auction once sat "active" for seventeen hours).

    Returns an event string for callers that narrate:
    'sold' | 'reserve_not_met' | 'no_bids' | 'foreign_order' | '' (not ready).
    """
    from apps.orders.models import Order
    from apps.orders.services import build_order_amounts
    from apps.payments.models import PaymentTransaction

    now = timezone.now()
    with transaction.atomic():
        locked = Listing.objects.select_for_update().get(pk=listing.pk)
        if (locked.listing_type != 'auction' or locked.status != 'active'
                or not locked.auction_end or locked.auction_end > now):
            return ''

        # A seller's own bid can never win. Bid.save() and place_bid both
        # refuse self-bids, so this only fires on rows predating those
        # guards — but letting one win would mint a self-purchase Order.
        eligible = Bid.objects.filter(listing=locked).exclude(bidder_id=locked.seller_id)
        winning_bid = eligible.filter(is_winning=True).select_related('bidder').first() or (
            eligible.select_related('bidder').order_by('-amount', 'placed_at').first()
        )

        if not winning_bid:
            locked.status = 'expired'
            locked.save(update_fields=['status', 'updated_at'])
            create_notification(
                user=locked.seller,
                notification_type='auction_expired',
                message=f'Your listing "{locked.title}" expired with no bids.',
                link_url=f'/listings/{locked.pk}/',
            )
            relist_unsold(locked, now)
            return 'no_bids'

        if locked.reserve_price is not None and winning_bid.amount < locked.reserve_price:
            locked.status = 'expired'
            locked.current_bid = winning_bid.amount
            locked.save(update_fields=['status', 'current_bid', 'updated_at'])
            create_notification(
                user=locked.seller,
                notification_type='auction_expired',
                message=(
                    f'Auction for "{locked.title}" ended without meeting reserve '
                    f'(${locked.reserve_price:.2f}).'
                ),
                link_url=f'/listings/{locked.pk}/',
            )
            create_notification(
                user=winning_bid.bidder,
                notification_type='auction_expired',
                message=(
                    f'Highest bid on "{locked.title}" was below reserve; '
                    'no sale was created.'
                ),
                link_url=f'/listings/{locked.pk}/',
            )
            relist_unsold(locked, now)
            return 'reserve_not_met'

        # Order.listing is a OneToOneField: one order slot, ever. Anything
        # already in it that is not this winner's pending order — a stale
        # fixture, a cancelled release, an old buy-now — must never be
        # silently adopted as the sale. get_or_create used to do exactly
        # that: hand a $775 win to a $212 stranger's order.
        existing = Order.objects.filter(listing=locked).first()
        if existing and not (existing.status == 'pending_payment'
                             and existing.buyer_id == winning_bid.bidder_id):
            logger.error(
                'close_auction: listing %s already carries order %s '
                '(status=%s, buyer=%s) which is not winner %s\'s pending '
                'order — closing without a sale; needs a human.',
                locked.pk, existing.pk, existing.status,
                existing.buyer_id, winning_bid.bidder_id,
            )
            locked.status = 'expired'
            locked.current_bid = winning_bid.amount
            locked.save(update_fields=['status', 'current_bid', 'updated_at'])
            return 'foreign_order'

        # 10.9 consistency: a listing is delisted to 'sold' only by the
        # paid webhook, never at close. 'pending' means "won, awaiting
        # payment"; release_unpaid_auction_wins reclaims it if the winner
        # never pays. The winner pays the standing price, never their max.
        locked.status = 'pending'
        locked.current_bid = winning_bid.amount
        locked.save(update_fields=['status', 'current_bid', 'updated_at'])

        item_amount, platform_fee, total_amount = build_order_amounts(winning_bid.amount)
        order, _ = Order.objects.get_or_create(
            listing=locked,
            defaults={
                'buyer': winning_bid.bidder,
                'seller': locked.seller,
                'order_type': 'auction',
                'item_amount': item_amount,
                'shipping_amount': 0,
                'platform_fee_amount': platform_fee,
                'total_amount': total_amount,
                'status': 'pending_payment',
                'shipping_payer': locked.shipping_payer,
            },
        )
        PaymentTransaction.objects.get_or_create(order=order, defaults={'status': 'pending'})

        # Link to the review page, not straight to Stripe — same rule as
        # buy-now: the buyer sees fee, shipping and total first.
        review_path = reverse('listings:auction_win_review', kwargs={'pk': locked.pk})
        review_url = f"{settings.SITE_URL.rstrip('/')}{review_path}"
        create_notification(
            user=winning_bid.bidder,
            notification_type='auction_won',
            message=(
                f'You won "{locked.title}" for ${winning_bid.amount:.2f}. '
                f'Review and complete payment: {review_url}'
            ),
            link_url=review_path,
            dedupe_window_hours=1,
        )
        create_notification(
            user=locked.seller,
            notification_type='auction_sold',
            message=(
                f'Your listing "{locked.title}" sold for ${winning_bid.amount:.2f}. '
                f'Order #{order.pk} created.'
            ),
            link_url=f'/orders/{order.pk}/',
        )
        return 'sold'


def relist_unsold(listing, now=None):
    """Auto-relist an unsold auction if eligible. Returns the new listing
    or None. Clones the row rather than enumerating fields — an
    enumeration silently drops every column added later."""
    from apps.listings.services import seller_shipping_ready

    now = now or timezone.now()
    if not listing.auto_relist or listing.relist_count >= 3:
        return None
    if not seller_shipping_ready(listing.seller):
        create_notification(
            user=listing.seller,
            notification_type='listing_activation_blocked',
            message=(
                f'"{listing.title}" was not relisted: add a default shipping address '
                'in your Account settings first.'
            ),
            link_url=f'/listings/{listing.pk}/',
        )
        return None

    if listing.auction_end and listing.created_at:
        duration_days = max(1, round((listing.auction_end - listing.created_at).total_seconds() / 86400))
    else:
        duration_days = 7

    original = listing.original_listing or listing
    new_listing = Listing.objects.get(pk=listing.pk)
    new_listing.pk = None
    new_listing._state.adding = True
    new_listing.current_bid = None
    new_listing.scheduled_at = None
    new_listing.relist_count = listing.relist_count + 1
    new_listing.original_listing = original
    new_listing.auction_end = now + timedelta(days=duration_days)
    new_listing.status = 'active'
    new_listing.save()
    new_listing.license_types.set(listing.license_types.all())

    create_notification(
        user=listing.seller,
        notification_type='listing_relisted',
        message=(
            f'"{listing.title}" has been automatically relisted '
            f'(relist {new_listing.relist_count}/3).'
        ),
        link_url=f'/listings/{new_listing.pk}/',
    )
    return new_listing


def lazily_close(listing):
    """Close an ended-but-still-active auction the moment somebody looks.

    Cheap no-op for everything else; refreshes the instance when a close
    actually happened so the caller renders the truth.
    """
    if (listing.listing_type == 'auction' and listing.status == 'active'
            and listing.auction_end and listing.auction_end <= timezone.now()):
        if close_auction(listing):
            listing.refresh_from_db()
            return True
    return False


def get_winning_bid(listing):
    """Get the winning bid for a listing"""
    return Bid.objects.filter(listing=listing, is_winning=True).first()


def get_user_bid_on_listing(user, listing):
    """Get user's highest bid on a listing"""
    return Bid.objects.filter(
        listing=listing,
        bidder=user
    ).order_by('-amount').first()
