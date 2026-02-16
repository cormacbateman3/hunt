from django.db import models
from django.contrib.auth.models import User


class Favorite(models.Model):
    """User favorite - either a listing or a collection item (XOR)"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites')
    listing = models.ForeignKey(
        'listings.Listing', on_delete=models.CASCADE, null=True, blank=True,
        related_name='favorites'
    )
    collection_item = models.ForeignKey(
        'collections.CollectionItem', on_delete=models.CASCADE, null=True, blank=True,
        related_name='favorites'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Favorite'
        verbose_name_plural = 'Favorites'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(listing__isnull=False, collection_item__isnull=True) |
                    models.Q(listing__isnull=True, collection_item__isnull=False)
                ),
                name='favorite_xor_listing_collection',
            ),
            models.UniqueConstraint(
                fields=['user', 'listing'],
                condition=models.Q(listing__isnull=False),
                name='favorite_unique_user_listing',
            ),
            models.UniqueConstraint(
                fields=['user', 'collection_item'],
                condition=models.Q(collection_item__isnull=False),
                name='favorite_unique_user_collection_item',
            ),
        ]
        indexes = [
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        target = self.listing or self.collection_item
        return f"{self.user.username} favorited {target}"
