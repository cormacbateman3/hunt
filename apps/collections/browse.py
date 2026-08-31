"""Everything owned — the public item browse, and the state of its filter bar.

Kept out of ``views.py`` because it is the whole of one screen: the query, the
options offered, and the chips describing what has been narrowed. A view that
did all three would be four hundred lines and nobody would find any of it.

Three rules the bar has to keep:

* **Every choice says so out loud.** Nine closed dropdowns hid the answer to
  "why am I seeing so little?"; every narrowing choice is now a chip you can
  take off in one click.
* **No filter names a database column.** Nobody outside this codebase knows
  what ``holder_eligibility`` means, so the labels are questions.
* **No Apply button.** The grid updates as you go, which is what the
  multi-select panels always implied.
"""

from django.core.paginator import Paginator
from django.db.models import Q

from apps.core import defaults
from apps.core.constants import (
    FORM_LICENSE_TYPE_CATEGORIES,
    LICENSE_TYPE_CATEGORY_QUESTIONS,
)
from apps.core.models import GeographicUnit, LicenseType, State
from apps.listings.models import ERA_LABEL_CHOICES
from apps.listings.views import _era_to_year_range

from .models import CollectionItem

PER_PAGE = 24

SORTS = {
    'newest': '-created_at',
    'year_asc': 'license_year',
    'year_desc': '-license_year',
    'owner_az': 'owner__username',
}


def apply_filters(queryset, params):
    """Narrow the public item queryset by everything the bar can set."""
    search = params.get('search', '').strip()
    if search:
        queryset = queryset.filter(
            Q(title__icontains=search) | Q(description__icontains=search))

    state_id = params.get('state_id', '')
    if state_id.isdigit():
        queryset = queryset.filter(state_id=state_id)

    county_id = params.get('county_id', '')
    if county_id.isdigit():
        queryset = queryset.filter(county_id=county_id)

    for key, lookup in (('year_min', 'gte'), ('year_max', 'lte')):
        raw = params.get(key, '')
        if raw:
            try:
                queryset = queryset.filter(**{f'license_year__{lookup}': int(raw)})
            except ValueError:
                pass

    # An item has to carry *every* category ticked, which is why this narrows
    # hardest — worth remembering when an empty result looks like a bug.
    for category in FORM_LICENSE_TYPE_CATEGORIES:
        chosen = [v for v in params.getlist(f'{category}_id') if v.isdigit()]
        if chosen:
            queryset = queryset.filter(license_types__id__in=chosen)

    eras = [v for v in params.getlist('era') if v]
    if eras:
        era_q = Q()
        for era in eras:
            years = _era_to_year_range(era)
            if years:
                low, high = years
                # A dated item matches by year; an undated one only by its
                # own era label, so neither kind is silently dropped.
                era_q |= (
                    Q(license_year__gte=low, license_year__lte=high)
                    | Q(license_year__isnull=True, era_label=era)
                )
            else:
                era_q |= Q(era_label=era, license_year__isnull=True)
        queryset = queryset.filter(era_q)

    owner = params.get('owner', '').strip()
    if owner:
        queryset = queryset.filter(
            Q(owner__username__icontains=owner)
            | Q(owner__profile__display_name__icontains=owner)
        )

    sort = params.get('sort', 'newest')
    return queryset.order_by(SORTS.get(sort, SORTS['newest'])).distinct()


def resolve_state(params, user=None):
    """(default state, selected state). The viewer's home state unless told
    otherwise (10.21), the site default when they never said one; an
    explicit empty ``state_id`` means *anywhere* and must survive."""
    default = defaults.default_state(user)
    if 'state_id' not in params:
        return default, default
    state_id = params.get('state_id', '')
    if state_id.isdigit():
        return default, State.objects.filter(pk=state_id).first()
    return default, None


