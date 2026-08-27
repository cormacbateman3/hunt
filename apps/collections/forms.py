from django import forms
from django.db.models import Q
from django.utils import timezone

from apps.core.constants import (
    ABSOLUTE_MIN_LICENSE_YEAR,
    COLOR_CHOICES,
    FORM_LICENSE_TYPE_CATEGORIES,
    SHAPE_CHOICES,
)
from apps.core.models import GeographicUnit, LicenseType, ReferenceDataSuggestion, State
from apps.core.widgets import TagsStillAttachedSelect
from apps.collections.models import (
    MAX_FEATURED,
    CollectionItem,
    CollectionItemImage,
    WantedItem,
)
from apps.listings.models import ERA_LABEL_CHOICES


def _state_license_type_queryset(state, category=None):
    queryset = LicenseType.objects.filter(is_system_value=True)
    if category:
        queryset = queryset.filter(category=category)
    if state:
        queryset = queryset.filter(Q(state=state) | Q(state__isnull=True) | Q(state__code='FD'))
    else:
        queryset = queryset.filter(Q(state__isnull=True) | Q(state__code='FD'))
    return queryset.order_by('category', 'name').distinct()


class CollectionItemForm(forms.ModelForm):
    state = forms.ModelChoiceField(queryset=State.objects.none(), required=True, empty_label='Choose a state', widget=forms.Select(attrs={'class': 'kb-select'}))
    county = forms.ModelChoiceField(queryset=GeographicUnit.objects.none(), required=False, empty_label='Select geographic unit', widget=forms.Select(attrs={'class': 'kb-select'}))
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
    shape = forms.ChoiceField(choices=[('', 'Select shape')] + SHAPE_CHOICES, required=False, widget=forms.Select(attrs={'class': 'kb-select'}))
    shape_other = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'kb-input', 'placeholder': 'Enter shape'}))
    colors = forms.MultipleChoiceField(choices=COLOR_CHOICES, required=False, widget=forms.CheckboxSelectMultiple(attrs={'class': 'chip-checkboxes'}))
    colors_other = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'kb-input', 'placeholder': 'Enter color'}))
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
        model = CollectionItem
        fields = [
            'item_kind',
            'addons_attached',
            'title',
            'description',
            'state',
            'license_year',
            'county',
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
            'is_public',
            'tradeability',
            'trade_wants',
            'disposition',
            'purchase_price',
            'acquired_note',
            'private_note',
            'serial_number',
            'era_label',
        ]
        widgets = {
            'item_kind': forms.RadioSelect(attrs={'class': 'chip-radios'}),
            'addons_attached': TagsStillAttachedSelect(attrs={'class': 'kb-select'}),
            # Placeholders and box heights are 4a's own.
            'title': forms.TextInput(attrs={'class': 'kb-input', 'placeholder': 'Written for you from the answers below — edit freely'}),
            'description': forms.Textarea(attrs={'class': 'kb-textarea', 'rows': 2, 'maxlength': 2000, 'placeholder': 'Where it came from, what the photographs can’t show.'}),
            'license_year': forms.NumberInput(attrs={'class': 'kb-input', 'placeholder': '1942 (leave blank if unknown)'}),
            'condition_grade': forms.RadioSelect(attrs={'class': 'chip-radios'}),
            'condition_description': forms.Textarea(attrs={'class': 'kb-textarea', 'rows': 2, 'maxlength': 2000, 'placeholder': 'Foxing, tears, tape, a bent pin, any repair — the things a buyer will ask about.'}),
            'is_restored': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'tradeability': forms.RadioSelect(),
            'trade_wants': forms.TextInput(attrs={'class': 'kb-input', 'placeholder': 'Anything pre-1930 from a county I am missing'}),
            'disposition': forms.RadioSelect(attrs={'class': 'chip-radios'}),
            'purchase_price': forms.NumberInput(attrs={'class': 'kb-input', 'step': '0.01', 'min': '0', 'placeholder': '48.00'}),
            'acquired_note': forms.TextInput(attrs={'class': 'kb-input', 'placeholder': 'Mar 2026, Bloomsburg'}),
            'private_note': forms.Textarea(attrs={'class': 'kb-textarea', 'rows': 2, 'placeholder': 'A note to yourself about this piece.'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['state'].queryset = State.objects.order_by('-is_primary_default', 'name')
        # 14a: the unit word rides beside each state ("Colorado · GMU"),
        # so choosing one says what the next field will ask for.
        self.fields['state'].label_from_instance = lambda state: state.option_label
        # Not required, because a silence must not be read as an answer —
        # see clean_tradeability and clean_disposition.
        self.fields['tradeability'].required = False
        self.fields['disposition'].required = False
        # Chip ladder: the model's grade is optional here, so the quiet way
        # out is a named chip rather than a "---------" radio.
        self.fields['condition_grade'].choices = [('', 'Not set')] + [
            choice for choice in self.fields['condition_grade'].choices if choice[0]
        ]
        # `traded` and `sold` are the lifecycles' records (trade delivery,
        # paid order), not choices anybody makes on a form. Each stays
        # selectable only on a piece that already carries it, so editing
        # that piece doesn't force a different answer.
        lifecycle_values = {'traded', 'sold'}
        current = self.instance.disposition if self.instance.pk else None
        self.fields['disposition'].choices = [
            (value, label)
            for value, label in CollectionItem.DISPOSITION_CHOICES
            if value not in lifecycle_values or value == current
        ]

        state = self._resolve_state()
        if state:
            self.fields['state'].initial = state
        self._set_reference_querysets(state)
        self._apply_year_bounds(state)

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
            state = self.instance.state or getattr(self.instance.county, 'state', None)
        # No fallback to a default state: a fresh form says "Choose a state"
        # rather than quietly deciding the piece is from Pennsylvania.
        return state

    def _set_reference_querysets(self, state):
        if state:
            self.fields['county'].queryset = GeographicUnit.objects.filter(state=state).order_by('sort_order', 'name')
            self.fields['county'].label = state.issuance_unit_label or 'Geographic Unit'
        else:
            self.fields['county'].queryset = GeographicUnit.objects.none()
            self.fields['county'].label = 'Geographic Unit'
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
                'belong here — leave blank if the year is unknown.'
            )
        else:
            self.fields['license_year'].help_text = (
                'Only expired, antique items (25+ years old) belong here — '
                'pick the state to see its years, and leave blank if the year is unknown.'
            )

    def clean_tradeability(self):
        """A missing answer means *unchanged* — never *open*.

        The radio always posts something, so this only fires for a form built
        without the trade block. Reading a silence as "open" would flip a
        piece somebody had deliberately closed, which is the exact class of
        bug this field replaced a boolean to end.
        """
        answer = self.cleaned_data.get('tradeability')
        if answer:
            return answer
        if self.instance and self.instance.pk:
            return self.instance.tradeability
        return CollectionItem._meta.get_field('tradeability').get_default()

    def clean_disposition(self):
        """Same rule as tradeability: a form without the control (the
        add-from-order form, for one) must not quietly mark a piece held —
        or worse, un-mark one that has left."""
        answer = self.cleaned_data.get('disposition')
        if answer:
            return answer
        if self.instance and self.instance.pk:
            return self.instance.disposition
        return CollectionItem._meta.get_field('disposition').get_default()

    def clean(self):
        cleaned_data = super().clean()
        state = cleaned_data.get('state')
        county = cleaned_data.get('county')
        year = cleaned_data.get('license_year')
        # A standalone add-on has no base-license dimensions; drop anything
        # picked while those fields were hidden.
        if cleaned_data.get('item_kind') == 'addon':
            cleaned_data['addons_attached'] = None
            for category in ('residency', 'holder_eligibility', 'activity_scope', 'duration'):
                cleaned_data[category] = None
                cleaned_data[f'{category}_other'] = ''
        if county and state and county.state_id != state.id:
            self.add_error('county', 'Selected geographic unit does not belong to the chosen state.')
        max_year = timezone.now().year - 25
        if year is not None:
            if state and state.min_license_year and year < state.min_license_year:
                self.add_error('license_year', f'Earliest known hunting license year for {state.name} is {state.min_license_year}.')
            elif year < ABSOLUTE_MIN_LICENSE_YEAR:
                self.add_error('license_year', "That's earlier than any known hunting license — check the year.")
            if year > max_year:
                self.add_error('license_year', f'Only antique licenses (25+ years old) are collectible here - the latest allowed year is {max_year}.')

        # No at-least-one-attribute rule and no era-when-yearless rule here:
        # a shelf record is the collector's own catalogue and can be as
        # thin as they like. (The listing flow keeps those rules for
        # *publishing*, in publish_gaps.)
        for category in FORM_LICENSE_TYPE_CATEGORIES:
            selected = cleaned_data.get(category)
            other_text = (cleaned_data.get(f'{category}_other') or '').strip()
            if category == 'addon_type':
                has_other = any(item.name.lower() == 'other' for item in (selected or []))
            else:
                has_other = bool(selected and selected.name.lower() == 'other')
            if has_other and not other_text:
                self.add_error(f'{category}_other', 'Please describe the missing value.')
        if cleaned_data.get('shape') == 'other' and not (cleaned_data.get('shape_other') or '').strip():
            self.add_error('shape_other', 'Please describe the missing shape.')
        if 'other' in (cleaned_data.get('colors') or []) and not (cleaned_data.get('colors_other') or '').strip():
            self.add_error('colors_other', 'Please describe the missing color.')
        return cleaned_data

    def save(self, commit=True):
        item = super().save(commit=False)
        item.state = self.cleaned_data['state']
        item.shape = self.cleaned_data.get('shape') or ''
        item.colors = self.cleaned_data.get('colors') or []
        item.serial_number = (self.cleaned_data.get('serial_number') or '').strip()
        item.era_label = self.cleaned_data.get('era_label') or None
        if commit:
            item.save()
            selected_types = []
            for category in FORM_LICENSE_TYPE_CATEGORIES:
                value = self.cleaned_data.get(category)
                if not value:
                    continue
                if category == 'addon_type':
                    selected_types.extend(value)
                else:
                    selected_types.append(value)
            item.license_types.set(selected_types)
            self._create_other_suggestions(item)
        return item

    def _create_other_suggestions(self, item):
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
                target_model='collection_item',
                target_id=item.id,
                field_name='shape',
                current_value='Other',
                proposed_value=shape_other,
            )
        colors_other = (self.cleaned_data.get('colors_other') or '').strip()
        if 'other' in (self.cleaned_data.get('colors') or []) and colors_other:
            ReferenceDataSuggestion.objects.create(
                user=self.user,
                suggestion_type='new_value',
                target_model='collection_item',
                target_id=item.id,
                field_name='colors',
                current_value='Other',
                proposed_value=colors_other,
            )


class CollectionItemImageForm(forms.ModelForm):
    """One photograph and what it is of — same slots as a listing, so the
    front stays the front when an item goes up for sale."""

    class Meta:
        model = CollectionItemImage
        fields = ['image', 'image_role', 'sort_order']
        widgets = {
            'sort_order': forms.HiddenInput(),
            'image_role': forms.HiddenInput(),
        }

    def has_changed(self):
        """Same rule as the listing rows: a role without a photograph is
        an empty slot, never a row missing its required image."""
        if self.instance.pk:
            return super().has_changed()
        if not (self.files.get(self.add_prefix('image')) or self.data.get(self.add_prefix('image'))):
            return False
        return super().has_changed()


# Five slots drawn on the frame: front, back, and three details.
CollectionItemImageFormSet = forms.inlineformset_factory(
    CollectionItem,
    CollectionItemImage,
    form=CollectionItemImageForm,
    extra=5,
    max_num=12,
    validate_max=True,
    can_delete=True,
)


class CollectionItemTermsForm(forms.ModelForm):
    """Step 3 for the My-collection destination — the collection panel.

    Asks nothing about money publicly and everything about privacy: who
    sees it, whether it sits in the display case, whether you'd trade it,
    and the only-you-ever-see-this block. The folder row waits on
    CollectionFolder (10.14) — until it ships, that row isn't here.
    """

    open_to_trade = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
    )

    class Meta:
        model = CollectionItem
        fields = [
            'is_public',
            'featured',
            'trade_wants',
            'purchase_price',
            'acquired_note',
            'private_note',
        ]
        widgets = {
            'is_public': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'featured': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'trade_wants': forms.TextInput(attrs={'class': 'kb-input', 'placeholder': 'Anything pre-1930 from a county I am missing'}),
            'purchase_price': forms.NumberInput(attrs={'class': 'kb-input', 'step': '0.01', 'min': '0', 'placeholder': '48.00'}),
            'acquired_note': forms.TextInput(attrs={'class': 'kb-input', 'placeholder': 'Mar 2026, Bloomsburg'}),
            'private_note': forms.Textarea(attrs={'class': 'kb-textarea', 'rows': 2, 'placeholder': 'Bought with the 1971. Ask Dale about the overprint.'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.fields['open_to_trade'].initial = self.instance.tradeability == 'open'

    def clean_featured(self):
        featured = self.cleaned_data.get('featured')
        if featured and not self.instance.featured:
            count = CollectionItem.objects.filter(
                owner=self.instance.owner, featured=True,
            ).exclude(pk=self.instance.pk).count()
            if count >= MAX_FEATURED:
                raise forms.ValidationError(
                    f'The display case holds {MAX_FEATURED} — take one out first.'
                )
        return featured

    def save(self, commit=True):
        item = super().save(commit=False)
        item.tradeability = 'open' if self.cleaned_data.get('open_to_trade') else 'closed'
        if commit:
            item.save()
        return item


class WantedItemForm(forms.ModelForm):
    state = forms.ModelChoiceField(queryset=State.objects.none(), required=False, widget=forms.Select(attrs={'class': 'kb-select'}))
    county = forms.ModelChoiceField(queryset=GeographicUnit.objects.none(), required=False, empty_label='Any geographic unit', widget=forms.Select(attrs={'class': 'kb-select'}))
    license_type = forms.ModelChoiceField(queryset=LicenseType.objects.none(), required=False, empty_label='Any type', widget=forms.Select(attrs={'class': 'kb-select'}))

    class Meta:
        model = WantedItem
        fields = ['state', 'county', 'year_min', 'year_max', 'license_type', 'notes']
        widgets = {
            'year_min': forms.NumberInput(attrs={'class': 'kb-input'}),
            'year_max': forms.NumberInput(attrs={'class': 'kb-input'}),
            'notes': forms.TextInput(attrs={'class': 'kb-input', 'maxlength': 250}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['state'].queryset = State.objects.order_by('-is_primary_default', 'name')
        self.fields['state'].label_from_instance = lambda state: state.option_label
        state = self._resolve_state()
        if state:
            self.fields['state'].initial = state
            self.fields['county'].queryset = GeographicUnit.objects.filter(state=state).order_by('sort_order', 'name')
            self.fields['county'].label = state.issuance_unit_label or 'Geographic Unit'
            self.fields['license_type'].queryset = _state_license_type_queryset(state)
        else:
            self.fields['county'].queryset = GeographicUnit.objects.none()
            self.fields['license_type'].queryset = _state_license_type_queryset(None)

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
            state = self.instance.state or getattr(self.instance.county, 'state', None)
        if state is None:
            state = State.objects.filter(is_primary_default=True).first() or State.objects.order_by('name').first()
        return state

    def clean(self):
        cleaned_data = super().clean()
        state = cleaned_data.get('state')
        county = cleaned_data.get('county')
        year_min = cleaned_data.get('year_min')
        year_max = cleaned_data.get('year_max')
        if county and state and county.state_id != state.id:
            self.add_error('county', 'Selected geographic unit does not belong to the chosen state.')
        if year_min and year_max and year_min > year_max:
            self.add_error('year_max', 'Year max must be greater than or equal to year min.')
        return cleaned_data
