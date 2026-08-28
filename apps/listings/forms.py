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
from apps.core.widgets import TagsStillAttachedSelect
from apps.listings.models import ERA_LABEL_CHOICES, Listing, ListingImage


def _state_license_type_queryset(state, category):
    queryset = LicenseType.objects.filter(category=category, is_system_value=True)
    if state:
        queryset = queryset.filter(Q(state=state) | Q(state__isnull=True) | Q(state__code='FD'))
    else:
        queryset = queryset.filter(Q(state__isnull=True) | Q(state__code='FD'))
    return queryset.order_by('name').distinct()


def publish_gaps(listing):
    """What the item still needs before it can be public.

    Step 2 saves drafts as thin as a title — required-to-publish fields
    gate *publishing*, so the checks live here and run on the terms page,
    the only place a listing goes public. Returned as readable phrases the
    band can print verbatim.
    """
    gaps = []
    has_image = bool(listing.featured_image) or bool(
        listing.source_collection_item_id
        and listing.source_collection_item.images.exists()
    )
    if not has_image:
        gaps.append('a front photograph')
    if not listing.state_id:
        gaps.append('the issuing state')
    if not (listing.license_year or listing.era_label):
        gaps.append('the year, or roughly the era')
    if not listing.condition_grade:
        gaps.append('a condition grade')
    if not (listing.description or '').strip():
        gaps.append('a line of description')
    if not (listing.license_types.exists() or listing.shape or listing.colors):
        gaps.append('one detail collectors filter on — residency, material, shape or colour')
    return gaps


