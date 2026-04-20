from django import template

register = template.Library()


@register.filter
def bound_field(form, field_name):
    """Return the bound field for a dynamic field name: form|bound_field:field_name"""
    return form[field_name]
