from django import forms

from .models import Review


class ReviewForm(forms.ModelForm):
    """The review card's two fields.

    The option titles and their describing lines live in
    ``reviews/_review_form.html`` — they change with who is being reviewed,
    which is a rendering fact, not a data one.
    """

    class Meta:
        model = Review
        fields = ['sentiment', 'body']
        widgets = {
            'sentiment': forms.RadioSelect(),
            'body': forms.Textarea(attrs={
                'class': 'kb-textarea',
                'rows': 2,
                'maxlength': 255,
            }),
        }
        labels = {
            'sentiment': 'How was it',
            'body': 'A line about it',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A "---------" radio is not an answer anybody can give.
        self.fields['sentiment'].choices = [
            choice for choice in self.fields['sentiment'].choices if choice[0]
        ]