def license_type_groups(params, state):
    """The six categories as questions, each with what is currently ticked.

    Federal types are always offered — a duck stamp belongs to no state.
    """
    if not state:
        return []

    types = list(
        LicenseType.objects.filter(is_system_value=True)
        .filter(Q(state=state) | Q(state__isnull=True) | Q(state__code='FD'))
        .order_by('category', 'name')
        .distinct()
    )

    groups = []
    for category in FORM_LICENSE_TYPE_CATEGORIES:
        in_category = [lt for lt in types if lt.category == category]
        if in_category:
            groups.append({
                'category': category,
                'label': LICENSE_TYPE_CATEGORY_QUESTIONS.get(
                    category, category.replace('_', ' ').title()),
                'types': in_category,
                'filter_key': f'{category}_id',
                'selected_ids': params.getlist(f'{category}_id'),
            })
    return groups


def without(params, key, value=None):
    """The current query string with one filter — or one value of one — removed."""
    out = params.copy()
    out.pop('page', None)
    if value is None:
        out.pop(key, None)
    else:
        kept = [v for v in out.getlist(key) if v != value]
        out.setlist(key, kept)
        if not kept:
            out.pop(key, None)
    encoded = out.urlencode()
    return f'?{encoded}' if encoded else '?tab=owned'


def applied_filters(params, groups):
    """What you've chosen, as chips you can take off again."""
    chips = []

    for key, template in (
        ('search', 'Search: {}'),
        ('owner', 'Collector: {}'),
        ('year_min', 'From {}'),
        ('year_max', 'To {}'),
    ):
        value = params.get(key, '').strip()
        if value:
            chips.append({'label': template.format(value),
                          'url': without(params, key)})

    county_id = params.get('county_id', '')
    if county_id.isdigit():
        unit = GeographicUnit.objects.filter(pk=county_id).first()
        if unit:
            chips.append({'label': unit.name,
                          'url': without(params, 'county_id')})

    for era in params.getlist('era'):
        if era:
            chips.append({'label': era, 'url': without(params, 'era', era)})

    for group in groups:
        chosen = set(group['selected_ids'])
        for license_type in group['types']:
            if str(license_type.id) in chosen:
                chips.append({
                    'label': license_type.name,
                    'url': without(params, group['filter_key'], str(license_type.id)),
                })

    return chips


def page(params, user=None):
    """Everything the Everything-owned template needs, in one call."""
    items = (
        CollectionItem.objects.filter(is_public=True)
        .select_related('owner__profile', 'state', 'county')
        .prefetch_related('images', 'license_types')
    )
    paginator = Paginator(apply_filters(items, params), PER_PAGE)
    page_obj = paginator.get_page(params.get('page'))

    default_state, selected_state = resolve_state(params, user)
    groups = license_type_groups(params, selected_state)

    query = params.copy()
    query.pop('page', None)

    return {
        'zone_tab': 'owned',
        'page_obj': page_obj,
        'result_total': paginator.count,
        'collector_total': (
            CollectionItem.objects.filter(is_public=True)
            .values('owner_id').distinct().count()
        ),
        'applied_filters': applied_filters(params, groups),
        'states': State.objects.order_by('-is_primary_default', 'name'),
        'selected_state': selected_state,
        'counties': (
            GeographicUnit.objects.filter(state=selected_state)
            .order_by('sort_order', 'name')
            if selected_state else GeographicUnit.objects.none()
        ),
        'license_type_groups': groups,
        'era_choices': ERA_LABEL_CHOICES,
        'filters': {
            'search': params.get('search', '').strip(),
            'state_id': params.get(
                'state_id', str(default_state.id) if default_state else ''),
            'county_id': params.get('county_id', ''),
            'year_min': params.get('year_min', ''),
            'year_max': params.get('year_max', ''),
            'era_list': params.getlist('era'),
            'owner': params.get('owner', '').strip(),
            'sort': params.get('sort', 'newest'),
        },
        'query_string': query.urlencode(),
    }
