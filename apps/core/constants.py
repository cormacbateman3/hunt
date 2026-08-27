# Floor for license years when a state has no researched min_license_year
# (matches the prefill resolver's fallback).
ABSOLUTE_MIN_LICENSE_YEAR = 1850

RESIDENT_STATUS_CHOICES = [
    ('resident', 'Resident'),
    ('non_resident', 'Non-Resident'),
    ('unknown', 'Unknown'),
]

ITEM_KIND_CHOICES = [
    ('license', 'License'),
    ('addon', 'Add-on / Stamp / Tag'),
]

INSTRUMENT_CHOICES = [
    ('stamp', 'Stamp'),
    ('tag', 'Tag'),
    ('permit', 'Permit'),
    ('license', 'License'),
    ('fee', 'Fee'),
    ('certification', 'Certification'),
]

# Values are Shippo servicelevel tokens (except 'cheapest', which means
# "pick the lowest rate returned").
SHIPPING_SERVICE_CHOICES = [
    ('cheapest', 'Best available (cheapest rate)'),
    ('usps_ground_advantage', 'USPS Ground Advantage'),
    ('usps_priority', 'USPS Priority Mail'),
    ('ups_ground', 'UPS Ground'),
    ('fedex_ground', 'FedEx Ground'),
    ('fedex_2_day', 'FedEx 2-Day'),
]

SHIPPING_PAYER_CHOICES = [
    ('buyer', 'Buyer pays shipping'),
    ('seller', 'Seller pays (free shipping)'),
]

LICENSE_TYPE_CATEGORY_CHOICES = [
    ('residency', 'Residency'),
    ('holder_eligibility', 'Holder Eligibility'),
    ('activity_scope', 'Activity Scope'),
    ('duration', 'Duration'),
    ('addon_type', 'Add-on Type'),
    ('material', 'Physical Form / Material'),
    # A property of the issue, not an attachment — a Special Issue turkey tag
    # is both, which is why this is its own category rather than an addon_type
    # value (Pass 8b; the reasoning lives in plan_design.md's inbox).
    ('issue_class', 'Issue Class'),
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
    'issue_class',
]

# The same categories, asked the way a person would ask them. Nobody
# outside this codebase knows what holder_eligibility or activity_scope mean,
# so no filter should say them out loud. Browse UI uses these; the admin and
# the model keep the schema names, which is where they belong.
LICENSE_TYPE_CATEGORY_QUESTIONS = {
    'residency': 'Residency',
    'holder_eligibility': 'Who could hold it',
    'activity_scope': 'What it covered',
    'duration': 'How long',
    'addon_type': 'Attachments',
    'material': 'Material',
    'issue_class': 'Issue class',
}

# The same categories again, labelled the way the item form asks them —
# turn 6b writes the labels out on the drawing ("Who it was for", "What it
# allowed"), and both the listing and collection forms read from here so the
# two can never drift.
FORM_TAXONOMY_FIELDS = [
    ('residency', 'residency_other', 'Residency'),
    ('holder_eligibility', 'holder_eligibility_other', 'Who it was for'),
    ('activity_scope', 'activity_scope_other', 'What it allowed'),
    ('duration', 'duration_other', 'How long it lasted'),
    ('addon_type', 'addon_type_other', 'Tags or stamps on it'),
    ('material', 'material_other', 'What it’s made of'),
    ('issue_class', 'issue_class_other', 'Issue class'),
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
    ('burgundy', 'Burgundy/Maroon'),
    ('forest_green', 'Forest Green'),
    ('olive', 'Olive/Drab'),
    ('lime_bright_green', 'Lime/Bright Green'),
    ('teal', 'Teal'),
    ('blue', 'Blue'),
    ('navy', 'Navy'),
    ('white', 'White'),
    ('cream_ivory', 'Cream/Ivory'),
    ('gray', 'Gray'),
    ('silver', 'Silver'),
    ('copper_bronze', 'Copper/Bronze'),
    ('brown_tan', 'Brown/Tan'),
    ('gold', 'Gold'),
    ('pink', 'Pink'),
    ('purple', 'Purple'),
    ('black', 'Black'),
    ('multi_color', 'Multi-color'),
    ('other', 'Other'),
]

# Interim improved grades (10.8) ahead of the future grading model.
# Old keys stay valid — existing rows keep their values.
CONDITION_CHOICES = [
    ('damaged', 'Damaged'),
    ('poor', 'Poor'),
    ('fair', 'Fair'),
    ('good', 'Good'),
    ('very_good', 'Very good'),
    ('excellent', 'Excellent'),
    ('near_mint', 'Near mint'),
    ('mint', 'Mint'),
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

