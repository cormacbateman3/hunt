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
    state = forms.ModelChoiceField(queryset=State.objects.none(), required=True, widget=forms.Select(attrs={'class': 'form-select'}))
    county = forms.ModelChoiceField(queryset=GeographicUnit.objects.none(), required=False, empty_label='Select geographic unit', widget=forms.Select(attrs={'class': 'form-select'}))
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
    shape = forms.ChoiceField(choices=[('', 'Select shape')] + SHAPE_CHOICES, required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    shape_other = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter shape'}))
    colors = forms.MultipleChoiceField(choices=COLOR_CHOICES, required=False, widget=forms.CheckboxSelectMultiple(attrs={'class': 'chip-checkboxes'}))
    colors_other = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter color'}))
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
            'shape',
            'colors',
            'resident_status',
            'condition_grade',
            'is_public',
            'trade_eligible',
            'serial_number',
            'era_label',
        ]
        widgets = {
            'item_kind': forms.RadioSelect(),
            'addons_attached': forms.NullBooleanSelect(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g., 1942 Adams County Resident Hunting License'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 4, 'placeholder': 'Condition, notable features, provenance, and any context worth keeping.'}),
            'license_year': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '1942 (leave blank if unknown)'}),
            'resident_status': forms.Select(attrs={'class': 'form-select'}),
            'condition_grade': forms.Select(attrs={'class': 'form-select'}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'trade_eligible': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['state'].queryset = State.objects.order_by('-is_primary_default', 'name')

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
    class Meta:
        model = CollectionItemImage
        fields = ['image', 'sort_order']
        widgets = {
            'sort_order': forms.NumberInput(attrs={'class': 'form-input', 'min': 0}),
        }


CollectionItemImageFormSet = forms.inlineformset_factory(
    CollectionItem,
    CollectionItemImage,
    form=CollectionItemImageForm,
    extra=4,
    max_num=12,
    validate_max=True,
    can_delete=True,
)


class WantedItemForm(forms.ModelForm):
    state = forms.ModelChoiceField(queryset=State.objects.none(), required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    county = forms.ModelChoiceField(queryset=GeographicUnit.objects.none(), required=False, empty_label='Any geographic unit', widget=forms.Select(attrs={'class': 'form-select'}))
    license_type = forms.ModelChoiceField(queryset=LicenseType.objects.none(), required=False, empty_label='Any type', widget=forms.Select(attrs={'class': 'form-select'}))

    class Meta:
        model = WantedItem
        fields = ['state', 'county', 'year_min', 'year_max', 'license_type', 'notes']
        widgets = {
            'year_min': forms.NumberInput(attrs={'class': 'form-input'}),
            'year_max': forms.NumberInput(attrs={'class': 'form-input'}),
            'notes': forms.TextInput(attrs={'class': 'form-input', 'maxlength': 250}),
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
