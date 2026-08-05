from datetime import timedelta
from decimal import Decimal

from django import forms
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import Address
from apps.collections.models import CollectionItem
from apps.core.constants import (
    ABSOLUTE_MIN_LICENSE_YEAR,
    COLOR_CHOICES,
    FORM_LICENSE_TYPE_CATEGORIES,
    SHAPE_CHOICES,
)
from apps.core.models import GeographicUnit, LicenseType, ReferenceDataSuggestion, State
from apps.listings.models import ERA_LABEL_CHOICES, Listing, ListingImage


def _state_license_type_queryset(state, category):
    queryset = LicenseType.objects.filter(category=category, is_system_value=True)
    if state:
        queryset = queryset.filter(Q(state=state) | Q(state__isnull=True) | Q(state__code='FD'))
    else:
        queryset = queryset.filter(Q(state__isnull=True) | Q(state__code='FD'))
    return queryset.order_by('name').distinct()


class ListingForm(forms.ModelForm):
    """Form for creating and editing listings across all listing types."""

    duration_days = forms.ChoiceField(
        choices=[
            (1, '1 day'),
            (3, '3 days'),
            (5, '5 days'),
            (7, '7 days'),
            (10, '10 days'),
        ],
        initial=7,
        required=False,
        help_text="How long should the auction run?",
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    state = forms.ModelChoiceField(
        queryset=State.objects.none(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    county_ref = forms.ModelChoiceField(
        queryset=GeographicUnit.objects.none(),
        required=False,
        empty_label='Select geographic unit',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    residency = forms.ModelChoiceField(queryset=LicenseType.objects.none(), required=False, empty_label='Select residency', widget=forms.Select(attrs={'class': 'form-select'}))
    residency_other = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter residency value'}))
    holder_eligibility = forms.ModelChoiceField(queryset=LicenseType.objects.none(), required=False, empty_label='Select holder eligibility', widget=forms.Select(attrs={'class': 'form-select'}))
    holder_eligibility_other = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter eligibility value'}))
    activity_scope = forms.ModelChoiceField(queryset=LicenseType.objects.none(), required=False, empty_label='Select activity scope', widget=forms.Select(attrs={'class': 'form-select'}))
    activity_scope_other = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter activity scope'}))
    duration = forms.ModelChoiceField(queryset=LicenseType.objects.none(), required=False, empty_label='Select duration', widget=forms.Select(attrs={'class': 'form-select'}))
    duration_other = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter duration'}))
    addon_type = forms.ModelMultipleChoiceField(
        queryset=LicenseType.objects.none(), required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'chip-checkboxes'}),
    )
    addon_type_other = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter add-on type'}))
    material = forms.ModelChoiceField(queryset=LicenseType.objects.none(), required=False, empty_label='Select material', widget=forms.Select(attrs={'class': 'form-select'}))
    material_other = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter material'}))
    shape = forms.ChoiceField(
        choices=[('', 'Select shape')] + SHAPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    shape_other = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter shape'}))
    colors = forms.MultipleChoiceField(
        choices=COLOR_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'chip-checkboxes'}),
    )
    colors_other = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter color'}))
    source_collection_item = forms.ModelChoiceField(
        queryset=CollectionItem.objects.none(),
        required=False,
        empty_label='None',
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='Prefill safe fields from an item in your collection.',
    )
    scheduled_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'class': 'form-input', 'type': 'datetime-local'}),
        help_text='Leave blank to publish immediately. Max 30 days in the future.',
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'],
    )
    auto_relist = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        help_text='Auto-relist if auction ends without a winner (up to 3 times).',
    )
    local_pickup_available = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        help_text='Offer local pickup as an alternative to shipping.',
    )
    local_pickup_location = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Lancaster, PA'}),
        help_text='City or region for local pickup.',
    )
    serial_number = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. A-12345'}),
        help_text='License serial or stub number, if visible.',
    )
    era_label = forms.ChoiceField(
        choices=[('', 'Select era')] + ERA_LABEL_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='Required when license year is unknown.',
    )
    ship_from_address = forms.ModelChoiceField(
        queryset=Address.objects.none(),
        required=False,
        empty_label='Account default address',
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='Where this item ships from.',
    )

    class Meta:
        model = Listing
        fields = [
            'listing_type',
            'item_kind',
            'addons_attached',
            'source_collection_item',
            'title',
            'description',
            'state',
            'license_year',
            'county_ref',
            'residency',
            'holder_eligibility',
            'activity_scope',
            'duration',
            'addon_type',
            'material',
            'shape',
            'colors',
            'condition_grade',
            'starting_price',
            'reserve_price',
            'buy_now_price',
            'allow_offers',
            'minimum_offer',
            'bid_increment',
            'trade_notes',
            'allow_cash',
            'scheduled_at',
            'auto_relist',
            'local_pickup_available',
            'local_pickup_location',
            'serial_number',
            'era_label',
            'featured_image',
            'ship_from_address',
            'package_weight_oz',
            'package_length_in',
            'package_width_in',
            'package_height_in',
            'shipping_service',
            'shipping_payer',
        ]
        widgets = {
            'listing_type': forms.Select(attrs={'class': 'form-select'}),
            'item_kind': forms.RadioSelect(),
            'addons_attached': forms.NullBooleanSelect(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., 1942 Adams County Resident Hunting License'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'placeholder': 'Describe the license condition, notable features, provenance, and any context collectors should know.', 'rows': 6}),
            'license_year': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '1942 (leave blank if unknown)'}),
            'condition_grade': forms.Select(attrs={'class': 'form-select'}),
            'starting_price': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '$25.00', 'step': '1', 'min': '1'}),
            'reserve_price': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '$50.00 (optional)', 'step': '1', 'min': '1'}),
            'buy_now_price': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '$75.00', 'step': '1', 'min': '1'}),
            'bid_increment': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '$1', 'step': '1', 'min': '1'}),
            'trade_notes': forms.Textarea(attrs={'class': 'form-input', 'rows': 4, 'placeholder': 'What are you looking for in return?'}),
            'allow_cash': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'allow_offers': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'minimum_offer': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01', 'min': '1', 'placeholder': 'Leave empty and every offer reaches you'}),
            'package_weight_oz': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '8.0', 'step': '0.5', 'min': '0.5'}),
            'package_length_in': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '10', 'step': '0.5', 'min': '1'}),
            'package_width_in': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '7', 'step': '0.5', 'min': '1'}),
            'package_height_in': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '1', 'step': '0.5', 'min': '0.5'}),
            'shipping_service': forms.Select(attrs={'class': 'form-select'}),
            'shipping_payer': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['state'].queryset = State.objects.order_by('-is_primary_default', 'name')
        self.fields['source_collection_item'].queryset = CollectionItem.objects.none()
        self.fields['featured_image'].required = False
        self.fields['license_year'].required = False
        # Model defaults cover these — never block a submit on them.
        for optional_field in ('bid_increment', 'shipping_service', 'shipping_payer'):
            self.fields[optional_field].required = False

        # Trade is not a listing type — trades start from collections;
        # legacy trade rows keep the option only while being edited.
        if not (self.instance.pk and self.instance.listing_type == 'trade'):
            self.fields['listing_type'].choices = [
                (value, label) for value, label in Listing.LISTING_TYPE_CHOICES if value != 'trade'
            ]

        selected_state = self._resolve_state()
        if selected_state:
            self.fields['state'].initial = selected_state
        self._set_reference_querysets(selected_state)
        self._apply_year_bounds(selected_state)

        if self.user and self.user.is_authenticated:
            self.fields['source_collection_item'].queryset = CollectionItem.objects.filter(owner=self.user).order_by('-created_at')
            self.fields['ship_from_address'].queryset = Address.objects.filter(user=self.user)
            if not self.instance.pk and not self.initial.get('ship_from_address'):
                profile = getattr(self.user, 'profile', None)
                if profile and profile.shipping_address_id:
                    self.fields['ship_from_address'].initial = profile.shipping_address_id

        if self.instance and self.instance.pk:
            self.fields['colors'].initial = self.instance.colors
            for category in FORM_LICENSE_TYPE_CATEGORIES:
                selected = self.instance.license_types.filter(category=category).order_by('name')
                if category == 'addon_type':
                    self.fields[category].initial = list(selected)
                elif selected.first():
                    self.fields[category].initial = selected.first()
        elif self.user and self.user.is_authenticated and not self.is_bound:
            # New listing: apply the seller's saved listing defaults
            saved = getattr(getattr(self.user, 'profile', None), 'listing_defaults', None) or {}
            for field in ('shipping_service', 'shipping_payer', 'package_weight_oz',
                          'package_length_in', 'package_width_in', 'package_height_in',
                          'auto_relist', 'bid_increment', 'local_pickup_available',
                          'local_pickup_location'):
                if field in saved and not self.initial.get(field):
                    self.fields[field].initial = saved[field]

    def _resolve_state(self):
        state = None
        if self.is_bound:
            state_id = self.data.get('state')
            if state_id and state_id.isdigit():
                state = State.objects.filter(pk=int(state_id)).first()
        if state is None and self.initial.get('state'):
            initial_state = self.initial['state']
            state = initial_state if isinstance(initial_state, State) else State.objects.filter(pk=initial_state).first()
        if state is None and self.instance and self.instance.pk:
            state = self.instance.state or getattr(self.instance.county_ref, 'state', None)
        if state is None:
            state = State.objects.filter(is_primary_default=True).first() or State.objects.order_by('name').first()
        return state

    def _set_reference_querysets(self, state):
        if state:
            self.fields['county_ref'].queryset = GeographicUnit.objects.filter(state=state).order_by('sort_order', 'name')
            self.fields['county_ref'].label = state.issuance_unit_label or 'Geographic Unit'
        else:
            self.fields['county_ref'].queryset = GeographicUnit.objects.none()
            self.fields['county_ref'].label = 'Geographic Unit'

        for category in FORM_LICENSE_TYPE_CATEGORIES:
            self.fields[category].queryset = _state_license_type_queryset(state, category)

    def _apply_year_bounds(self, state):
        """Mirror the server-side year rules onto the rendered input so the
        browser flags violations before a submit round-trip."""
        max_year = timezone.now().year - 25
        min_year = (state.min_license_year or ABSOLUTE_MIN_LICENSE_YEAR) if state else ABSOLUTE_MIN_LICENSE_YEAR
        self.fields['license_year'].widget.attrs.update({'min': min_year, 'max': max_year})
        state_label = state.name if state else 'This state'
        self.fields['license_year'].help_text = (
            f'{state_label}: {min_year}–{max_year}. Only expired, antique items (25+ years old) '
            'can be listed — leave blank if the year is unknown.'
        )

    def clean(self):
        cleaned_data = super().clean()
        # A standalone add-on has no base-license dimensions; drop anything the
        # seller picked while those fields were hidden, so it can't save or
        # invisibly satisfy the at-least-one-attribute rule below.
        if cleaned_data.get('item_kind') == 'addon':
            cleaned_data['addons_attached'] = None
            for category in ('residency', 'holder_eligibility', 'activity_scope', 'duration'):
                cleaned_data[category] = None
                cleaned_data[f'{category}_other'] = ''
        # Optional-with-model-default fields: blank means "use the default"
        if not cleaned_data.get('shipping_service'):
            cleaned_data['shipping_service'] = 'cheapest'
        if not cleaned_data.get('shipping_payer'):
            cleaned_data['shipping_payer'] = 'buyer'
        if not cleaned_data.get('bid_increment'):
            cleaned_data['bid_increment'] = Decimal('1')
        state = cleaned_data.get('state')
        county_ref = cleaned_data.get('county_ref')
        license_year = cleaned_data.get('license_year')
        listing_type = cleaned_data.get('listing_type')
        starting_price = cleaned_data.get('starting_price')
        reserve_price = cleaned_data.get('reserve_price')
        buy_now_price = cleaned_data.get('buy_now_price')
        trade_notes = (cleaned_data.get('trade_notes') or '').strip()
        duration_days = cleaned_data.get('duration_days')
        source_collection_item = cleaned_data.get('source_collection_item')
        featured_image = cleaned_data.get('featured_image') or getattr(self.instance, 'featured_image', None)
        selected_dimensions = [cleaned_data.get(category) for category in FORM_LICENSE_TYPE_CATEGORIES]
        selected_shape = cleaned_data.get('shape')
        selected_colors = cleaned_data.get('colors') or []

        if county_ref and state and county_ref.state_id != state.id:
            self.add_error('county_ref', 'Selected geographic unit does not belong to the chosen state.')
        max_year = timezone.now().year - 25
        if license_year is not None:
            if state and state.min_license_year and license_year < state.min_license_year:
                self.add_error('license_year', f'Earliest known hunting license year for {state.name} is {state.min_license_year}.')
            elif license_year < ABSOLUTE_MIN_LICENSE_YEAR:
                self.add_error('license_year', "That's earlier than any known hunting license — check the year.")
            if license_year > max_year:
                self.add_error('license_year', f'Only antique licenses (25+ years old) are tradeable — the latest allowed year is {max_year}.')

        # era_label is required when license_year is not provided
        era_label = cleaned_data.get('era_label')
        if license_year is None and not era_label:
            self.add_error('era_label', 'Era is required when license year is unknown.')

        if listing_type == 'auction':
            if starting_price is None:
                self.add_error('starting_price', 'Starting price is required for auctions.')
            if not duration_days:
                self.add_error('duration_days', 'Duration is required for auctions.')
            if reserve_price and starting_price and reserve_price < starting_price:
                self.add_error('reserve_price', 'Reserve price must be at least the starting price.')
        elif listing_type == 'buy_now':
            if buy_now_price is None:
                self.add_error('buy_now_price', 'Buy now price is required for The General Store listings.')
        elif listing_type == 'trade' and not trade_notes:
            self.add_error('trade_notes', 'Trade preferences are required for The Trading Block listings.')

        if not featured_image:
            source_has_image = bool(source_collection_item and source_collection_item.images.exists())
            if not source_has_image:
                self.add_error('featured_image', 'Featured image is required unless source collection item has images.')

        if not any(selected_dimensions) and not selected_shape and not selected_colors:
            raise forms.ValidationError('Select at least one taxonomy or physical attribute value to describe the item.')

        for category in FORM_LICENSE_TYPE_CATEGORIES:
            selected = cleaned_data.get(category)
            other_text = (cleaned_data.get(f'{category}_other') or '').strip()
            if category == 'addon_type':
                has_other = any(item.name.lower() == 'other' for item in (selected or []))
            else:
                has_other = bool(selected and selected.name.lower() == 'other')
            if has_other and not other_text:
                self.add_error(f'{category}_other', 'Please describe the missing value.')

        if selected_shape == 'other' and not (cleaned_data.get('shape_other') or '').strip():
            self.add_error('shape_other', 'Please describe the missing shape.')
        if 'other' in selected_colors and not (cleaned_data.get('colors_other') or '').strip():
            self.add_error('colors_other', 'Please describe the missing color.')

        scheduled_at = cleaned_data.get('scheduled_at')
        if scheduled_at:
            now = timezone.now()
            if scheduled_at <= now:
                self.add_error('scheduled_at', 'Scheduled go-live must be in the future.')
            elif scheduled_at > now + timedelta(days=30):
                self.add_error('scheduled_at', 'Scheduled go-live cannot be more than 30 days in the future.')

        local_pickup_available = cleaned_data.get('local_pickup_available')
        local_pickup_location = (cleaned_data.get('local_pickup_location') or '').strip()
        if local_pickup_available and not local_pickup_location:
            self.add_error('local_pickup_location', 'Enter a location for local pickup.')

        return cleaned_data

    def save(self, commit=True):
        listing = super().save(commit=False)
        listing.state = self.cleaned_data['state']
        listing.county_ref = self.cleaned_data.get('county_ref')
        listing.county = listing.county_ref.name if listing.county_ref else ''
        listing.is_statewide = bool(listing.county_ref and listing.county_ref.is_statewide)
        listing.shape = self.cleaned_data.get('shape') or ''
        listing.colors = self.cleaned_data.get('colors') or []
        listing.local_pickup_available = bool(self.cleaned_data.get('local_pickup_available'))
        listing.local_pickup_location = (self.cleaned_data.get('local_pickup_location') or '').strip()
        listing.serial_number = (self.cleaned_data.get('serial_number') or '').strip()
        listing.era_label = self.cleaned_data.get('era_label') or None

        listing_type = self.cleaned_data['listing_type']
        duration = self.cleaned_data.get('duration_days')
        scheduled_at = self.cleaned_data.get('scheduled_at')

        if listing_type == 'auction':
            listing.auto_relist = bool(self.cleaned_data.get('auto_relist'))
            go_live = scheduled_at or timezone.now()
            listing.auction_end = go_live + timedelta(days=int(duration))
            listing.buy_now_price = None
            listing.trade_notes = ''
            listing.allow_cash = False
            listing.allow_offers = False
        elif listing_type == 'buy_now':
            listing.starting_price = None
            listing.current_bid = None
            listing.reserve_price = None
            listing.auction_end = None
            listing.trade_notes = ''
            listing.allow_cash = False
        else:
            listing.starting_price = None
            listing.current_bid = None
            listing.reserve_price = None
            listing.buy_now_price = None
            listing.auction_end = None
            # Offers negotiate a buy-now price; trades have their own offer flow.
            listing.allow_offers = False

        # Scheduled go-live: only apply on new listings (no pk yet)
        if not listing.pk and scheduled_at:
            listing.scheduled_at = scheduled_at
            listing.status = 'scheduled'
        elif not listing.pk:
            listing.status = 'active'

        if commit:
            listing.save()
            selected_types = []
            for category in FORM_LICENSE_TYPE_CATEGORIES:
                value = self.cleaned_data.get(category)
                if not value:
                    continue
                if category == 'addon_type':
                    selected_types.extend(value)
                else:
                    selected_types.append(value)
            listing.license_types.set(selected_types)
            self._create_other_suggestions(listing)
        return listing

    def _create_other_suggestions(self, listing):
        if not self.user or not self.user.is_authenticated:
            return

        for category in FORM_LICENSE_TYPE_CATEGORIES:
            selected = self.cleaned_data.get(category)
            other_text = (self.cleaned_data.get(f'{category}_other') or '').strip()
            if category == 'addon_type':
                other_row = next((item for item in (selected or []) if item.name.lower() == 'other'), None)
            else:
                other_row = selected if (selected and selected.name.lower() == 'other') else None
            if other_row and other_text:
                ReferenceDataSuggestion.objects.create(
                    user=self.user,
                    suggestion_type='new_value',
                    target_model='license_type',
                    target_id=other_row.id,
                    field_name=category,
                    current_value='Other',
                    proposed_value=other_text,
                )

        shape_other = (self.cleaned_data.get('shape_other') or '').strip()
        if self.cleaned_data.get('shape') == 'other' and shape_other:
            ReferenceDataSuggestion.objects.create(
                user=self.user,
                suggestion_type='new_value',
                target_model='listing',
                target_id=listing.id,
                field_name='shape',
                current_value='Other',
                proposed_value=shape_other,
            )

        colors_other = (self.cleaned_data.get('colors_other') or '').strip()
        if 'other' in (self.cleaned_data.get('colors') or []) and colors_other:
            ReferenceDataSuggestion.objects.create(
                user=self.user,
                suggestion_type='new_value',
                target_model='listing',
                target_id=listing.id,
                field_name='colors',
                current_value='Other',
                proposed_value=colors_other,
            )


class ListingImageForm(forms.ModelForm):
    """One photograph and what it is of.

    ``image_role`` travels with the file rather than being read off the grid
    position, so reordering the slots cannot relabel a back as a front.
    """

    class Meta:
        model = ListingImage
        fields = ['image', 'image_role', 'sort_order']
        widgets = {
            'sort_order': forms.HiddenInput(),
            'image_role': forms.HiddenInput(),
        }


ListingImageFormSet = forms.inlineformset_factory(
    Listing,
    ListingImage,
    form=ListingImageForm,
    extra=4,
    max_num=4,
    validate_max=True,
    can_delete=True,
)
