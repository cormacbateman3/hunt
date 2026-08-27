"""Django service layer for image prefill.

ReferenceData snapshots the live taxonomy into the plain-dict shape the pure
resolver in prefill.core expects (the package/service seam — Lambda later ships
a JSON snapshot with the same shape). process_job orchestrates one PrefillJob:
extract -> resolve -> tier-tagged payload.
"""
from collections import defaultdict

from django.conf import settings
from django.utils import timezone
from PIL import Image

from apps.core.models import GeographicUnit, LicenseType, State
from apps.prefill.models import PrefillJob
from prefill import core

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MIN_IMAGE_EDGE_PX = 200


class ReferenceData:
    """Snapshot of the live taxonomy, shaped for fast matching."""

    STATE_ALIASES = {
        "PENNA": "PA", "PENN": "PA", "MICH": "MI", "WISC": "WI", "MINN": "MN",
        "MONT": "MT", "CONN": "CT", "MASS": "MA", "TENN": "TN", "CALIF": "CA",
        "ILL": "IL", "IND": "IN", "ORE": "OR", "WASH": "WA",
    }

    def __init__(self):
        norm = core._norm
        self.states_by_key = {}
        for s in State.objects.all():
            rec = {"id": s.id, "name": s.name, "abbrev": s.code, "min_year": s.min_license_year or 1850}
            self.states_by_key[norm(s.code)] = rec
            self.states_by_key[norm(s.name)] = rec

        self.geo_by_state = defaultdict(list)
        self.geo_num = defaultdict(dict)   # abbrev -> {unit_number: rec}
        self.geo_statewide = {}
        for g in GeographicUnit.objects.select_related("state").all():
            if not g.state:
                continue
            ab = g.state.code
            rec = {"id": g.id, "name": g.name, "norm": norm(g.name), "is_statewide": g.is_statewide}
            if g.is_statewide:
                self.geo_statewide[ab] = rec
            else:
                self.geo_by_state[ab].append(rec)
            if g.unit_number:
                self.geo_num[ab][str(g.unit_number).strip().lstrip("0") or "0"] = rec

        self.lt = defaultdict(list)
        for t in LicenseType.objects.select_related("state").filter(is_system_value=True):
            ab = t.state.code if t.state else ""
            rec = {"id": t.id, "name": t.name, "norm": norm(t.name), "slug": t.slug}
            if t.category == "addon_type":
                rec.update(
                    {
                        "species": t.target_species,
                        "species_norm": norm(t.target_species),
                        "method_norm": norm(t.hunting_method),
                        "instrument": t.instrument,
                        "first_year": t.first_year,
                        "last_year": t.last_year,
                    }
                )
            self.lt[(ab, t.category)].append(rec)

    def state(self, text):
        norm = core._norm
        key = norm(text)
        key = norm(self.STATE_ALIASES.get(key, key))
        return self.states_by_key.get(key)

    def license_candidates(self, abbrev, category):
        out, seen = [], set()
        for ab in (abbrev, "", "FD"):                 # state-specific, universal, federal
            for rec in self.lt.get((ab, category), []):
                if rec["id"] not in seen:
                    out.append(rec)
                    seen.add(rec["id"])
        return out


def validate_image(uploaded) -> str | None:
    """Reject non-images, oversized files, and tiny images before spending a model call."""
    if uploaded is None:
        return 'No image uploaded.'
    if uploaded.size > MAX_IMAGE_BYTES:
        return 'Image is larger than 10 MB.'
    try:
        with Image.open(uploaded) as im:
            im.verify()
        uploaded.seek(0)
        with Image.open(uploaded) as im:
            width, height = im.size
    except Exception:  # noqa: BLE001
        return 'File is not a readable image.'
    finally:
        uploaded.seek(0)
    if min(width, height) < MIN_IMAGE_EDGE_PX:
        return f'Image is too small (min {MIN_IMAGE_EDGE_PX}px on the short edge).'
    return None


def rate_limit_error(user) -> str | None:
    now = timezone.now()
    hour = PrefillJob.objects.filter(user=user, created_at__gte=now - timezone.timedelta(hours=1)).count()
    if hour >= settings.PREFILL_RATE_PER_HOUR:
        return 'Hourly prefill limit reached — try again in a bit.'
    day = PrefillJob.objects.filter(user=user, created_at__gte=now - timezone.timedelta(days=1)).count()
    if day >= settings.PREFILL_RATE_PER_DAY:
        return 'Daily prefill limit reached.'
    return None


