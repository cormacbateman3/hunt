import json
import logging

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from apps.collections.models import CollectionItem
from apps.listings.models import Listing
from apps.prefill.models import PrefillCorrection, PrefillJob
from apps.prefill.services import job_state, process_job, rate_limit_error, validate_image

logger = logging.getLogger(__name__)


def _auth_required(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required.'}, status=401)
    return None


@require_POST
def create_job(request):
    denied = _auth_required(request)
    if denied:
        return denied
    source_form = request.POST.get('source_form', 'collection')
    if source_form not in ('listing', 'collection'):
        source_form = 'collection'
    image = request.FILES.get('image')
    error = validate_image(image) or rate_limit_error(request.user)
    if error:
        return JsonResponse({'error': error}, status=400)

    job = PrefillJob.objects.create(user=request.user, image=image, source_form=source_form)
    try:
        process_job(job)   # local backend completes inline; the client still polls the same contract
    except Exception:
        # The polling contract promises JSON — an SDK/resolver crash must not
        # leak an HTML 500 to the fetch client.
        logger.exception('Prefill job %s crashed', job.pk)
        job.status = 'failed'
        job.error = 'Extraction failed unexpectedly — try again, or fill the form manually.'
        job.save(update_fields=['status', 'error'])
    return JsonResponse(job_state(job))


@require_GET
def job_status(request, pk):
    denied = _auth_required(request)
    if denied:
        return denied
    job = get_object_or_404(PrefillJob, pk=pk, user=request.user)
    return JsonResponse(job_state(job))


@require_POST
def job_corrections(request, pk):
    """Log the diff between suggested and submitted values on form save, and
    link the job to the record it produced."""
    denied = _auth_required(request)
    if denied:
        return denied
    job = get_object_or_404(PrefillJob, pk=pk, user=request.user)
    try:
        data = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON.'}, status=400)

    listing_id = data.get('listing_id')
    item_id = data.get('collection_item_id')
    update_fields = []
    if listing_id:
        listing = Listing.objects.filter(pk=listing_id, seller=request.user).first()
        if listing:
            job.resulting_listing = listing
            update_fields.append('resulting_listing')
    if item_id:
        item = CollectionItem.objects.filter(pk=item_id, owner=request.user).first()
        if item:
            job.resulting_collection_item = item
            update_fields.append('resulting_collection_item')
    if update_fields:
        job.save(update_fields=update_fields)

    corrections = data.get('corrections') or []
    created = PrefillCorrection.objects.bulk_create(
        PrefillCorrection(
            job=job,
            field_name=str(c.get('field_name', ''))[:50],
            suggested_value=c.get('suggested_value'),
            final_value=c.get('final_value'),
            tier=str(c.get('tier', ''))[:10],
            was_accepted=bool(c.get('was_accepted')),
            was_cleared=bool(c.get('was_cleared')),
        )
        for c in corrections[:100]
        if c.get('field_name')
    )
    return JsonResponse({'logged': len(created)})
