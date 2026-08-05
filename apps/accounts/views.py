from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.cache import cache
from django.core.mail import send_mail
from django.db.models import Count, Max, Q
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from . import settings_rooms
from .bench import needs_you
from .follows import follower_count, following_ids
from .forms import UserRegistrationForm, UserProfileForm, AddressForm
from .models import Address, Follow, UserProfile
from apps.core.models import GeographicUnit, State
from apps.listings.models import Listing
from apps.bids.models import Bid
from apps.orders.models import Order
from apps.notifications.models import Notification
from apps.collections.matching import (
    held_match_note, holdings, holdings_matching, want_summary,
)
from apps.collections.models import CollectionItem, WantedItem
from apps.collections.tracker import collection_groups, ground_covered
from apps.collections.tradeability import is_open_to_trade, open_to_trade
from apps.enforcement.models import Strike
from apps.favorites.models import Favorite
from apps.messaging.models import Block
from apps.reviews.models import Review
from apps.trades.models import Trade


def register(request):
    """User registration view with email verification"""
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            user.is_active = False
            user.save()

            verification_url = request.build_absolute_uri(
                reverse(
                    'accounts:verify_email',
                    kwargs={'token': user.profile.email_verification_token},
                )
            )
            email_context = {
                'user': user,
                'verification_url': verification_url,
            }
            subject = 'Verify your KeystoneBid account'
            text_body = render_to_string(
                'accounts/emails/verify_email.txt',
                email_context,
            )
            html_body = render_to_string(
                'accounts/emails/verify_email.html',
                email_context,
            )
            send_mail(
                subject=subject,
                message=text_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_body,
                fail_silently=False,
            )

            messages.success(
                request,
                'Account created. Check your email for a verification link before logging in.',
            )
            return redirect('accounts:login')
    else:
        form = UserRegistrationForm()

    return render(request, 'accounts/register.html', {
        'form': form,
        'stats': _joining_stats(),
    })


def _joining_stats():
    """What is actually here, for the right-hand column.

    Counted, never rounded up. A figure a visitor could check themselves and
    find wrong is worse than no figure.
    """
    from apps.core.models import GeographicUnit, State
    from apps.listings.models import Listing

    default_state = State.objects.filter(is_primary_default=True).first()
    units = (
        Listing.objects.filter(status='active', county_ref__isnull=False)
        .values('county_ref').distinct().count()
    )
    return {
        'listings': Listing.objects.filter(status='active').count(),
        'units': units,
        'unit_label': (
            f'{default_state.issuance_unit_label}s' if default_state else 'counties'
        ),
        'collectors': User.objects.filter(is_active=True).count(),
    }


@login_required
def user_logout(request):
    """User logout view"""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('home')


@login_required
def profile_edit(request):
    """Settings — ten named rooms rather than six stacked cards.

    Which room is open comes from `?room=`; an unknown one falls back to the
    first rather than 404ing, because a bookmark to a renamed room should
    land somewhere useful.
    """
    from apps.core.models import TermsAcceptance, TermsVersion
    from apps.enforcement.services import active_strikes_for_user
    from apps.messaging.models import Block
    from .forms import ListingDefaultsForm

    profile = request.user.profile
    room, room_label, room_blurb = settings_rooms.resolve(
        request.GET.get('room', settings_rooms.DEFAULT_ROOM))

    form = UserProfileForm(instance=profile)
    if request.method == 'POST' and room == 'profile':
        form = UserProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Saved.')
            return redirect(f"{reverse('accounts:profile_edit')}?room=profile")

    context = {
        'form': form,
        'profile': profile,
        'rail': settings_rooms.rail(room),
        'room': room,
        'room_label': room_label,
        'room_blurb': room_blurb,
    }

    # Each room loads only what it needs. Building all ten every time is how
    # a settings page ends up doing thirty queries to show one text field.
    if room == 'verification':
        context['readiness'] = profile.account_readiness
    elif room == 'addresses':
        context['addresses'] = request.user.addresses.all()
    elif room == 'alerts':
        context['wanted_count'] = request.user.wanted_items.count()
    elif room == 'defaults':
        context['listing_defaults_form'] = ListingDefaultsForm(
            initial=profile.listing_defaults or {})
    elif room == 'privacy':
        context['blocked_users'] = (
            Block.objects.filter(blocker=request.user).select_related('blocked'))
    elif room == 'records':
        context['counts'] = {
            'collection': request.user.collection_items.count(),
            'listings': request.user.listings.count(),
            'orders': (request.user.orders_as_buyer.count()
                       + request.user.orders_as_seller.count()),
        }
    elif room == 'policies':
        context['accepted'] = (
            TermsAcceptance.objects.filter(user=request.user)
            .select_related('terms').first())
        context['current_terms'] = TermsVersion.current()
        context['strikes'] = active_strikes_for_user(request.user)

    return render(request, 'accounts/profile_edit.html', context)


