from django import forms
from django.utils import timezone
from datetime import timedelta
from .models import Listing, ListingImage
from apps.core.models import County, LicenseType


class ListingForm(forms.ModelForm):
    """Form for creating and editing auction listings"""

    duration_days = forms.ChoiceField(
        choices=[
            (1, '1 day'),
            (3, '3 days'),
            (5, '5 days'),
            (7, '7 days'),
            (10, '10 days'),
        ],
        initial=7,
        help_text="How long should the auction run?",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    county_ref = forms.ModelChoiceField(
        queryset=County.objects.none(),
        required=True,
        empty_label='Select county',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    license_type_ref = forms.ModelChoiceField(
        queryset=LicenseType.objects.none(),
        required=True,
        empty_label='Select license type',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['county_ref'].queryset = County.objects.order_by('name')
        self.fields['license_type_ref'].queryset = LicenseType.objects.order_by('name')

    class Meta:
        model = Listing
        fields = [
            'title', 'description', 'license_year', 'county_ref', 'license_type_ref',
            'condition_grade', 'starting_price', 'featured_image'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g., 1942 Adams County Resident Hunting License'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-input',
                'placeholder': 'Describe the license condition, any notable features, provenance...',
                'rows': 6
            }),
            'license_year': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': '1942',
                'min': '1913',
                'max': '2000'
            }),
            'condition_grade': forms.Select(attrs={
                'class': 'form-select'
            }),
            'starting_price': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': '25.00',
                'step': '0.01',
                'min': '0.01'
            }),
        }

    def save(self, commit=True):
        listing = super().save(commit=False)

        # Keep legacy text fields populated while moving to FK selectors.
        if listing.county_ref:
            listing.county = listing.county_ref.name
        if listing.license_type_ref:
            listing.license_type = listing.license_type_ref.name

        # Calculate auction_end based on duration_days
        duration = int(self.cleaned_data['duration_days'])
        listing.auction_end = timezone.now() + timedelta(days=duration)

        if commit:
            listing.save()
        return listing


class ListingImageForm(forms.ModelForm):
    """Form for uploading additional listing images"""

    class Meta:
        model = ListingImage
        fields = ['image', 'sort_order']
        widgets = {
            'sort_order': forms.HiddenInput(),
        }


# Formset for multiple image uploads
ListingImageFormSet = forms.inlineformset_factory(
    Listing,
    ListingImage,
    form=ListingImageForm,
    extra=4,
    max_num=4,
    validate_max=True,
    can_delete=True
)
