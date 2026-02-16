from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from apps.orders.models import Order
from .forms import CollectionItemForm, CollectionItemImageFormSet, WantedItemForm
from .models import CollectionItem, CollectionItemImage, WantedItem


@login_required
def my_collection(request):
    items = (
        CollectionItem.objects.filter(owner=request.user)
        .select_related('county', 'license_type')
        .prefetch_related('images')
        .order_by('-created_at')
    )
    wanted_items = (
        WantedItem.objects.filter(user=request.user)
        .select_related('county', 'license_type')
        .order_by('-created_at')
    )
    return render(request, 'collections/my_collection.html', {
        'items': items,
        'wanted_items': wanted_items,
    })


@login_required
def collection_item_create(request):
    image_formset = CollectionItemImageFormSet(request.POST or None, request.FILES or None)
    if request.method == 'POST':
        form = CollectionItemForm(request.POST)
        if form.is_valid() and image_formset.is_valid():
            item = form.save(commit=False)
            item.owner = request.user
            item.save()

            image_formset = CollectionItemImageFormSet(request.POST, request.FILES, instance=item)
            if image_formset.is_valid():
                image_formset.save()
                messages.success(request, 'Collection item created.')
                return redirect('collections:my_collection')
            item.delete()
    else:
        form = CollectionItemForm()

    return render(request, 'collections/collection_item_form.html', {
        'form': form,
        'image_formset': image_formset,
        'mode': 'create',
    })


@login_required
def collection_item_edit(request, pk):
    item = get_object_or_404(CollectionItem, pk=pk, owner=request.user)
    if request.method == 'POST':
        form = CollectionItemForm(request.POST, instance=item)
        image_formset = CollectionItemImageFormSet(request.POST, request.FILES, instance=item)
        if form.is_valid() and image_formset.is_valid():
            form.save()
            image_formset.save()
            messages.success(request, 'Collection item updated.')
            return redirect('collections:my_collection')
    else:
        form = CollectionItemForm(instance=item)
        image_formset = CollectionItemImageFormSet(instance=item)

    return render(request, 'collections/collection_item_form.html', {
        'form': form,
        'image_formset': image_formset,
        'mode': 'edit',
        'item': item,
    })


@login_required
def collection_item_delete(request, pk):
    item = get_object_or_404(CollectionItem, pk=pk, owner=request.user)
    if request.method == 'POST':
        item.delete()
        messages.success(request, 'Collection item deleted.')
        return redirect('collections:my_collection')
    return render(request, 'collections/collection_item_delete.html', {'item': item})


@login_required
def wanted_item_create(request):
    if request.method == 'POST':
        form = WantedItemForm(request.POST)
        if form.is_valid():
            wanted_item = form.save(commit=False)
            wanted_item.user = request.user
            wanted_item.save()
            messages.success(request, 'Wanted item added.')
            return redirect('collections:my_collection')
    else:
        form = WantedItemForm()
    return render(request, 'collections/wanted_item_form.html', {'form': form, 'mode': 'create'})


@login_required
def wanted_item_edit(request, pk):
    wanted_item = get_object_or_404(WantedItem, pk=pk, user=request.user)
    if request.method == 'POST':
        form = WantedItemForm(request.POST, instance=wanted_item)
        if form.is_valid():
            form.save()
            messages.success(request, 'Wanted item updated.')
            return redirect('collections:my_collection')
    else:
        form = WantedItemForm(instance=wanted_item)
    return render(request, 'collections/wanted_item_form.html', {
        'form': form,
        'mode': 'edit',
        'wanted_item': wanted_item,
    })


@login_required
def wanted_item_delete(request, pk):
    wanted_item = get_object_or_404(WantedItem, pk=pk, user=request.user)
    if request.method == 'POST':
        wanted_item.delete()
        messages.success(request, 'Wanted item removed.')
        return redirect('collections:my_collection')
    return render(request, 'collections/wanted_item_delete.html', {'wanted_item': wanted_item})


@login_required
def add_from_order(request, order_id):
    order = get_object_or_404(Order.objects.select_related('listing'), pk=order_id, buyer=request.user)
    if order.status != 'completed':
        messages.error(request, 'Only completed orders can be added to your collection.')
        return redirect('orders:detail', pk=order.pk)
    if request.method != 'POST':
        return redirect('orders:detail', pk=order.pk)

    listing = order.listing
    item = CollectionItem.objects.create(
        owner=request.user,
        title=listing.title,
        description=listing.description,
        license_year=listing.license_year,
        county=listing.county_ref,
        license_type=listing.license_type_ref,
        resident_status='unknown',
        condition_grade=listing.condition_grade,
        is_public=True,
        trade_eligible=True,
    )
    if listing.featured_image:
        CollectionItemImage.objects.create(
            collection_item=item,
            image=listing.featured_image,
            sort_order=0,
        )
    for listing_image in listing.additional_images.order_by('sort_order', 'uploaded_at'):
        CollectionItemImage.objects.create(
            collection_item=item,
            image=listing_image.image,
            sort_order=listing_image.sort_order + 1,
        )
    messages.success(request, 'Purchase added to your collection.')
    return redirect('collections:edit', pk=item.pk)
