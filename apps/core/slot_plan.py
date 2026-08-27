"""The photograph slot plan, drawn server-side for the step-2 pages.

Both item forms (listing and collection) hang five named slots over a
plain image formset: front, back, three details. The template needs to
know which formset row backs which slot, what thumbnail it already holds,
and whether that image is saved on the record (existing) or merely held
through a failed submit (kept, via apps.core.upload_stash).

A static row→slot map only works on an empty form. On a saved record the
initial rows arrive in model order regardless of role, so "the back slot"
must mean *the row whose role is back* — wiring it to row 0 would relabel
a detail photograph the moment the form saved.
"""


def photo_slots(image_formset, kept=None, front_input_id=None, front_existing_url=None):
    """Return (slots_cfg, slot_view).

    ``slots_cfg`` is the KBItemForm wiring (selectors per slot);
    ``slot_view`` is what the template paints (thumb/existing/kept per
    slot, plus a filled count).

    ``front_input_id``: the id of a separate front input (the listing
    form's ``featured_image``), with ``front_existing_url`` the saved
    image's url when the record already carries one. When None, the front
    is a formset row of role ``front`` (the collection form).
    """
    kept = kept or {}
    prefix = image_formset.prefix

    def cfg(i):
        if i is None:
            return None
        return {'input': f'#id_{prefix}-{i}-image', 'role': f'#id_{prefix}-{i}-image_role',
                'sort': f'#id_{prefix}-{i}-sort_order', 'del': f'#id_{prefix}-{i}-DELETE'}

    forms_list = list(image_formset.forms)
    initial_count = image_formset.initial_form_count()

    def by_role(role):
        return next((i for i in range(initial_count)
                     if forms_list[i].instance.image_role == role), None)

    front_idx = None if front_input_id else by_role('front')
    back_idx = by_role('back')
    detail_idxs = [i for i in range(initial_count)
                   if forms_list[i].instance.image_role == 'detail'
                   and i not in (front_idx, back_idx)]
    taken = {front_idx, back_idx, *detail_idxs}
    free = [i for i in range(len(forms_list)) if i >= initial_count and i not in taken]
    if front_input_id is None and front_idx is None and free:
        front_idx = free.pop(0)
    if back_idx is None and free:
        back_idx = free.pop(0)
    while len(detail_idxs) < 3 and free:
        detail_idxs.append(free.pop(0))
    detail_idxs = detail_idxs[:3]

    def view_of(i, kept_field):
        existing = (i is not None and i < initial_count
                    and bool(forms_list[i].instance.image))
        thumb = forms_list[i].instance.image.url if existing else kept.get(kept_field or '')
        return {
            'existing': existing,
            'kept': (kept_field if (not existing and kept_field in kept) else ''),
            'thumb': thumb or '',
        }

    def field_of(i):
        return f'{prefix}-{i}-image' if i is not None else None

    slot_view = {
        'back': view_of(back_idx, field_of(back_idx)),
        'details': [view_of(i, field_of(i)) for i in detail_idxs],
    }
    slots_cfg = {
        'back': cfg(back_idx),
        'details': [cfg(i) for i in detail_idxs],
    }
    if front_input_id:
        slots_cfg['front'] = {'input': f'#{front_input_id}'}
        slot_view['front'] = {
            'existing': bool(front_existing_url),
            'kept': ('featured_image'
                     if (not front_existing_url and 'featured_image' in kept) else ''),
            'thumb': front_existing_url or kept.get('featured_image', ''),
        }
    else:
        slots_cfg['front'] = cfg(front_idx)
        slot_view['front'] = view_of(front_idx, field_of(front_idx))

    slot_view['count'] = sum(
        1 for s in [slot_view['front'], slot_view['back'], *slot_view['details']]
        if s.get('thumb')
    )
    return slots_cfg, slot_view
