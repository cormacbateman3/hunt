from django import forms
from django.utils import timezone
from datetime import timedelta
from .models import Listing, ListingImage


class ListingForm(forms.ModelForm):
    """Form for creating and editing auction listings"""

    duration_days = forms.ChoiceField(
        choices=[
            (1, '1 days'),
            (3, '3 days'),
            (5, '5 days'),
            (7, '7 days'),
            (10, '10 days'),
        ],
        initial=7,
        help_text="How long should the auction run?"
    )

    class Meta:
        model = Listing
        fields = [
            'title', 'description', 'license_year', 'county', 'license_type',
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
                'min': '1900',
                'max': '2000'
            }),
            'county': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Adams'
            }),
            'license_type': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Resident'
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
    can_delete=True
)
