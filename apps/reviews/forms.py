from django import forms
from .models import Review


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['sentiment', 'body']
        widgets = {
            'sentiment': forms.RadioSelect(),
            'body': forms.Textarea(attrs={
                'class': 'form-input',
                'rows': 3,
                'maxlength': 255,
                'placeholder': 'Optional — describe your experience (max 255 characters).',
            }),
        }
        labels = {
            'sentiment': 'Rating',
            'body': 'Comments (optional)',
        }
