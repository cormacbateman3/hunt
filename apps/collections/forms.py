from django import forms
from apps.core.models import County, LicenseType
from .models import CollectionItem


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