@login_required
def listing_defaults_save(request):
    """Save the user's default listing settings (applied to new listings)."""
    from .forms import ListingDefaultsForm
    if request.method != 'POST':
        return redirect('accounts:profile_edit')
    form = ListingDefaultsForm(request.POST)
    if form.is_valid():
        profile = request.user.profile
        profile.listing_defaults = form.to_defaults()
        profile.save(update_fields=['listing_defaults'])
        messages.success(request, 'Listing defaults saved — new listings will start with these values.')
    else:
        messages.error(request, 'Could not save listing defaults — please check the values.')
    return redirect('accounts:profile_edit')


@login_required
def follow_toggle(request, username):
    """Follow or unfollow a collector."""
    if request.method != 'POST':
        return redirect('accounts:profile', username=username)

    target = get_object_or_404(User, username=username, is_active=True)
    if target.id == request.user.id:
        messages.error(request, 'You cannot follow yourself.')
    else:
        existing = Follow.objects.filter(follower=request.user, following=target)
        if existing.exists():
            existing.delete()
            messages.success(request, f'No longer following {target.profile.get_display_name()}.')
        else:
            Follow.objects.create(follower=request.user, following=target)
            messages.success(request, f'Following {target.profile.get_display_name()}.')

    return redirect(request.POST.get('next') or reverse(
        'accounts:profile', kwargs={'username': username}))


