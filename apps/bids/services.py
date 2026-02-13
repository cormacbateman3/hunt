"""
Business logic for bidding system
"""
from django.db import transaction
from .models import Bid
from apps.notifications.models import Notification


def place_bid(listing, bidder, amount):
    """
    Place a bid on a listing with validation and notifications.

    Returns:
        tuple: (success: bool, message: str)
    """

    # Validation
    if bidder == listing.seller:
        return False, "You cannot bid on your own listing"

    if not bidder.profile.email_verified:
        return False, "You must verify your email before bidding"

    if not listing.is_active():
        return False, "This auction has ended"

    minimum_bid = (listing.current_bid or listing.starting_price) + 1
    if amount < minimum_bid:
        return False, f"Bid must be at least ${minimum_bid:.2f}"

    # Create bid transaction
    with transaction.atomic():
        # Create new bid
        new_bid = Bid.objects.create(
            listing=listing,
            bidder=bidder,
            amount=amount,
            is_winning=True
        )

        # Get previous winning bidder
        previous_winner = Bid.objects.filter(
            listing=listing,
            is_winning=True
        ).exclude(pk=new_bid.pk).first()

        # Mark previous bids as not winning
        Bid.objects.filter(listing=listing).exclude(pk=new_bid.pk).update(is_winning=False)

        # Update listing's current bid
        listing.current_bid = amount
        listing.save(update_fields=['current_bid'])

        # Create notification for outbid user
        if previous_winner:
            Notification.objects.create(
                user=previous_winner.bidder,
                notification_type='outbid',
                message=f'You have been outbid on "{listing.title}". Current bid: ${amount}'
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
