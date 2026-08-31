from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User

from apps.core.constants import SHIPPING_PAYER_CHOICES, SHIPPING_SERVICE_CHOICES
from .models import UserProfile, Address


class UserRegistrationForm(UserCreationForm):
    """Custom user registration form with email verification"""
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'kb-input',
            'placeholder': 'your@email.com'
        })
    )
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'kb-input',
            'placeholder': 'Username'
        })
    )
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'kb-input',
            'placeholder': 'Password'
        })
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'kb-input',
            'placeholder': 'Confirm Password'
        })
    )

    # 10.21: home state is the one thing the whole site personalises on —
    # every filter and fresh form opens there — so joining asks for it.
    # The county does not belong here: it prefills nothing, and a shorter
    # door matters more than a fuller profile.
    home_state = forms.ModelChoiceField(
        queryset=None,
        label='Home state',
        empty_label='Choose your state',
        error_messages={'required': 'Say which state is home — the site opens on it.'},
        widget=forms.Select(attrs={'class': 'kb-input'}),
    )

    accept_terms = forms.BooleanField(
        required=True,
        error_messages={'required': 'You have to accept the rules to join.'},
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.core.models import State, TermsVersion

        # Alphabetical and by plain name: a new member is scanning for the
        # one state they live in, not reading unit vocabularies. Federal is
        # a pseudo-state for duck stamps, not a place anybody lives.
        self.fields['home_state'].queryset = (
            State.objects.exclude(code='FD').order_by('name'))
        self.fields['home_state'].label_from_instance = lambda state: state.name

        # Acceptance is recorded against a version, so there has to be one.
        # If nothing is published the checkbox is not shown at all rather
        # than asking somebody to agree to a document that does not exist.
        self.terms = TermsVersion.current()
        if self.terms:
            self.fields['accept_terms'].label = (
                f'I’ve read the Marketplace Rules and Terms, version '
                f'{self.terms.version}.'
            )
        else:
            del self.fields['accept_terms']

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            # The profile row already exists — the post_save signal made it.
            profile = user.profile
            profile.home_state = self.cleaned_data['home_state']
            profile.save(update_fields=['home_state'])
            if self.terms:
                from apps.core.models import TermsAcceptance
                TermsAcceptance.objects.get_or_create(
                    user=user, terms=self.terms,
                    defaults={'context': 'registration'})
        return user

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('This email address is already in use.')
        return email


class UserLoginForm(AuthenticationForm):
    """Custom login form with styling"""
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'kb-input',
            'placeholder': 'Username'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'kb-input',
            'placeholder': 'Password'
        })
    )


