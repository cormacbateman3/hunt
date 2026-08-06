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
from apps.collections.models import CollectionItem, CollectionItemImage, WantedItem
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
            'resident_status',
            'condition_grade',
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
            'title': forms.TextInput(attrs={'class': 'kb-input', 'placeholder': 'Written for you from the answers below — edit freely'}),
            'description': forms.Textarea(attrs={'class': 'kb-textarea', 'rows': 4, 'maxlength': 2000, 'placeholder': 'Turkey tag still attached and uncut. Light foxing along the bottom edge, pin intact. Out of an estate lot from Muncy.'}),
            'license_year': forms.NumberInput(attrs={'class': 'kb-input', 'placeholder': '1942 (leave blank if unknown)'}),
            'resident_status': forms.Select(attrs={'class': 'kb-select'}),
            'condition_grade': forms.RadioSelect(attrs={'class': 'chip-radios'}),
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
        # Not required, because a silence must not be read as an answer —
        # see clean_tradeability and clean_disposition.
        self.fields['tradeability'].required = False
        self.fields['disposition'].required = False
        # Chip ladder: the model's grade is optional here, so the quiet way
        # out is a named chip rather than a "---------" radio.
        self.fields['condition_grade'].choices = [('', 'Not set')] + [
            choice for choice in self.fields['condition_grade'].choices if choice[0]
        ]
        # `traded` is the trade lifecycle's record, not a choice anybody
        # makes on a form. It stays selectable only on a piece that already
        # carries it, so editing that piece doesn't force a different answer.
        if not (self.instance.pk and self.instance.disposition == 'traded'):
            self.fields['disposition'].choices = [
                (value, label)
                for value, label in CollectionItem.DISPOSITION_CHOICES
                if value != 'traded'
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
        if state is None:
            state = State.objects.filter(is_primary_default=True).first() or State.objects.order_by('name').first()
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
        state_label = state.name if state else 'This state'
        self.fields['license_year'].help_text = (
            f'{state_label}: {min_year}–{max_year}. Only expired, antique items (25+ years old) '
            'belong here — leave blank if the year is unknown.'
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
        selected_dimensions = [cleaned_data.get(category) for category in FORM_LICENSE_TYPE_CATEGORIES]
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

        # era_label is required when license_year is not provided
        era_label = cleaned_data.get('era_label')
        if year is None and not era_label:
            self.add_error('era_label', 'Era is required when license year is unknown.')

        if not any(selected_dimensions) and not cleaned_data.get('shape') and not (cleaned_data.get('colors') or []):
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