class ListingForm(forms.ModelForm):
    """Step 2 — the item.

    Only what the thing *is*: photographs, title, place, year, condition and
    the taxonomy. The terms — prices, duration, shipping — live on
    :class:`ListingTermsForm`, because each destination carries only its own
    questions and nothing is public until step 3 is done. A new listing saves
    as a draft.
    """

    state = forms.ModelChoiceField(
        queryset=State.objects.none(),
        required=True,
        empty_label='Choose a state',
        widget=forms.Select(attrs={'class': 'kb-select'}),
    )
    county_ref = forms.ModelChoiceField(
        queryset=GeographicUnit.objects.none(),
        required=False,
        empty_label='Select geographic unit',
        widget=forms.Select(attrs={'class': 'kb-select'}),
    )
    residency = forms.ModelChoiceField(queryset=LicenseType.objects.none(), required=False, empty_label='Select residency', widget=forms.Select(attrs={'class': 'kb-select'}))
    residency_other = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'kb-input', 'placeholder': 'Enter residency value'}))
    holder_eligibility = forms.ModelChoiceField(queryset=LicenseType.objects.none(), required=False, empty_label='Select holder eligibility', widget=forms.Select(attrs={'class': 'kb-select'}))
    holder_eligibility_other = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'kb-input', 'placeholder': 'Enter eligibility value'}))
    activity_scope = forms.ModelChoiceField(queryset=LicenseType.objects.none(), required=False, empty_label='Select activity scope', widget=forms.Select(attrs={'class': 'kb-select'}))
    activity_scope_other = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'kb-input', 'placeholder': 'Enter activity scope'}))
    duration = forms.ModelChoiceField(queryset=LicenseType.objects.none(), required=False, empty_label='Select duration', widget=forms.Select(attrs={'class': 'kb-select'}))
    duration_other = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'kb-input', 'placeholder': 'Enter duration'}))
    addon_type = forms.ModelMultipleChoiceField(
        queryset=LicenseType.objects.none(), required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'chip-checkboxes'}),
    )
    addon_type_other = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'kb-input', 'placeholder': 'Enter add-on type'}))
    material = forms.ModelChoiceField(queryset=LicenseType.objects.none(), required=False, empty_label='Select material', widget=forms.Select(attrs={'class': 'kb-select'}))
    material_other = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'kb-input', 'placeholder': 'Enter material'}))
    issue_class = forms.ModelChoiceField(queryset=LicenseType.objects.none(), required=False, empty_label='Ordinary issue', widget=forms.Select(attrs={'class': 'kb-select'}))
    issue_class_other = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'kb-input', 'placeholder': 'Enter issue class'}))
    shape = forms.ChoiceField(
        choices=[('', 'Select shape')] + SHAPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'kb-select'}),
    )
    shape_other = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'kb-input', 'placeholder': 'Enter shape'}))
    colors = forms.MultipleChoiceField(
        choices=COLOR_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'chip-checkboxes'}),
    )
    colors_other = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'kb-input', 'placeholder': 'Enter color'}))
    source_collection_item = forms.ModelChoiceField(
        queryset=CollectionItem.objects.none(),
        required=False,
        empty_label='None',
        widget=forms.Select(attrs={'class': 'kb-select'}),
        help_text='Prefill safe fields from an item in your collection.',
    )
    serial_number = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'kb-input', 'placeholder': 'e.g. A-12345'}),
        help_text='License serial or stub number, if visible.',
    )
    era_label = forms.ChoiceField(
        choices=[('', 'Select era')] + ERA_LABEL_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'kb-select'}),
        help_text='Required when license year is unknown.',
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
            'issue_class',
            'shape',
            'colors',
            'condition_grade',
            'condition_description',
            'is_restored',
            'serial_number',
            'era_label',
            'featured_image',
        ]
        widgets = {
            'listing_type': forms.Select(attrs={'class': 'kb-select'}),
            'item_kind': forms.RadioSelect(attrs={'class': 'chip-radios'}),
            'addons_attached': TagsStillAttachedSelect(attrs={'class': 'kb-select'}),
            # Placeholders and box heights are 4a's own: the description a
            # 44px two-liner, the condition note a 60px one.
            'title': forms.TextInput(attrs={'class': 'kb-input', 'placeholder': 'Written for you from the answers below — edit freely'}),
            'description': forms.Textarea(attrs={'class': 'kb-textarea', 'placeholder': 'Where it came from, what the photographs can’t show.', 'rows': 2, 'maxlength': 2000}),
            'license_year': forms.NumberInput(attrs={'class': 'kb-input', 'placeholder': '1942 (leave blank if unknown)'}),
            'condition_grade': forms.RadioSelect(attrs={'class': 'chip-radios'}),
            'condition_description': forms.Textarea(attrs={'class': 'kb-textarea', 'rows': 2, 'maxlength': 2000, 'placeholder': 'Foxing, tears, tape, a bent pin, any repair — the things a buyer will ask about.'}),
            'is_restored': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['state'].queryset = State.objects.order_by('-is_primary_default', 'name')
        # 14a: the unit word rides beside each state ("Colorado · GMU"),
        # so choosing one says what the next field will ask for.
        self.fields['state'].label_from_instance = lambda state: state.option_label
        self.fields['source_collection_item'].queryset = CollectionItem.objects.none()
        self.fields['featured_image'].required = False
        self.fields['license_year'].required = False

        # Step 2 never hard-blocks: a draft can be as thin as a title, and
        # publish_gaps() gates the terms page instead. Only a listing that
        # is already public keeps the full requirements as form errors —
        # an edit must not quietly strip a live listing below publishable.
        self.require_complete = bool(self.instance.pk and self.instance.status != 'draft')
        if not self.require_complete:
            for name in ('description', 'condition_grade', 'state'):
                self.fields[name].required = False
        # The grade renders as a chip ladder — a "---------" radio is not a
        # rung anybody can stand on.
        self.fields['condition_grade'].choices = [
            choice for choice in self.fields['condition_grade'].choices if choice[0]
        ]
        # Plain file input: on the edit pages the bound ClearableFileInput
        # printed "Currently: <path> Change:" — the thumbnail already
        # shows what's there.
        self.fields['featured_image'].widget = forms.FileInput()

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

        # Once a listing is bound to its shelf record the pair is one
        # item — a POST that happens to omit the field must not quietly
        # sever the link and orphan the piece. Disabled fields ignore
        # posted data and keep the stored value.
        if self.instance.pk and self.instance.source_collection_item_id:
            self.fields['source_collection_item'].disabled = True

        if self.instance and self.instance.pk:
            self.fields['colors'].initial = self.instance.colors
            for category in FORM_LICENSE_TYPE_CATEGORIES:
                selected = self.instance.license_types.filter(category=category).order_by('name')
                if category == 'addon_type':
                    self.fields[category].initial = list(selected)
                elif selected.first():
                    self.fields[category].initial = selected.first()

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
        # No fallback to a default state: a fresh form says "Choose a state"
        # rather than quietly deciding the item is from Pennsylvania.
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
        if state:
            self.fields['license_year'].help_text = (
                f'{state.name}: {min_year}–{max_year}. Only expired, antique items (25+ years old) '
                'can be listed — leave blank if the year is unknown.'
            )
        else:
            # No state chosen yet — quote no range that isn't its.
            self.fields['license_year'].help_text = (
                'Only expired, antique items (25+ years old) can be listed — '
                'pick the state to see its years, and leave blank if the year is unknown.'
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
        state = cleaned_data.get('state')
        county_ref = cleaned_data.get('county_ref')
        license_year = cleaned_data.get('license_year')
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

        # Required-to-publish, not required-to-save: on a draft these come
        # back from publish_gaps() at the terms page instead of blocking
        # the save here (the old hard block was why the foot buttons looked
        # dead — an invisible rule with no field to point at).
        if self.require_complete:
            era_label = cleaned_data.get('era_label')
            if license_year is None and not era_label:
                self.add_error('era_label', 'Era is required when license year is unknown.')

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

        return cleaned_data

    def save(self, commit=True):
        listing = super().save(commit=False)
        listing.state = self.cleaned_data.get('state')
        listing.county_ref = self.cleaned_data.get('county_ref')
        listing.county = listing.county_ref.name if listing.county_ref else ''
        listing.is_statewide = bool(listing.county_ref and listing.county_ref.is_statewide)
        listing.shape = self.cleaned_data.get('shape') or ''
        listing.colors = self.cleaned_data.get('colors') or []
        listing.serial_number = (self.cleaned_data.get('serial_number') or '').strip()
        listing.era_label = self.cleaned_data.get('era_label') or None

        # The item is described; the terms aren't set. Publishing — prices,
        # duration, auction_end, active/scheduled — is ListingTermsForm's job.
        if not listing.pk:
            listing.status = 'draft'

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


class ListingTermsForm(forms.ModelForm):
    """Step 3 — the terms, one panel per destination.

    Carries only the destination's own questions plus the shared getting-it-
    there strip. Publishing happens here and nowhere else: a draft flips to
    active (or scheduled) when this form saves with ``publish=True``. On the
    edit page it saves with ``publish=False`` so touching a live listing's
    price never resets its clock — and a live auction doesn't offer the
    duration or go-live fields at all, because the clock has already run.
    """

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
        widget=forms.Select(attrs={'class': 'kb-select'}),
    )
    scheduled_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(
            attrs={'class': 'kb-input', 'type': 'datetime-local'},
            format='%Y-%m-%dT%H:%M',
        ),
        help_text='Handy before a show. Max 30 days out; leave blank to go live now.',
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'],
    )
    auto_relist = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
    )
    local_pickup_available = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
    )
    local_pickup_location = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'kb-input', 'placeholder': 'e.g. Lancaster, PA'}),
    )
    ship_from_address = forms.ModelChoiceField(
        queryset=Address.objects.none(),
        required=False,
        empty_label='Account default address',
        widget=forms.Select(attrs={'class': 'kb-select'}),
    )
    # The standing answer lives on the collection item, not the listing —
    # both the store panel and the collection panel set the same switch.
    open_to_trade = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
    )
    trade_wants = forms.CharField(
        required=False, max_length=250,
        widget=forms.TextInput(attrs={'class': 'kb-input', 'placeholder': 'Anything pre-1930 from a county I&rsquo;m missing.'}),
    )

    class Meta:
        model = Listing
        fields = [
            'starting_price',
            'reserve_price',
            'bid_increment',
            'buy_now_price',
            'allow_offers',
            'minimum_offer',
            'local_pickup_available',
            'local_pickup_location',
            'ship_from_address',
            'package_weight_oz',
            'package_length_in',
            'package_width_in',
            'package_height_in',
            'shipping_service',
            'shipping_payer',
        ]
        widgets = {
            'starting_price': forms.NumberInput(attrs={'class': 'kb-input', 'placeholder': '$25.00', 'step': '1', 'min': '1'}),
            'reserve_price': forms.NumberInput(attrs={'class': 'kb-input', 'placeholder': '$50.00 (optional)', 'step': '1', 'min': '1'}),
            'buy_now_price': forms.NumberInput(attrs={'class': 'kb-input', 'placeholder': '$75.00', 'step': '1', 'min': '1'}),
            'bid_increment': forms.NumberInput(attrs={'class': 'kb-input', 'placeholder': '$1', 'step': '1', 'min': '1'}),
            'allow_offers': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'minimum_offer': forms.NumberInput(attrs={'class': 'kb-input', 'step': '0.01', 'min': '1', 'placeholder': 'Leave empty and every offer reaches you'}),
            'package_weight_oz': forms.NumberInput(attrs={'class': 'kb-input', 'placeholder': '8.0', 'step': '0.5', 'min': '0.5'}),
            'package_length_in': forms.NumberInput(attrs={'class': 'kb-input', 'placeholder': '10', 'step': '0.5', 'min': '1'}),
            'package_width_in': forms.NumberInput(attrs={'class': 'kb-input', 'placeholder': '7', 'step': '0.5', 'min': '1'}),
            'package_height_in': forms.NumberInput(attrs={'class': 'kb-input', 'placeholder': '1', 'step': '0.5', 'min': '0.5'}),
            'shipping_service': forms.Select(attrs={'class': 'kb-select'}),
            'shipping_payer': forms.Select(attrs={'class': 'kb-select'}),
        }

    AUCTION_ONLY = ('starting_price', 'reserve_price', 'bid_increment', 'duration_days', 'auto_relist')
    STORE_ONLY = ('buy_now_price', 'allow_offers', 'minimum_offer', 'open_to_trade', 'trade_wants')

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.listing_type = self.instance.listing_type
        # Scheduled is NOT live: nothing is public and no clock has run, so
        # the duration and go-live fields stay editable — a seller who
        # scheduled a week out must be able to reschedule or go up now.
        self.is_live = bool(self.instance.pk) and self.instance.status not in ('draft', 'scheduled')

        drop = self.STORE_ONLY if self.listing_type == 'auction' else self.AUCTION_ONLY
        for name in drop:
            self.fields.pop(name, None)
        if self.is_live:
            # The clock question was answered when the lot opened.
            self.fields.pop('duration_days', None)
            self.fields.pop('scheduled_at', None)
        elif self.instance.pk and self.instance.scheduled_at \
                and 'scheduled_at' in self.fields:
            # A scheduled listing reopens its terms with the date it was
            # given, so rescheduling starts from the truth.
            self.fields['scheduled_at'].initial = self.instance.scheduled_at

        for optional_field in ('bid_increment', 'shipping_service', 'shipping_payer'):
            if optional_field in self.fields:
                self.fields[optional_field].required = False

        if self.user and self.user.is_authenticated:
            self.fields['ship_from_address'].queryset = Address.objects.filter(user=self.user)
            if not self.initial.get('ship_from_address') and not self.instance.ship_from_address_id:
                profile = getattr(self.user, 'profile', None)
                if profile and profile.shipping_address_id:
                    self.fields['ship_from_address'].initial = profile.shipping_address_id

        # A fresh draft starts from the seller's saved selling defaults.
        if not self.is_bound and not self.is_live:
            saved = getattr(getattr(self.user, 'profile', None), 'listing_defaults', None) or {}
            for field in ('shipping_service', 'shipping_payer', 'package_weight_oz',
                          'package_length_in', 'package_width_in', 'package_height_in',
                          'auto_relist', 'bid_increment', 'local_pickup_available',
                          'local_pickup_location'):
                if field in self.fields and field in saved and not self.initial.get(field):
                    self.fields[field].initial = saved[field]

        source = self.instance.source_collection_item
        if source and 'open_to_trade' in self.fields and not self.is_bound:
            self.fields['open_to_trade'].initial = source.tradeability == 'open'
            self.fields['trade_wants'].initial = source.trade_wants

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('shipping_service'):
            cleaned_data['shipping_service'] = 'cheapest'
        if not cleaned_data.get('shipping_payer'):
            cleaned_data['shipping_payer'] = 'buyer'

        if self.listing_type == 'auction':
            starting_price = cleaned_data.get('starting_price')
            reserve_price = cleaned_data.get('reserve_price')
            if not cleaned_data.get('bid_increment'):
                cleaned_data['bid_increment'] = Decimal('1')
            if starting_price is None:
                self.add_error('starting_price', 'Starting price is required for auctions.')
            if not self.is_live and not cleaned_data.get('duration_days'):
                self.add_error('duration_days', 'Duration is required for auctions.')
            if reserve_price and starting_price and reserve_price < starting_price:
                self.add_error('reserve_price', 'Reserve price must be at least the starting price.')
        else:
            if cleaned_data.get('buy_now_price') is None:
                self.add_error('buy_now_price', 'Your price is required for The General Store.')

        scheduled_at = cleaned_data.get('scheduled_at')
        if scheduled_at:
            now = timezone.now()
            if scheduled_at <= now:
                self.add_error('scheduled_at', 'Scheduled go-live must be in the future.')
            elif scheduled_at > now + timedelta(days=30):
                self.add_error('scheduled_at', 'Scheduled go-live cannot be more than 30 days in the future.')

        if cleaned_data.get('local_pickup_available') and not (cleaned_data.get('local_pickup_location') or '').strip():
            self.add_error('local_pickup_location', 'Enter a location for local pickup.')

        return cleaned_data

    def save(self, commit=True, publish=False):
        listing = super().save(commit=False)
        listing.local_pickup_available = bool(self.cleaned_data.get('local_pickup_available'))
        listing.local_pickup_location = (self.cleaned_data.get('local_pickup_location') or '').strip()

        if self.listing_type == 'auction':
            listing.auto_relist = bool(self.cleaned_data.get('auto_relist')) if not self.is_live else listing.auto_relist
            listing.buy_now_price = None
            listing.trade_notes = ''
            listing.allow_cash = False
            listing.allow_offers = False
        else:
            listing.starting_price = None
            listing.current_bid = None
            listing.reserve_price = None
            listing.auction_end = None
            listing.trade_notes = ''
            listing.allow_cash = False

        if publish and listing.status in ('draft', 'scheduled'):
            # A scheduled listing publishes again freely: a new date
            # reschedules it, a cleared date puts it up right now.
            scheduled_at = self.cleaned_data.get('scheduled_at')
            if self.listing_type == 'auction':
                go_live = scheduled_at or timezone.now()
                listing.auction_end = go_live + timedelta(days=int(self.cleaned_data['duration_days']))
            listing.scheduled_at = scheduled_at
            listing.status = 'scheduled' if scheduled_at else 'active'

        if commit:
            listing.save()
            source = listing.source_collection_item
            if source and 'open_to_trade' in self.fields:
                source.tradeability = 'open' if self.cleaned_data.get('open_to_trade') else 'closed'
                source.trade_wants = (self.cleaned_data.get('trade_wants') or '').strip()
                source.save(update_fields=['tradeability', 'trade_wants', 'updated_at'])
        return listing


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
            # A plain file input: the default ClearableFileInput prints
            # "Currently: <path> Change:" — a filesystem path is not a
            # sentence anybody should read. The thumbnail shows what's
            # there; the drop checkbox removes it.
            'image': forms.FileInput(),
        }

    def has_changed(self):
        """A new row with a role but no photograph is an empty slot, not a
        half-filled form. Counting it as changed made Django demand its
        image — four invisible errors and a submit that looked dead."""
        if self.instance.pk:
            return super().has_changed()
        if not (self.files.get(self.add_prefix('image')) or self.data.get(self.add_prefix('image'))):
            return False
        return super().has_changed()


ListingImageFormSet = forms.inlineformset_factory(
    Listing,
    ListingImage,
    form=ListingImageForm,
    extra=4,
    max_num=4,
    validate_max=True,
    can_delete=True,
)
