"""
Business logic for bidding system
"""
from decimal import Decimal

from django.db import transaction
from django.urls import reverse
from apps.listings.models import Listing
from .models import Bid
from apps.enforcement.services import enforce_capability
from apps.notifications.services import create_notification


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


def place_bid(listing, bidder, amount):
    """
    Place a bid on a listing with validation and notifications.

    Returns:
        tuple: (success: bool, message: str)
    """

    if listing.listing_type != 'auction':
        return False, "Bids are only allowed on The Auction House listings"
    allowed, restriction_reason = enforce_capability(bidder, 'bid')
    if not allowed:
        return False, restriction_reason

    # Validation that does not depend on locking first.
    if bidder == listing.seller:
        return False, "You cannot bid on your own listing"
    if not bidder.profile.email_verified:
        return False, (
            'To bid, your email must be verified. '
            f'<a href="{reverse("accounts:resend_verification")}">Resend verification email &rarr;</a>'
        )

    # Serialize bid writes against the listing to avoid stale bid races.
    with transaction.atomic():
        locked_listing = Listing.objects.select_for_update().get(pk=listing.pk)

        if not locked_listing.is_active():
            return False, "This auction has ended"

        # Seller-configured minimum increment (10.8); first bid meets the start price.
        minimum_bid = minimum_bid_for(locked_listing)
        if amount < minimum_bid:
            if locked_listing.current_bid:
                increment = locked_listing.bid_increment or Decimal('1')
                return False, (
                    f"Bid must be at least ${minimum_bid:.2f} "
                    f"(current bid ${locked_listing.current_bid:.2f} + ${increment:.2f} increment)"
                )
            return False, f"Bid must be at least ${minimum_bid:.2f} — the starting price for this auction"

        previous_winner = (
            Bid.objects.filter(listing=locked_listing, is_winning=True)
            .select_related('bidder')
            .first()
        )

        new_bid = Bid.objects.create(
            listing=locked_listing,
            bidder=bidder,
            amount=amount,
            is_winning=True
        )

        Bid.objects.filter(listing=locked_listing, is_winning=True).exclude(pk=new_bid.pk).update(
            is_winning=False
        )

        locked_listing.current_bid = amount
        locked_listing.save(update_fields=['current_bid'])

        if previous_winner and previous_winner.bidder_id != bidder.id:
            create_notification(
                user=previous_winner.bidder,
                notification_type='outbid',
                message=f'You have been outbid on "{locked_listing.title}". Current bid: ${amount}',
                link_url=f'/listings/{locked_listing.pk}/',
            )

    return True, f"Bid placed successfully! Your bid: ${amount:.2f}"


def get_winning_bid(listing):
    """Get the winning bid for a listing"""
    return Bid.objects.filter(listing=listing, is_winning=True).first()


def get_user_bid_on_listing(user, listing):
    """Get user's highest bid on a listing"""
    return Bid.objects.filter(
        listing=listing,
        bidder=user
    ).order_by('-amount').first()
