"""Move each negotiation's anchor from the lot to the piece.

10.10 finishes here. Until now a trade offer needed a `Listing`, which is why
nothing could be traded without first being put up for sale — and why the
collector card's "Propose a trade" had to walk you to somebody's trade shelf
instead of just asking. Two things held it:

* ``TradeOffer.trade_listing`` was non-null, so an offer had nowhere to hang.
* ``Trade.listing`` was a ``OneToOneField`` doing double duty as the
  uniqueness anchor — "this lot already has an accepted trade" — so nulling
  it would have quietly dropped that guarantee.

Both are now nullable, uniqueness has moved to ``Trade.offer`` where it is
actually true (one accepted offer, one trade), and this migration fills the
new columns from the old ones so no existing negotiation loses its subject.

Nothing is deleted. Old offers keep their `trade_listing`, so a trade struck
against a lot still reads as one; the FK simply stops being required.
"""

from django.db import migrations


def carry_the_anchor(apps, schema_editor):
    TradeOffer = apps.get_model('trades', 'TradeOffer')
    Trade = apps.get_model('trades', 'Trade')

    # The piece a negotiation is about is the one the lot was created from.
    # Where a lot never had a source item there is nothing to carry, and the
    # offer keeps reading through its listing.
    for offer in TradeOffer.objects.filter(
        subject_item__isnull=True, trade_listing__isnull=False
    ).select_related('trade_listing').iterator():
        item_id = offer.trade_listing.source_collection_item_id
        if item_id:
            offer.subject_item_id = item_id
            offer.save(update_fields=['subject_item'])

    # A trade's identity is the offer that was accepted. Picking the newest
    # accepted offer on the lot matches what `accept_trade_offer` did: it
    # marks one accepted and declines the rest.
    for trade in Trade.objects.filter(offer__isnull=True, listing__isnull=False).iterator():
        accepted = (
            TradeOffer.objects
            .filter(trade_listing_id=trade.listing_id, status='accepted')
            .order_by('-created_at')
            .first()
        )
        if accepted and not Trade.objects.filter(offer_id=accepted.id).exists():
            trade.offer_id = accepted.id
            trade.save(update_fields=['offer'])


def put_it_back(apps, schema_editor):
    """Reverse is a clear-down, not a guess.

    Both columns are derived from the listing, which is still there, so
    dropping them loses nothing that cannot be recomputed by running this
    migration again.
    """
    apps.get_model('trades', 'TradeOffer').objects.update(subject_item=None)
    apps.get_model('trades', 'Trade').objects.update(offer=None)


class Migration(migrations.Migration):

    dependencies = [
        ('trades', '0006_offers_hang_off_a_piece'),
        ('listings', '0001_initial'),
        ('collections', '0013_tradeable_unless_you_say_otherwise'),
    ]

    operations = [
        migrations.RunPython(carry_the_anchor, put_it_back),
    ]
