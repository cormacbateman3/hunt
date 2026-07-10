from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Q

from apps.core.constants import FORM_LICENSE_TYPE_CATEGORIES
from apps.core.forms import ReferenceDataSuggestionForm
from apps.core.models import GeographicUnit, LicenseType, State


def _selected_state_from_code(state_code):
    if state_code:
        if str(state_code).isdigit():
            return State.objects.filter(pk=int(state_code)).first()
        return State.objects.filter(code__iexact=state_code).first()
    return State.objects.filter(is_primary_default=True).first() or State.objects.order_by('name').first()


def geo_units_api(request):
    state = _selected_state_from_code(request.GET.get('state', ''))
    units = GeographicUnit.objects.none()
    if state:
        units = GeographicUnit.objects.filter(state=state).order_by('sort_order', 'name')
    return JsonResponse(
        {
            'state': state.code if state else '',
            'state_name': state.name if state else '',
            'issuance_unit_label': state.issuance_unit_label if state else 'Geographic Unit',
            'results': [
                {
                    'id': unit.id,
                    'name': unit.name,
                    'unit_type': unit.unit_type,
                    'is_statewide': unit.is_statewide,
                }
                for unit in units
            ],
        }
    )


def license_types_api(request):
    state = _selected_state_from_code(request.GET.get('state', ''))
    year_param = request.GET.get('year', '')
    year = int(year_param) if year_param.isdigit() else None

    queryset = LicenseType.objects.filter(is_system_value=True).select_related('state')
    if state:
        queryset = queryset.filter(Q(state=state) | Q(state__isnull=True) | Q(state__code='FD'))
    else:
        queryset = queryset.filter(Q(state__isnull=True) | Q(state__code='FD'))
    grouped = {category: [] for category in FORM_LICENSE_TYPE_CATEGORIES}
    for license_type in queryset.distinct().order_by('category', 'name'):
        if license_type.category not in grouped:
            continue
        entry = {
            'id': license_type.id,
            'name': license_type.name,
            'is_other': license_type.name.lower() == 'other',
        }
        if license_type.category == 'addon_type':
            entry.update(
                {
                    'target_species': license_type.target_species,
                    'hunting_method': license_type.hunting_method,
                    'instrument': license_type.instrument,
                    'first_year': license_type.first_year,
                    'last_year': license_type.last_year,
                    'is_federal': bool(license_type.state_id and license_type.state.code == 'FD'),
                }
            )
            if year is not None:
                entry['out_of_range'] = bool(
                    (license_type.first_year and year < license_type.first_year)
                    or (license_type.last_year and year > license_type.last_year)
                )
        grouped[license_type.category].append(entry)

    if year is not None:
        # Era-appropriate options first; the flag lets the form soft-warn
        # on out-of-range selections without a second call.
        grouped['addon_type'].sort(key=lambda e: (e.get('out_of_range', False), e['name'].lower()))

    return JsonResponse(
        {
            'state': state.code if state else '',
            'year': year,
            'results': grouped,
        }
    )


def state_detail(request, slug):
    state = get_object_or_404(State, slug=slug)
    suggestion_form = ReferenceDataSuggestionForm(
        initial={
            'suggestion_type': 'correction',
            'target_model': 'state',
            'target_id': state.id,
            'field_name': 'min_license_year',
            'current_value': state.min_license_year or '',
            'next': request.path,
        }
    )
    return render(
        request,
        'core/state_detail.html',
        {
            'state': state,
            'suggestion_form': suggestion_form,
        },
    )


def geographic_unit_detail(request, pk):
    geographic_unit = get_object_or_404(
        GeographicUnit.objects.select_related('state'),
        pk=pk,
    )
    suggestion_form = ReferenceDataSuggestionForm(
        initial={
            'suggestion_type': 'correction',
            'target_model': 'geographic_unit',
            'target_id': geographic_unit.id,
            'field_name': 'name',
            'current_value': geographic_unit.name,
            'next': request.path,
        }
    )
    return render(
        request,
        'core/geographic_unit_detail.html',
        {
            'geographic_unit': geographic_unit,
            'suggestion_form': suggestion_form,
        },
    )


@login_required
def create_reference_data_suggestion(request):
    if request.method != 'POST':
        return redirect('home')

    form = ReferenceDataSuggestionForm(request.POST)
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or '/'
    if form.is_valid():
        suggestion = form.save(commit=False)
        suggestion.user = request.user
        suggestion.status = 'pending'
        suggestion.save()
        messages.success(request, 'Reference-data suggestion submitted for review.')
    else:
        messages.error(request, 'Please correct the suggestion form and try again.')
    return redirect(next_url)
