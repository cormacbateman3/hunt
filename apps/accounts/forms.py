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
            'class': 'form-input',
            'placeholder': 'your@email.com'
        })
    )
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Username'
        })
    )
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Password'
        })
    )
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Confirm Password'
        })
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('This email address is already in use.')
        return email


class UserLoginForm(AuthenticationForm):
    """Custom login form with styling"""
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Username'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-input',
            'placeholder': 'Password'
        })
    )


class UserProfileForm(forms.ModelForm):
    """Form for editing user profile"""
    class Meta:
        model = UserProfile
        fields = ['display_name', 'bio', 'county', 'avatar']
        widgets = {
            'display_name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Display Name'
            }),
            'bio': forms.Textarea(attrs={
                'class': 'form-input',
                'placeholder': 'Tell us about yourself...',
                'rows': 4
            }),
            'county': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Your Pennsylvania County'
            }),
        }


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
                'class': 'form-input',
                'placeholder': 'Full name'
            }),
            'line1': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Street address'
            }),
            'line2': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Apt, suite, unit (optional)'
            }),
            'city': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'City'
            }),
            'state': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'State (2-letter)',
                'maxlength': 2,
                'style': 'text-transform: uppercase;'
            }),
            'postal_code': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'ZIP code'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-input',
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
        widget=forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '8.0', 'step': '0.5'}),
    )
    package_length_in = forms.DecimalField(
        required=False, min_value=1, max_digits=5, decimal_places=1,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '10', 'step': '0.5'}),
    )
    package_width_in = forms.DecimalField(
        required=False, min_value=1, max_digits=5, decimal_places=1,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '7', 'step': '0.5'}),
    )
    package_height_in = forms.DecimalField(
        required=False, min_value=0.5, max_digits=5, decimal_places=1,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '1', 'step': '0.5'}),
    )
    bid_increment = forms.DecimalField(
        required=False, min_value=1, max_digits=8, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'placeholder': '1', 'step': '1'}),
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