def profile_view(request, username):
    """The collector profile — a display case with a person attached.

    Not a settings page in public. Trust sits beside the name where it can be
    read in one glance, the display case carries the owner's own words about
    each piece, and the "looking for" rail is cross-referenced against the
    viewer's own shelves: *you have one, 1931, mint*. That single line is the
    difference between a profile you read and a profile you act on.
    """
    user = get_object_or_404(User, username=username)
    profile = user.profile
    is_owner = request.user.is_authenticated and request.user.id == user.id

    tab = request.GET.get('tab', 'collection')
    group = request.GET.get('group', '')

    collection_qs = (
        CollectionItem.objects.filter(owner=user)
        .select_related('state', 'county')
        .prefetch_related('images', 'license_types')
        .order_by('-created_at')
    )
    if not is_owner:
        collection_qs = collection_qs.filter(is_public=True)

    featured_items = list(collection_qs.filter(featured=True).order_by('-created_at')[:4])
    # One query for the whole case rather than a lot lookup per piece.
    open_featured = set(
        open_to_trade(CollectionItem.objects.filter(
            pk__in=[item.pk for item in featured_items]))
        .values_list('pk', flat=True)
    )
    for item in featured_items:
        item.open_to_trade = item.pk in open_featured
    collection_items = collection_qs
    collection_total = collection_qs.count()

    # Chips over the collection: the decades they hold, plus what a visitor
    # could actually ask about today.
    decade_groups, open_to_trade_count = collection_groups(user, public_only=not is_owner)
    if group == 'trade':
        collection_items = open_to_trade(collection_items)
    elif group.isdigit():
        decade = int(group)
        collection_items = collection_items.filter(
            license_year__gte=decade, license_year__lte=decade + 9)
    shown_items = list(collection_items[:10])

    # Active listings tab — auction house + general store only (not trade)
    active_listings = (
        Listing.objects.filter(
            seller=user,
            status='active',
            listing_type__in=('auction', 'buy_now'),
        )
        .select_related('state', 'county_ref')
        .prefetch_related('license_types')
        .order_by('-created_at')
    )

    # The trade hook. Every want they've named, read against what the viewer
    # actually holds — the wanted-list matcher pointed at one person.
    all_wants = list(
        WantedItem.objects.filter(user=user)
        .select_related('state', 'county', 'license_type')
        .order_by('-created_at')
    )
    viewer_holdings = holdings(request.user) if not is_owner else []
    wanted_items, answerable = [], 0
    for want in all_wants:
        matches = holdings_matching(want, viewer_holdings)
        if matches:
            answerable += 1
        wanted_items.append({
            'want': want,
            'summary': want_summary(want),
            'note': want.notes,
            'you_have': held_match_note(matches),
        })
    # Anything the viewer can answer floats to the top; that is the whole
    # point of showing somebody else's wanted list.
    wanted_items.sort(key=lambda row: not row['you_have'])

    favorite_collection_ids = set()
    if request.user.is_authenticated:
        favorite_collection_ids = set(
            Favorite.objects.filter(user=request.user, collection_item__isnull=False)
            .values_list('collection_item_id', flat=True)
        )

    # Review summary
    review_summary = Review.summary_for_user(user)
    completed_transaction_count = (
        Listing.objects.filter(
            seller=user,
            order__status='completed',
        ).count() +
        Listing.objects.filter(
            trade__status='completed',
        ).filter(
            trade__initiator=user,
        ).count() +
        Listing.objects.filter(
            trade__status='completed',
        ).filter(
            trade__counterparty=user,
        ).count()
    )

    trade_count = Trade.objects.filter(
        Q(initiator=user) | Q(counterparty=user), status='completed').count()
    sale_count = Order.objects.filter(seller=user, status='completed').count()
    strike_count = Strike.objects.filter(user=user, is_excused=False).count()

    context = {
        'profile_user': user,
        'profile': profile,
        'kb_zone': 'collections',
        'zone_tab': 'people',
        'featured_items': featured_items,
        'collection_items': shown_items,
        'collection_total': collection_total,
        'collection_shown': collection_items.count(),
        'decade_groups': decade_groups,
        'open_to_trade_count': open_to_trade_count,
        'viewer_has_blocked': (
            request.user.is_authenticated and not is_owner
            and Block.objects.filter(blocker=request.user, blocked=user).exists()
        ),
        'active_group': group,
        'ground': ground_covered(user, public_only=not is_owner),
        'active_listings': active_listings,
        'active_listing_count': active_listings.count(),
        'wanted_items': wanted_items,
        'wanted_total': len(all_wants),
        'wanted_answerable': answerable,
        'recent_reviews': (
            Review.objects.filter(reviewed_user=user)
            .exclude(moderation_state='hidden')
            .select_related('reviewer')
            .order_by('-created_at')[:2]
        ),
        'is_owner': is_owner,
        'is_following': (
            request.user.is_authenticated
            and Follow.objects.filter(follower=request.user, following=user).exists()
        ),
        'following_ids': following_ids(request.user),
        'follower_count': follower_count(user),
        'favorite_collection_ids': favorite_collection_ids,
        'review_summary': review_summary,
        'completed_transaction_count': completed_transaction_count,
        'trade_count': trade_count,
        'sale_count': sale_count,
        'strike_count': strike_count,
        'active_tab': tab,
    }

    return render(request, 'accounts/profile.html', context)


@login_required
def dashboard(request):
    """User dashboard with listings, bids, payments, and notifications."""
    my_listings = Listing.objects.filter(seller=request.user).order_by('-created_at')[:8]
    active_listings = Listing.objects.filter(seller=request.user, status='active').count()

    my_bids = Bid.objects.filter(bidder=request.user).select_related('listing').order_by('-placed_at')[:8]
    winning_bids = Bid.objects.filter(bidder=request.user, is_winning=True, listing__status='active').count()

    pending_payments = Order.objects.filter(
        buyer=request.user,
        status='pending_payment'
    ).select_related('listing').order_by('-created_at')
    recent_purchases = Order.objects.filter(
        buyer=request.user
    ).select_related('listing').order_by('-created_at')[:6]
    recent_sales = Order.objects.filter(
        seller=request.user
    ).select_related('listing').order_by('-created_at')[:6]
    recent_favorites = (
        Favorite.objects.filter(user=request.user)
        .select_related('listing', 'collection_item', 'collection_item__owner')
        .order_by('-created_at')[:8]
    )

    recent_notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:10]

    context = {
        'active_listings_count': active_listings,
        'my_listings': my_listings,
        'my_bids': my_bids,
        'winning_bids_count': winning_bids,
        'pending_payments': pending_payments,
        'recent_purchases': recent_purchases,
        'recent_sales': recent_sales,
        'recent_notifications': recent_notifications,
        'recent_favorites': recent_favorites,
        'readiness': request.user.profile.account_readiness,
    }
    return render(request, 'accounts/dashboard.html', context)


