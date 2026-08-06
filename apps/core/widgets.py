from django import forms


class TagsStillAttachedSelect(forms.NullBooleanSelect):
    """The three honest answers to "Tags still attached?" (turn 6b).

    Django's stock labels — Unknown / Yes / No — read like a database
    talking. The value contract is unchanged; only the words are ours.
    """

    def __init__(self, attrs=None):
        super().__init__(attrs)
        self.choices = [
            ('unknown', 'Not sure'),
            ('true', 'Yes, uncut'),
            ('false', 'No — cut or detached'),
        ]
