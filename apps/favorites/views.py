from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from apps.collections.models import CollectionItem
from apps.listings.models import Listing
from . import saved
from .models import Favorite


@login_required
def favorites_list(request):
    """Saved — sorted by what closes soonest, not by when you saved it.

    The arithmetic is in :mod:`apps.favorites.saved`.
    """
    return render(request, 'favorites/list.html',
                  saved.page(request.user, request.GET.get('tab', '')))


@login_required
@require_POST
def toggle_listing_favorite(request, pk):
    listing = get_object_or_404(Listing, pk=pk)
    fav = Favorite.objects.filter(user=request.user, listing=listing).first()
    if fav:
        fav.delete()
        messages.info(request, 'Removed listing from favorites.')
    else:
        Favorite.objects.create(user=request.user, listing=listing)
        messages.success(request, 'Listing added to favorites.')
    next_url = (request.POST.get('next') or '').strip()
    if next_url.startswith('/'):
        return redirect(next_url)
    return redirect('listings:detail', pk=pk)


@login_required
@require_POST
def toggle_collection_item_favorite(request, pk):
    item = get_object_or_404(CollectionItem, pk=pk)
    if not item.is_public and item.owner_id != request.user.id:
        messages.error(request, 'Only public collection items can be favorited.')
        next_url = (request.POST.get('next') or '').strip()
        if next_url.startswith('/'):
            return redirect(next_url)
        return redirect('accounts:profile', username=item.owner.username)

    fav = Favorite.objects.filter(user=request.user, collection_item=item).first()
    if fav:
        fav.delete()
        messages.info(request, 'Removed collection item from favorites.')
    else:
        Favorite.objects.create(user=request.user, collection_item=item)
        messages.success(request, 'Collection item added to favorites.')
    next_url = (request.POST.get('next') or '').strip()
    if next_url.startswith('/'):
        return redirect(next_url)
    return redirect('accounts:profile', username=item.owner.username)
