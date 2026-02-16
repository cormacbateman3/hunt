"""
Business logic for bidding system
"""
from django.db import transaction
from apps.listings.models import Listing
from .models import Bid
from apps.enforcement.services import enforce_capability
from apps.notifications.services import create_notification


def place_bid(listing, bidder, amount):
    """
    Place a bid on a listing with validation and notifications.

    Returns:
        tuple: (success: bool, message: str)
    """

    if listing.listing_type != 'auction':
        return False, "Bids are only allowed on Auction House listings"
    allowed, restriction_reason = enforce_capability(bidder, 'bid')
    if not allowed:
        return False, restriction_reason

    # Validation that does not depend on locking first.
    if bidder == listing.seller:
        return False, "You cannot bid on your own listing"
    if not bidder.profile.email_verified:
        return False, "You must verify your email before bidding"

    # Serialize bid writes against the listing to avoid stale bid races.
    with transaction.atomic():
        locked_listing = Listing.objects.select_for_update().get(pk=listing.pk)

        if not locked_listing.is_active():
            return False, "This auction has ended"

        minimum_bid = (locked_listing.current_bid or locked_listing.starting_price or 0) + 1
        if amount < minimum_bid:
            return False, f"Bid must be at least ${minimum_bid:.2f}"

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
