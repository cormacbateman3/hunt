from decimal import Decimal
from django import forms
from .models import TradeOffer


class TradeOfferForm(forms.Form):
    """What goes on the table, from both sides of it.

    The two item fields are hidden multi-selects: the picking happens in the
    rosters either side of the dark panel, which post one input per piece.
    Server-side validation stays authoritative — ownership, availability and
    cash rules are all re-checked in ``create_trade_offer``, because a hidden
    input is a suggestion.
    """

    # Not required at this layer: when you are the one being asked for a
    # licence, the piece under negotiation is already yours to give and it
    # has no checkbox — it is fixed on the table. The service decides whether
    # the table has enough on it, after the subject is placed.
    offered_items = forms.ModelMultipleChoiceField(
        queryset=None,
        required=False,
        widget=forms.MultipleHiddenInput,
        help_text='Pieces of yours going on the table.',
    )
    requested_items = forms.ModelMultipleChoiceField(
        queryset=None,
        required=False,
        widget=forms.MultipleHiddenInput,
        help_text='Pieces of theirs you are asking for.',
    )
    cash_amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.00'),
        required=False,
        initial=Decimal('0.00'),
        widget=forms.NumberInput(attrs={'class': 'kb-input', 'step': '0.01', 'min': '0'}),
    )
    cash_direction = forms.ChoiceField(
        choices=TradeOffer.CASH_DIRECTION_CHOICES,
        required=False,
        initial='from_proposer',
        widget=forms.RadioSelect,
    )
    expires_days = forms.IntegerField(
        min_value=1,
        max_value=14,
        initial=4,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'kb-input', 'min': 1, 'max': 14}),
        help_text='How long they have to answer. Four days by default.',
    )
    message = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'kb-input', 'rows': 3,
                                     'placeholder': 'Say something about the pieces…'}),
    )

    def __init__(self, *args, offered_queryset=None, requested_queryset=None,
                 allow_cash=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.allow_cash = allow_cash
        self.fields['offered_items'].queryset = offered_queryset
        self.fields['requested_items'].queryset = requested_queryset
        if not allow_cash:
            self.fields['cash_amount'].widget = forms.HiddenInput()
            self.fields['cash_amount'].required = False
            self.fields['cash_amount'].initial = Decimal('0.00')

    def clean_cash_direction(self):
        return self.cleaned_data.get('cash_direction') or 'from_proposer'

    def clean(self):
        cleaned = super().clean()
        if not self.allow_cash and cleaned.get('cash_amount'):
            # Not a field error: the seller turned cash off, so there is no
            # control on the page for the proposer to have got wrong.
            raise forms.ValidationError(
                'This listing does not allow cash on top of the licences.')
        return cleaned


class TradeOfferActionForm(forms.Form):
    action = forms.ChoiceField(
        choices=TradeOffer.STATUS_CHOICES,
        widget=forms.HiddenInput,
    )
