from django import forms
from django.utils import timezone
from datetime import timedelta
from .models import Listing, ListingImage
from apps.core.models import County, LicenseType


class ListingForm(forms.ModelForm):
    """Form for creating and editing listings across all listing types"""

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
        self.fields['duration_days'].required = False

        if self.instance and self.instance.pk:
            self.fields['duration_days'].initial = 7

    class Meta:
        model = Listing
        fields = [
            'listing_type',
            'title',
            'description',
            'license_year',
            'county_ref',
            'license_type_ref',
            'condition_grade',
            'starting_price',
            'reserve_price',
            'buy_now_price',
            'trade_notes',
            'allow_cash',
            'featured_image',
        ]
        widgets = {
            'listing_type': forms.Select(attrs={'class': 'form-select'}),
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
            'reserve_price': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': 'Optional reserve',
                'step': '0.01',
                'min': '0.01'
            }),
            'buy_now_price': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': '75.00',
                'step': '0.01',
                'min': '0.01'
            }),
            'trade_notes': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 4,
                'placeholder': 'What are you looking for in return?',
            }),
            'allow_cash': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        listing_type = cleaned_data.get('listing_type')
        starting_price = cleaned_data.get('starting_price')
        reserve_price = cleaned_data.get('reserve_price')
        buy_now_price = cleaned_data.get('buy_now_price')
        trade_notes = (cleaned_data.get('trade_notes') or '').strip()
        duration_days = cleaned_data.get('duration_days')

        if listing_type == 'auction':
            if starting_price is None:
                self.add_error('starting_price', 'Starting price is required for auctions.')
            if not duration_days:
                self.add_error('duration_days', 'Duration is required for auctions.')
            if reserve_price and starting_price and reserve_price < starting_price:
                self.add_error('reserve_price', 'Reserve price must be at least the starting price.')
        elif listing_type == 'buy_now':
            if buy_now_price is None:
                self.add_error('buy_now_price', 'Buy now price is required for General Store listings.')
        elif listing_type == 'trade':
            if not trade_notes:
                self.add_error('trade_notes', 'Trade preferences are required for Trading Block listings.')

        return cleaned_data

    def save(self, commit=True):
        listing = super().save(commit=False)

        # Keep legacy text fields populated while moving to FK selectors.
        if listing.county_ref:
            listing.county = listing.county_ref.name
        if listing.license_type_ref:
            listing.license_type = listing.license_type_ref.name

        listing_type = self.cleaned_data['listing_type']
        duration = self.cleaned_data.get('duration_days')

        if listing_type == 'auction':
            listing.auction_end = timezone.now() + timedelta(days=int(duration))
            listing.buy_now_price = None
            listing.trade_notes = ''
            listing.allow_cash = False
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
