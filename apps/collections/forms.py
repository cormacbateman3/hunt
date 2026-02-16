from django import forms
from apps.core.models import County, LicenseType
from .models import CollectionItem, CollectionItemImage, WantedItem


class CollectionItemForm(forms.ModelForm):
    county = forms.ModelChoiceField(
        queryset=County.objects.none(),
        required=False,
        empty_label='Select county',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    license_type = forms.ModelChoiceField(
        queryset=LicenseType.objects.none(),
        required=False,
        empty_label='Select license type',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta:
        model = CollectionItem
        fields = [
            'title',
            'description',
            'license_year',
            'county',
            'license_type',
            'resident_status',
            'condition_grade',
            'is_public',
            'trade_eligible',
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 4}),
            'license_year': forms.NumberInput(attrs={'class': 'form-input'}),
            'resident_status': forms.Select(attrs={'class': 'form-select'}),
            'condition_grade': forms.Select(attrs={'class': 'form-select'}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'trade_eligible': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['county'].queryset = County.objects.order_by('name')
        self.fields['license_type'].queryset = LicenseType.objects.order_by('name')


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
    county = forms.ModelChoiceField(
        queryset=County.objects.none(),
        required=False,
        empty_label='Any county',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    license_type = forms.ModelChoiceField(
        queryset=LicenseType.objects.none(),
        required=False,
        empty_label='Any type',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta:
        model = WantedItem
        fields = ['county', 'year_min', 'year_max', 'license_type', 'notes']
        widgets = {
            'year_min': forms.NumberInput(attrs={'class': 'form-input'}),
            'year_max': forms.NumberInput(attrs={'class': 'form-input'}),
            'notes': forms.TextInput(attrs={'class': 'form-input', 'maxlength': 250}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['county'].queryset = County.objects.order_by('name')
        self.fields['license_type'].queryset = LicenseType.objects.order_by('name')

    def clean(self):
        cleaned_data = super().clean()
        year_min = cleaned_data.get('year_min')
        year_max = cleaned_data.get('year_max')
        if year_min and year_max and year_min > year_max:
            self.add_error('year_max', 'Year max must be greater than or equal to year min.')
        return cleaned_data
