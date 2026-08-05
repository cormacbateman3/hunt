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
    # **A box on each side, not one box and a switch.** Cash is part of what
    # sits on that half of the table, so it is typed where it lands. The
    # direction falls out of which box has a figure in it, which is one less
    # thing to get wrong than a radio somewhere else on the page.
    cash_i_add = forms.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal('0.00'),
        required=False,
        widget=forms.NumberInput(attrs={'class': 'tb-cash-input', 'step': '0.01',
                                        'min': '0', 'placeholder': '0.00'}),
    )
    cash_to_me = forms.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal('0.00'),
        required=False,
        widget=forms.NumberInput(attrs={'class': 'tb-cash-input', 'step': '0.01',
                                        'min': '0', 'placeholder': '0.00'}),
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
            for name in ('cash_i_add', 'cash_to_me'):
                self.fields[name].widget = forms.HiddenInput()

    def clean(self):
        cleaned = super().clean()
        mine = cleaned.get('cash_i_add') or Decimal('0.00')
        theirs = cleaned.get('cash_to_me') or Decimal('0.00')

        if mine and theirs:
            # Money cannot run both ways at once, and quietly netting it off
            # would answer a question the proposer did not mean to ask.
            raise forms.ValidationError(
                'Cash runs one way. Put a figure in one box and leave the '
                'other empty.')
        if not self.allow_cash and (mine or theirs):
            # Not a field error: the seller turned cash off, so there is no
            # control on the page for the proposer to have got wrong.
            raise forms.ValidationError(
                'This listing does not allow cash on top of the licences.')

        cleaned['cash_amount'] = mine or theirs
        cleaned['cash_direction'] = 'to_proposer' if theirs else 'from_proposer'
        return cleaned


class TradeOfferActionForm(forms.Form):
    action = forms.ChoiceField(
        choices=TradeOffer.STATUS_CHOICES,
        widget=forms.HiddenInput,
    )
