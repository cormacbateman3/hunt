from django import template

from apps.accounts.identity import initials_for, short_name

register = template.Library()


@register.filter
def bound_field(form, field_name):
    """Return the bound field for a dynamic field name: form|bound_field:field_name"""
    return form[field_name]


@register.filter
def initials(user):
    """Two letters for an avatar square: user|initials."""
    return initials_for(user)


@register.filter
def byline_name(user):
    """The byline short form ("M. Yoder"): user|byline_name."""
    return short_name(user)
