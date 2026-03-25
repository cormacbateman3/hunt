from django import forms

from apps.core.models import ReferenceDataSuggestion


class ReferenceDataSuggestionForm(forms.ModelForm):
    next = forms.CharField(widget=forms.HiddenInput(), required=False)

    class Meta:
        model = ReferenceDataSuggestion
        fields = [
            'suggestion_type',
            'target_model',
            'target_id',
            'field_name',
            'current_value',
            'proposed_value',
            'source_or_evidence',
            'next',
        ]
        widgets = {
            'suggestion_type': forms.Select(attrs={'class': 'form-select'}),
            'target_model': forms.Select(attrs={'class': 'form-select'}),
            'target_id': forms.HiddenInput(),
            'field_name': forms.TextInput(attrs={'class': 'form-input'}),
            'current_value': forms.Textarea(attrs={'class': 'form-input', 'rows': 2}),
            'proposed_value': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'source_or_evidence': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
        }