@login_required
def bench(request):
    """My Bench → Needs you — the page a returning collector lands on.

    Three things need you, or none do. Everything that used to hide in the
    username dropdown is a visible tab beside it.
    """
    user = request.user
    rows = needs_you(user)

    hour = timezone.localtime().hour
    if hour < 12:
        greeting = 'Morning'
    elif hour < 17:
        greeting = 'Afternoon'
    else:
        greeting = 'Evening'

    context = {
        'greeting': greeting,
        'needs_you': rows,
        'needs_you_count': len(rows),
        'readiness': user.profile.account_readiness,
        'closing_soon': _closing_in_my_units(user),
        'wanted_matches': _wanted_matches(user),
        'progress': _collection_progress(user),
    }
    return render(request, 'accounts/bench.html', context)


def _primary_state(user):
    """The state this collector actually collects, not the one they live in."""
    top = (
        CollectionItem.objects.filter(owner=user, state__isnull=False)
        .values('state')
        .annotate(n=Count('id'))
        .order_by('-n')
        .first()
    )
    if top:
        return State.objects.filter(pk=top['state']).first()
    profile_state = getattr(user.profile, 'state', None)
    return profile_state or State.objects.filter(is_primary_default=True).first()


def _collection_progress(user):
    """Ground covered, in the state's own vocabulary.

    Pennsylvania issues by county; other states issue by GMU, WMD or hunt
    area. Reading ``issuance_unit_label`` keeps "county" out of the
    interface everywhere it would be wrong.
    """
    state = _primary_state(user)
    if not state:
        return None

    items = CollectionItem.objects.filter(owner=user, state=state)

    unit_total = GeographicUnit.objects.filter(state=state, is_statewide=False).count()
    unit_held = items.filter(county__isnull=False).values('county').distinct().count()

    first_year = state.licensing_start_year or state.min_license_year
    years = items.filter(license_year__isnull=False)
    year_held = years.values('license_year').distinct().count()
    last_year = years.aggregate(Max('license_year'))['license_year__max']
    year_total = (last_year - first_year + 1) if (first_year and last_year and last_year >= first_year) else 0

    held_ids = set(items.filter(county__isnull=False).values_list('county_id', flat=True))
    gaps = list(
        GeographicUnit.objects.filter(state=state, is_statewide=False)
        .exclude(id__in=held_ids)
        .order_by('sort_order', 'name')
        .values_list('name', flat=True)[:5]
    )

    return {
        'state': state,
        'unit_label': f'{state.issuance_unit_label}s',
        'unit_held': unit_held,
        'unit_total': unit_total,
        'unit_pct': round(unit_held / unit_total * 100) if unit_total else 0,
        'year_label': f'Years {first_year}–{last_year}' if first_year and last_year else 'Years',
        'year_held': year_held,
        'year_total': year_total,
        'year_pct': round(year_held / year_total * 100) if year_total else 0,
        'gaps': gaps,
    }


def _closing_in_my_units(user, limit=3):
    """Auctions closing soonest in the units this collector already holds."""
    held = set(
        CollectionItem.objects.filter(owner=user, county__isnull=False)
        .values_list('county_id', flat=True)
    )
    qs = Listing.objects.filter(
        status='active', listing_type='auction', auction_end__gt=timezone.now()
    ).exclude(seller=user).select_related('county_ref', 'state')
    if held:
        qs = qs.filter(county_ref_id__in=held)
    return list(qs.order_by('auction_end')[:limit])


def _wanted_matches(user, limit=2):
    """Live listings that satisfy one of this collector's wants."""
    wants = WantedItem.objects.filter(user=user).select_related('state', 'county')
    if not wants.exists():
        return []

    match = Q(pk__in=[])
    for want in wants:
        clause = Q()
        if want.state_id:
            clause &= Q(state_id=want.state_id)
        if want.county_id:
            clause &= Q(county_ref_id=want.county_id)
        if want.year_min:
            clause &= Q(license_year__gte=want.year_min)
        if want.year_max:
            clause &= Q(license_year__lte=want.year_max)
        if want.license_type_id:
            clause &= Q(license_types__id=want.license_type_id)
        if clause:
            match |= clause

    return list(
        Listing.objects.filter(status='active')
        .filter(match)
        .exclude(seller=user)
        .select_related('county_ref')
        .distinct()
        .order_by('-created_at')[:limit]
    )


