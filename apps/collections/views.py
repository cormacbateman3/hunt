from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from .forms import CollectionItemForm
from .models import CollectionItem


@login_required
def my_collection(request):
    items = CollectionItem.objects.filter(owner=request.user).select_related(
        'county', 'license_type'
    ).order_by('-created_at')
    return render(request, 'collections/my_collection.html', {'items': items})


@login_required
def collection_item_create(request):
    if request.method == 'POST':
        form = CollectionItemForm(request.POST)
        if form.is_valid():
            item = form.save(commit=False)
            item.owner = request.user
            item.save()
            messages.success(request, 'Collection item created.')
            return redirect('collections:my_collection')
    else:
        form = CollectionItemForm()

    return render(request, 'collections/collection_item_form.html', {
        'form': form,
        'mode': 'create',
    })


@login_required
def collection_item_edit(request, pk):
    item = get_object_or_404(CollectionItem, pk=pk, owner=request.user)
    if request.method == 'POST':
        form = CollectionItemForm(request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, 'Collection item updated.')
            return redirect('collections:my_collection')
    else:
        form = CollectionItemForm(instance=item)

    return render(request, 'collections/collection_item_form.html', {
        'form': form,
        'mode': 'edit',
        'item': item,
    })