def _annotate_checks(payload):
    """4e's row treatment, decided here where the floors are known.

    A field renders amber (the ✓/× pair) when its match sat at or just
    above the fuzzy floor, came from the second pass, or was inferred
    rather than read; high and medium otherwise render green with
    "change". The client can't know the floors — they live in the
    prefill config — so the payload carries a plain ``check`` flag.
    """
    fuzzy_floor = getattr(core, 'FUZZY_FLOOR', 80)
    geo_floor = getattr(core, 'GEO_NAME_FLOOR', fuzzy_floor)
    just_above = 4

    def mark(data, floor):
        if not isinstance(data, dict) or data.get('value') is None:
            return
        near_floor = data.get('score', 100) <= floor + just_above
        data['check'] = bool(data.get('inferred') or data.get('second_pass') or near_floor)

    for name, data in (payload.get('fields') or {}).items():
        if name == 'addon_type':
            for item in (data or {}).get('items', []):
                mark(item, fuzzy_floor)
        else:
            mark(data, geo_floor if name == 'geographic_unit' else fuzzy_floor)
    return payload


def _unmatched(fields) -> list[dict]:
    """Values we read but couldn't match — the suggestion-panel feed."""
    out = []
    for name in ('state', 'geographic_unit', 'residency', 'holder_eligibility',
                 'activity_scope', 'duration', 'material', 'shape'):
        d = fields.get(name) or {}
        if d.get('value') is None and d.get('source_text'):
            out.append({'field': name, 'source_text': str(d['source_text'])})
    for item in (fields.get('addon_type') or {}).get('items', []):
        if item.get('value') is None and item.get('source_text'):
            out.append({'field': 'addon_type', 'source_text': str(item['source_text'])})
    return out


def process_job(job: PrefillJob, extractor=None, client=None) -> PrefillJob:
    """Run one job through extract -> resolve. Local backend runs inline (the
    async job_id + polling API contract is preserved for the Lambda path in 10.19)."""
    backend = settings.PREFILL_BACKEND
    if backend != 'local':
        job.status = 'failed'
        job.error = f'PREFILL_BACKEND={backend!r} is not wired yet (Lambda path lands with 10.19).'
        job.save(update_fields=['status', 'error'])
        return job

    client = client or core.get_client()
    if client is None:
        job.status = 'failed'
        job.error = 'ANTHROPIC_API_KEY is not configured.'
        job.save(update_fields=['status', 'error'])
        return job

    extract = extractor or core.extract
    with job.image.open('rb') as fh:
        result = extract(fh, client)
    if 'error' in result:
        job.status = 'failed'
        job.error = result['error']
        job.save(update_fields=['status', 'error'])
        return job

    job.raw_extraction = result['raw']
    job.model_version = core.MODEL_ID
    job.prompt_version = result.get('prompt_version', '')
    job.latency_ms = int(result.get('latency_ms') or 0)
    job.status = 'resolving'
    job.save(update_fields=['raw_extraction', 'model_version', 'prompt_version', 'latency_ms', 'status'])

    resolution = core.resolve(result['raw'], ReferenceData(), client)
    payload = {
        'state_abbrev': resolution['state_abbrev'],
        'item_kind': resolution['item_kind'],
        'lot_detected': resolution['lot_detected'],
        'fields': resolution['fields'],
        'raw_text': resolution['raw_text'],
        'context_text': resolution['context_text'],
        'unmatched': _unmatched(resolution['fields']),
    }
    job.resolved_payload = _annotate_checks(payload)
    job.cost_usd = round(result.get('cost_usd', 0) + resolution.get('second_pass_cost_usd', 0), 5)
    job.status = 'complete'
    job.completed_at = timezone.now()
    job.save(update_fields=['resolved_payload', 'cost_usd', 'status', 'completed_at'])
    return job


def job_state(job: PrefillJob) -> dict:
    """The polling-API contract."""
    state = {'job_id': job.pk, 'status': job.status}
    if job.status == 'complete':
        state['payload'] = job.resolved_payload
        # The few numbers a ledger line is allowed to cite, computed here
        # once so the copy layer never queries on its own (4e).
        from apps.prefill.ledger import line_facts
        state['line_facts'] = line_facts(job)
    if job.status == 'failed':
        state['error'] = job.error
    return state


def resume_state_json(request) -> str:
    """The completed job behind a failed submit, as JSON for the template.

    A validation error reloads the page, but the read already happened —
    with this in context the ledger settles straight back in, describing
    the values the form kept, instead of vanishing with the reload.
    """
    import json

    job_id = request.POST.get('prefill_job_id', '') if request.method == 'POST' else ''
    if not job_id.isdigit():
        return 'null'
    job = PrefillJob.objects.filter(
        pk=int(job_id), user=request.user, status='complete',
    ).first()
    return json.dumps(job_state(job)) if job else 'null'
