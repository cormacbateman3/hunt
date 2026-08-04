"""Shell context — which zone the current page belongs to.

The redesign replaces four top-level pillars with four zones that each have
a job: Hunt (one catalog), Collections (people and what they own), My Bench
(your workspace) and The Almanac (what the community knows). Rather than
have every template declare its own zone and drift out of sync, the zone is
derived once from the resolved view name.
"""

# Views that belong to a zone regardless of their app namespace. The zone
# roots are top-level URLs, so they carry no namespace at all.
_ZONE_BY_VIEW = {
    'hunt': 'hunt',
    'bench': 'bench',
    'collectors': 'collections',
    'almanac': 'almanac',
    # Looking at someone's collection is discovery, so it lives in
    # Collections; managing your own is work, so it lives in My Bench.
    'collections:browse': 'collections',
    'accounts:profile': 'collections',
    'collections:my_collection': 'bench',
}

# Fallback by namespace, for the apps that sit wholly inside one zone.
_ZONE_BY_NAMESPACE = {
    'listings': 'hunt',
    'core': 'hunt',
    'bids': 'bench',
    'offers': 'bench',
    'orders': 'bench',
    'payments': 'bench',
    'shipping': 'bench',
    'trades': 'bench',
    'favorites': 'bench',
    'messaging': 'bench',
    'notifications': 'bench',
    'collections': 'bench',
}

# Listing views that are really part of selling, not browsing.
_BENCH_LISTING_VIEWS = {
    'listings:my_listings',
    'listings:create',
    'listings:edit',
}

_BENCH_ACCOUNT_VIEWS = {
    'accounts:bench',
    'accounts:dashboard',
}


def _zone_for(view_name, namespace):
    if view_name in _BENCH_LISTING_VIEWS or view_name in _BENCH_ACCOUNT_VIEWS:
        return 'bench'
    if view_name in _ZONE_BY_VIEW:
        return _ZONE_BY_VIEW[view_name]
    return _ZONE_BY_NAMESPACE.get(namespace)


def shell(request):
    """Expose ``kb_zone`` so the topbar can mark the current destination."""
    match = getattr(request, 'resolver_match', None)
    if match is None:
        return {'kb_zone': None, 'bench_needs_count': 0}

    zone = _zone_for(match.view_name or '', match.namespace or '')

    # The Needs-you count rides the whole zone, so the tab strip reads the
    # same on every Bench page. Only paid for inside the zone.
    count = 0
    if zone == 'bench' and request.user.is_authenticated:
        from apps.accounts.bench import needs_you_count
        count = needs_you_count(request.user)

    return {'kb_zone': zone, 'bench_needs_count': count}