def verify_email(request, token):
    """Email verification view"""
    try:
        profile = UserProfile.objects.get(email_verification_token=token)
        if not profile.email_verified:
            profile.email_verified = True
            profile.save()
            profile.user.is_active = True
            profile.user.save(update_fields=['is_active'])
            messages.success(request, 'Email verified successfully!')
        else:
            messages.info(request, 'Email already verified.')
        return redirect('accounts:login')
    except UserProfile.DoesNotExist:
        messages.error(request, 'Invalid verification link.')
        return redirect('home')


@login_required
def resend_verification_email(request):
    """Resend email verification link. Rate-limited to 3 per hour."""
    if request.method != 'POST':
        return redirect('accounts:profile_edit')

    profile = request.user.profile
    if profile.email_verified:
        messages.info(request, 'Your email is already verified.')
        return redirect('accounts:profile_edit')

    cache_key = f'resend_verify_{request.user.pk}'
    sent_times = cache.get(cache_key, [])
    now = timezone.now().timestamp()
    # Keep only timestamps within the last hour
    sent_times = [t for t in sent_times if now - t < 3600]
    if len(sent_times) >= 3:
        messages.error(request, 'You have requested too many verification emails. Please wait before trying again.')
        return redirect('accounts:profile_edit')

    sent_times.append(now)
    cache.set(cache_key, sent_times, 3600)

    verification_url = request.build_absolute_uri(
        reverse('accounts:verify_email', kwargs={'token': profile.email_verification_token})
    )
    email_context = {'user': request.user, 'verification_url': verification_url}
    send_mail(
        subject='Verify your KeystoneBid account',
        message=render_to_string('accounts/emails/verify_email.txt', email_context),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[request.user.email],
        html_message=render_to_string('accounts/emails/verify_email.html', email_context),
        fail_silently=False,
    )
    messages.success(request, 'Verification email sent. Check your inbox.')
    return redirect('accounts:profile_edit')


@login_required
def address_add(request):
    """Add a new shipping address."""
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            address.save()
            # Make default if this is the user's first address
            profile = request.user.profile
            if not profile.shipping_address_id:
                profile.shipping_address = address
                profile.save(update_fields=['shipping_address'])
                address.is_default = True
                address.save(update_fields=['is_default'])
            messages.success(request, 'Address saved.')
            return redirect('accounts:profile_edit')
    else:
        form = AddressForm()

    return render(request, 'accounts/address_form.html', {
        'form': form, 'action': 'Add',
        'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY,
    })


@login_required
def address_edit(request, pk):
    """Edit an existing shipping address."""
    address = get_object_or_404(Address, pk=pk, user=request.user)
    if request.method == 'POST':
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            form.save()
            messages.success(request, 'Address updated.')
            return redirect('accounts:profile_edit')
    else:
        form = AddressForm(instance=address)

    return render(request, 'accounts/address_form.html', {
        'form': form, 'action': 'Edit', 'address': address,
        'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY,
    })


@login_required
def address_delete(request, pk):
    """Delete an address. POST only."""
    address = get_object_or_404(Address, pk=pk, user=request.user)
    if request.method == 'POST':
        profile = request.user.profile
        if profile.shipping_address_id == address.pk:
            # Clear default; auto-assign another if available
            profile.shipping_address = None
            profile.save(update_fields=['shipping_address'])
            remaining = request.user.addresses.exclude(pk=address.pk).first()
            if remaining:
                profile.shipping_address = remaining
                profile.save(update_fields=['shipping_address'])
                remaining.is_default = True
                remaining.save(update_fields=['is_default'])
        address.delete()
        messages.success(request, 'Address removed.')
        return redirect('accounts:profile_edit')

    return render(request, 'accounts/address_confirm_delete.html', {'address': address})


@login_required
def address_set_default(request, pk):
    """Set an address as the default. POST only."""
    if request.method != 'POST':
        return redirect('accounts:profile_edit')
    address = get_object_or_404(Address, pk=pk, user=request.user)
    profile = request.user.profile
    # Clear old default flag
    request.user.addresses.filter(is_default=True).update(is_default=False)
    address.is_default = True
    address.save(update_fields=['is_default'])
    profile.shipping_address = address
    profile.save(update_fields=['shipping_address'])
    messages.success(request, 'Default address updated.')
    return redirect('accounts:profile_edit')
