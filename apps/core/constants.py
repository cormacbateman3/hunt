RESIDENT_STATUS_CHOICES = [
    ('resident', 'Resident'),
    ('non_resident', 'Non-Resident'),
    ('unknown', 'Unknown'),
]

LICENSE_TYPE_CATEGORY_CHOICES = [
    ('residency', 'Residency'),
    ('holder_eligibility', 'Holder Eligibility'),
    ('activity_scope', 'Activity Scope'),
    ('duration', 'Duration'),
    ('addon_type', 'Add-on Type'),
    ('material', 'Physical Form / Material'),
    ('shape', 'Shape'),
    ('colors', 'Color(s)'),
]

FORM_LICENSE_TYPE_CATEGORIES = [
    'residency',
    'holder_eligibility',
    'activity_scope',
    'duration',
    'addon_type',
    'material',
]

SHAPE_CHOICES = [
    ('rectangle', 'Rectangle'),
    ('square', 'Square'),
    ('button_disc', 'Button/Disc'),
    ('tag_with_hole', 'Tag (with hole)'),
    ('strip', 'Strip'),
    ('irregular_custom', 'Irregular/Custom'),
    ('other', 'Other'),
]

COLOR_CHOICES = [
    ('orange', 'Orange'),
    ('yellow', 'Yellow'),
    ('red', 'Red'),
    ('crimson_dark_red', 'Crimson/Dark Red'),
    ('forest_green', 'Forest Green'),
    ('lime_bright_green', 'Lime/Bright Green'),
    ('blue', 'Blue'),
    ('navy', 'Navy'),
    ('white', 'White'),
    ('cream_ivory', 'Cream/Ivory'),
    ('gray', 'Gray'),
    ('silver', 'Silver'),
    ('brown_tan', 'Brown/Tan'),
    ('gold', 'Gold'),
    ('pink', 'Pink'),
    ('purple', 'Purple'),
    ('black', 'Black'),
    ('multi_color', 'Multi-color'),
    ('other', 'Other'),
]

SUGGESTION_TYPE_CHOICES = [
    ('new_value', 'New Value'),
    ('correction', 'Correction'),
    ('other', 'Other'),
]

SUGGESTION_TARGET_MODEL_CHOICES = [
    ('state', 'State'),
    ('geographic_unit', 'Geographic Unit'),
    ('license_type', 'License Type'),
    ('listing', 'Listing'),
    ('collection_item', 'Collection Item'),
    ('other', 'Other'),
]

SUGGESTION_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('accepted', 'Accepted'),
    ('rejected', 'Rejected'),
]

