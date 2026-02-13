from django import forms
from .models import Bid


class BidForm(forms.ModelForm):
    """Form for placing a bid"""

    class Meta:
        model = Bid
        fields = ['amount']
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter bid amount',
                'step': '0.01',
                'min': '0.01'
            })
        }

    def __init__(self, *args, **kwargs):
        self.listing = kwargs.pop('listing', None)
        self.bidder = kwargs.pop('bidder', None)
        super().__init__(*args, **kwargs)

    def clean_amount(self):
        amount = self.cleaned_data['amount']

        if not self.listing:
            raise forms.ValidationError("Listing is required")

        # Get minimum bid (current bid + 1, or starting price)
        minimum_bid = (self.listing.current_bid or self.listing.starting_price) + 1

        if amount < minimum_bid:
            raise forms.ValidationError(
                f"Bid must be at least ${minimum_bid:.2f}"
            )

        return amount

    def clean(self):
        cleaned_data = super().clean()

        # Check if user is the seller
        if self.bidder and self.listing and self.bidder == self.listing.seller:
            raise forms.ValidationError("You cannot bid on your own listing")

        # Check if user's email is verified
        if self.bidder and not self.bidder.profile.email_verified:
            raise forms.ValidationError("You must verify your email before bidding")

        # Check if listing is still active
        if self.listing and not self.listing.is_active():
            raise forms.ValidationError("This auction has ended")

        return cleaned_data
