from decimal import Decimal

from django import forms


class OfferForm(forms.Form):
    """Used for both a buyer's opening offer and a seller's counter."""

    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('1'),
        label='Your offer',
        widget=forms.NumberInput(
            attrs={'class': 'form-input', 'step': '1', 'min': '1', 'placeholder': '75'}
        ),
    )
    message = forms.CharField(
        required=False,
        label='Message (optional)',
        widget=forms.Textarea(
            attrs={
                'class': 'form-input',
                'rows': 3,
                'placeholder': 'Anything the other party should know.',
            }
        ),
    )
    expires_days = forms.IntegerField(
        min_value=1,
        max_value=14,
        initial=2,
        label='Expires in (days)',
        widget=forms.NumberInput(attrs={'class': 'form-input', 'step': '1'}),
    )

    def __init__(self, *args, list_price=None, is_counter=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.list_price = list_price
        self.is_counter = is_counter
        if is_counter:
            self.fields['amount'].label = 'Your counter'
        if list_price is not None:
            self.fields['amount'].widget.attrs['max'] = str(list_price)

    def clean_amount(self):
        amount = self.cleaned_data['amount']
        # Mirrored server-side in services.create_offer; duplicated here only so
        # the user gets a field-level error instead of a page-level message.
        if self.list_price is not None and amount >= self.list_price:
            if self.is_counter:
                raise forms.ValidationError('A counter must be below the list price.')
            raise forms.ValidationError(
                'Your offer must be below the list price — use Buy now to pay the asking price.'
            )
        return amount
