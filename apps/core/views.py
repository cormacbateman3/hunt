from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.core import defaults
from apps.core.constants import FORM_LICENSE_TYPE_CATEGORIES
from apps.core.daybook import day_book
from apps.core.forms import ReferenceDataSuggestionForm
from apps.core.models import GeographicUnit, LicenseType, State
from apps.listings.models import Listing


def _selected_state_from_code(state_code, user=None):
    if state_code:
        if str(state_code).isdigit():
            return State.objects.filter(pk=int(state_code)).first()
        return State.objects.filter(code__iexact=state_code).first()
    return defaults.default_state(user)


def geo_units_api(request):
    state = _selected_state_from_code(request.GET.get('state', ''), request.user)
    units = GeographicUnit.objects.none()
    if state:
        units = GeographicUnit.objects.filter(state=state).order_by('sort_order', 'name')
    return JsonResponse(
        {
            'state': state.code if state else '',
            'state_name': state.name if state else '',
            'issuance_unit_label': state.issuance_unit_label if state else 'Geographic Unit',
            'min_license_year': state.min_license_year if state else None,
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


def map_data_api(request):
    """Aggregates for the ground map, keyed by FIPS.

    ``?state=PA`` narrows to one state's units; without it the payload is one
    row per state. ``?collector=<username>`` makes the owned figures describe
    that member's public pieces instead of the viewer's own — the profile's
    Ground covered map reads someone else's ground without seeing their
    private shelf.
    """
    from apps.core import ground

    collector = None
    collector_name = request.GET.get('collector', '')
    if collector_name:
        collector = User.objects.filter(
            username=collector_name, is_active=True
        ).first()
        if collector is None:
            return JsonResponse({'error': 'No such collector.'}, status=404)

    if collector is not None:
        owner = collector
        public_only = collector != request.user
    elif request.user.is_authenticated:
        owner, public_only = request.user, False
    else:
        owner, public_only = None, False

    state_code = request.GET.get('state', '')
    if state_code:
        state = State.objects.filter(code__iexact=state_code).first()
        if state is None:
            return JsonResponse({'error': 'No such state.'}, status=404)
        exclude = owner if owner is not None else None
        payload = ground.state_rows(
            state, owner=owner, owner_public_only=public_only,
            exclude_collector=exclude,
        )
        payload['scope'] = 'state'
        payload['collector'] = collector.username if collector else ''
        return JsonResponse(payload)

    return JsonResponse({
        'scope': 'us',
        'collector': collector.username if collector else '',
        'states': ground.us_rows(owner=owner, owner_public_only=public_only),
    })


def license_types_api(request):
    state = _selected_state_from_code(request.GET.get('state', ''), request.user)
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


def almanac(request):
    """The Almanac — a nav-level destination with no model behind it yet.

    The design calls for an index of member-written entries about a county, an
    era or a single licence, with a corrections queue and a moderator step.
    The build order puts the model third, after price history
    and CollectionSet.

    Shipping the nav slot without the app is deliberate: the four-zone
    masthead is the settled design, and a zone that quietly disappears is
    worse than one that says plainly what it will be. This page states that
    and points at the two things that already exist.
    """
    # The reference button names the viewer's own state (10.21).
    return render(request, 'core/almanac.html',
                  {'default_state': defaults.default_state(request.user)})


def search_suggest_api(request):
    """The header typeahead (implementation plan §2): results grouped by
    type — Listings / Collectors / Counties — each row a real link. The
    Archives search will eventually answer through this same box.
    """
    from django.contrib.auth.models import User

    from apps.listings.models import Listing

    q = (request.GET.get('q') or '').strip()
    if len(q) < 2:
        return JsonResponse({'listings': [], 'collectors': [], 'counties': []})

    listings = [
        {
            'title': listing.title,
            'meta': ' · '.join(filter(None, [
                listing.county_ref.name if listing.county_ref_id else '',
                str(listing.license_year or ''),
            ])),
            'url': f'/listings/{listing.pk}/',
        }
        for listing in Listing.objects.filter(
            status='active', title__icontains=q)
        .select_related('county_ref').order_by('-created_at')[:5]
    ]
    collectors = [
        {
            'title': user.profile.get_display_name() if hasattr(user, 'profile') else user.username,
            'meta': user.username,
            'url': f'/accounts/profile/{user.username}/',
        }
        for user in User.objects.filter(
            is_active=True, username__icontains=q)
        .select_related('profile')[:5]
    ]
    counties = [
        {
            'title': f'{unit.name}, {unit.state.code}' if unit.state_id else unit.name,
            'meta': unit.state.issuance_unit_label if unit.state_id else '',
            'url': f'/market/?state_id={unit.state_id}&county_id={unit.pk}',
        }
        for unit in GeographicUnit.objects.filter(
            name__icontains=q, is_statewide=False)
        .select_related('state').order_by('sort_order', 'name')[:5]
    ]
    return JsonResponse({'listings': listings, 'collectors': collectors,
                         'counties': counties})


def research(request):
    """Research — the section landing over two areas (implementation plan §1).

    The Field Guide is the reference wiki (the Almanac content under its
    new name); the Archives is the permanent census of public items —
    shell only this pass, real index later.
    """
    from apps.collections.models import CollectionItem

    return render(request, 'core/research.html', {
        'kb_zone': 'almanac',
        'public_item_count': CollectionItem.objects.filter(
            is_public=True).count(),
        'state_count': State.objects.exclude(code='FD').count(),
    })


def archives(request):
    """The Archives — a searchable record of every public item, past and
    present: a permanent census of what survives, not a browse of what's
    for sale. Shell only this pass (plan §1: "Just create shell") — the
    page says plainly what it will be, with real numbers so it isn't
    hypothetical. The search box ships disabled rather than pretending.
    """
    from apps.collections.models import CollectionItem

    return render(request, 'core/archives.html', {
        'kb_zone': 'almanac',
        'public_item_count': CollectionItem.objects.filter(
            is_public=True).count(),
    })


def home(request):
    """The home page.

    Signed in and signed out are deliberately two
    different pages, not the same page with the greeting removed: a stranger
    needs to be told what this is, a member needs to be told what changed.

    Every band answers a question a collector actually has when they open the
    site — what needs me, what closes tonight, what happened while I was out,
    what am I missing, what turned up. The old page answered none of them.
    """
    now = timezone.now()
    live = Listing.objects.filter(status='active')

    # The three names come out of the navigation and go back on the goods.
    tonight = now.replace(hour=23, minute=59, second=59)
    marketplaces = [
        {
            'name': 'The Auction House',
            'url': f"{reverse('hunt')}?format=auction",
            'count': live.filter(listing_type='auction').count(),
            'noun': 'taking bids',
            'detail': live.filter(
                listing_type='auction', auction_end__gt=now, auction_end__lte=tonight
            ).count(),
            'detail_noun': 'close tonight',
        },
        {
            'name': 'The General Store',
            'url': f"{reverse('hunt')}?format=buy_now",
            'count': live.filter(listing_type='buy_now').count(),
            'noun': 'priced to sell',
            'detail': live.filter(listing_type='buy_now', allow_offers=True).count(),
            'detail_noun': 'taking offers',
        },
        {
            'name': 'The Trading Block',
            'url': f"{reverse('hunt')}?format=trade",
            'count': live.filter(listing_type='trade').count(),
            'noun': 'open to trade',
        },
    ]

    running = live.filter(listing_type='auction', auction_end__gt=now)
    closing = list(
        running.select_related('county_ref', 'state', 'seller')
        .order_by('auction_end')[:4]
    )
    fresh = list(
        live.select_related('county_ref', 'state')
        .order_by('-created_at')[:5]
    )

    context = {
        'marketplaces': marketplaces,
        'closing_tonight': closing,
        'closing_count': running.count(),
        'fresh': fresh,
        'day_book': day_book(request.user),
        'stat_listings': live.count(),
        'stat_units': live.filter(county_ref__isnull=False)
                          .values('county_ref').distinct().count(),
        'stat_collectors': User.objects.filter(is_active=True).count(),
    }

    if not request.user.is_authenticated:
        return render(request, 'home_signed_out.html', context)

    from apps.accounts.bench import needs_you_count
    from apps.accounts.views import _collection_progress, _wanted_matches

    hour = timezone.localtime().hour
    context.update({
        'greeting': 'Morning' if hour < 12 else 'Afternoon' if hour < 17 else 'Evening',
        'needs_count': needs_you_count(request.user),
        'progress': _collection_progress(request.user),
        'wanted_matches': _wanted_matches(request.user, limit=2),
    })
    return render(request, 'home.html', context)