class UserProfileForm(forms.ModelForm):
    """Profile & display — how you appear to other collectors.

    The county is picked from the same unit list the listings use, so a
    profile can never disagree with a listing about what a county is called.
    """

    class Meta:
        model = UserProfile
        fields = ['display_name', 'home_state', 'home_county', 'bio',
                  'avatar', 'showcase_layout']
        labels = {
            'home_state': 'State',
            'home_county': 'Home county',
            'bio': 'A few lines about your collecting',
            'showcase_layout': 'How your profile is laid out',
        }
        help_texts = {
            'display_name': 'Leave it blank and we’ll show your username.',
            'bio': 'What you collect and what you’re after — that’s what other '
                   'collectors read this for.',
        }
        widgets = {
            'display_name': forms.TextInput(attrs={
                'class': 'kb-input', 'placeholder': 'Ray Miller',
            }),
            'home_state': forms.Select(attrs={'class': 'form-select'}),
            'home_county': forms.Select(attrs={'class': 'form-select'}),
            'bio': forms.Textarea(attrs={
                'class': 'kb-input', 'rows': 4, 'maxlength': 400,
                'placeholder': 'Chasing a full run of numbered county tags, '
                               '1913 to 1937. Twenty-six counties to go.',
            }),
            'showcase_layout': forms.RadioSelect(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.core.models import GeographicUnit, State

        self.fields['home_state'].queryset = State.objects.order_by(
            '-is_primary_default', 'name')
        self.fields['home_state'].empty_label = 'Not saying'

        # Only offer units inside the chosen state; offering all of them is
        # how "Towson, MD, PA" happens.
        state_id = (
            self.data.get('home_state')
            or (self.instance.home_state_id if self.instance.pk else None)
        )
        units = GeographicUnit.objects.none()
        if state_id:
            units = GeographicUnit.objects.filter(
                state_id=state_id).order_by('sort_order', 'name')
        self.fields['home_county'].queryset = units
        self.fields['home_county'].empty_label = 'Not saying'
        self.fields['home_county'].required = False

        unit_label = 'County'
        if state_id:
            state = State.objects.filter(pk=state_id).first()
            if state and state.issuance_unit_label:
                unit_label = state.issuance_unit_label
        self.fields['home_county'].label = f'Home {unit_label.lower()}'

    def clean(self):
        cleaned = super().clean()
        state = cleaned.get('home_state')
        county = cleaned.get('home_county')
        if county and state and county.state_id != state.id:
            self.add_error(
                'home_county',
                f'{county.name} is not in {state.name}. Pick one from the list.')
        if county and not state:
            cleaned['home_state'] = county.state
        return cleaned


class AddressForm(forms.ModelForm):
    """Form for adding/editing a shipping address"""

    def clean_state(self):
        state = (self.cleaned_data.get('state') or '').strip().upper()
        if len(state) != 2 or not state.isalpha():
            raise forms.ValidationError('Use the two-letter state abbreviation (e.g. PA, MD).')
        return state

    def clean_postal_code(self):
        import re
        postal_code = (self.cleaned_data.get('postal_code') or '').strip()
        if not re.fullmatch(r'\d{5}(-\d{4})?', postal_code):
            raise forms.ValidationError('Enter a 5-digit ZIP code (or ZIP+4).')
        return postal_code

    class Meta:
        model = Address
        fields = ['full_name', 'line1', 'line2', 'city', 'state', 'postal_code', 'phone']
        widgets = {
            'full_name': forms.TextInput(attrs={
                'class': 'kb-input',
                'placeholder': 'Full name'
            }),
            'line1': forms.TextInput(attrs={
                'class': 'kb-input',
                'placeholder': 'Street address'
            }),
            'line2': forms.TextInput(attrs={
                'class': 'kb-input',
                'placeholder': 'Apt, suite, unit (optional)'
            }),
            'city': forms.TextInput(attrs={
                'class': 'kb-input',
                'placeholder': 'City'
            }),
            'state': forms.TextInput(attrs={
                'class': 'kb-input',
                'placeholder': 'State (2-letter)',
                'maxlength': 2,
                'style': 'text-transform: uppercase;'
            }),
            'postal_code': forms.TextInput(attrs={
                'class': 'kb-input',
                'placeholder': 'ZIP code'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'kb-input',
                'placeholder': 'Phone (optional)'
            }),
        }


class ListingDefaultsForm(forms.Form):
    """Saved defaults applied to new listings (10.8) — stored on
    UserProfile.listing_defaults and read by ListingForm on create."""

    shipping_service = forms.ChoiceField(
        choices=SHIPPING_SERVICE_CHOICES, required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    shipping_payer = forms.ChoiceField(
        choices=SHIPPING_PAYER_CHOICES, required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    package_weight_oz = forms.DecimalField(
        required=False, min_value=0.5, max_digits=6, decimal_places=1,
        widget=forms.NumberInput(attrs={'class': 'kb-input', 'placeholder': '8.0', 'step': '0.5'}),
    )
    package_length_in = forms.DecimalField(
        required=False, min_value=1, max_digits=5, decimal_places=1,
        widget=forms.NumberInput(attrs={'class': 'kb-input', 'placeholder': '10', 'step': '0.5'}),
    )
    package_width_in = forms.DecimalField(
        required=False, min_value=1, max_digits=5, decimal_places=1,
        widget=forms.NumberInput(attrs={'class': 'kb-input', 'placeholder': '7', 'step': '0.5'}),
    )
    package_height_in = forms.DecimalField(
        required=False, min_value=0.5, max_digits=5, decimal_places=1,
        widget=forms.NumberInput(attrs={'class': 'kb-input', 'placeholder': '1', 'step': '0.5'}),
    )
    bid_increment = forms.DecimalField(
        required=False, min_value=1, max_digits=8, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'kb-input', 'placeholder': '1', 'step': '1'}),
    )
    auto_relist = forms.BooleanField(
        required=False, widget=forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
    )

    def to_defaults(self):
        """JSON-safe dict, empties dropped (booleans always kept)."""
        out = {}
        for key, value in self.cleaned_data.items():
            if isinstance(value, bool):
                out[key] = value
            elif value not in (None, ''):
                out[key] = str(value)
        return out
