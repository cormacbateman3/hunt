"""Listing business logic shared by views and management commands."""


def seller_shipping_ready(user) -> bool:
    """A listing may only be live when its seller has a default shipping address.

    This is the seller-side half of the checkout contract — enforced at every
    activation path (create view, scheduled go-live, auto-relist) so a buyer can
    never be blocked at payment by a seller-side gap.
    """
    profile = getattr(user, 'profile', None)
    return bool(profile and profile.shipping_address_id)
