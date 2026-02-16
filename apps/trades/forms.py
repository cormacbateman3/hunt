from decimal import Decimal
from django import forms
from .models import TradeOffer


class TradeOfferForm(forms.Form):
    offered_items = forms.ModelMultipleChoiceField(
        queryset=None,
        required=True,
        widget=forms.CheckboxSelectMultiple,
        help_text='Select one or more trade-eligible items from your collection.',
    )
    cash_amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.00'),
        required=False,
        initial=Decimal('0.00'),
        widget=forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01', 'min': '0'}),
    )
    expires_days = forms.IntegerField(
        min_value=1,
        max_value=14,
        initial=4,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'min': 1, 'max': 14}),
        help_text='Offer expiration window in days (default 4).',
    )
    message = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-input', 'rows': 4}),
    )

    def __init__(self, *args, offered_queryset=None, allow_cash=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['offered_items'].queryset = offered_queryset
        if not allow_cash:
            self.fields['cash_amount'].widget = forms.HiddenInput()
            self.fields['cash_amount'].required = False
            self.fields['cash_amount'].initial = Decimal('0.00')


class TradeOfferActionForm(forms.Form):
    action = forms.ChoiceField(
        choices=TradeOffer.STATUS_CHOICES,
        widget=forms.HiddenInput,
    )
