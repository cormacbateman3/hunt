"""Image-prefill library for the listing/collection forms.

This is the app-ready consolidation of the sandbox notebook. It is organized into
the three seams from docs/internal/image_prefill_model_dev_plan.md so it lifts
cleanly into the real package later:

    reference   -> ReferenceData (DB-backed taxonomy provider; the Django service seam)
    extractor   -> prep_image / EXTRACTION_TOOL / SYSTEM_PROMPT / extract  (pure VLM call)
    resolver    -> resolve()  (raw VLM output -> tier-tagged, form-ready payload)

Reference data is read from the live Django ORM (not CSVs). Run the DB seeders first:
    python manage.py seed_states && seed_geographic_units && seed_license_types
"""
from __future__ import annotations

import base64
import os
import re
import sys
import time
from collections import defaultdict
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops

# --------------------------------------------------------------------------- #
# Django bootstrap (so the module is importable from a notebook or a plain script)
# --------------------------------------------------------------------------- #
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def bootstrap_django() -> None:
    # Jupyter runs an asyncio event loop; Django blocks sync ORM calls from an async
    # context unless we opt in. Safe in a notebook/script (this only guards real async
    # web requests). Must be set before any ORM access.
    os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
    from django.apps import apps as _apps
    if _apps.ready:
        return
    sys.path.insert(0, str(PROJECT_ROOT))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
    import django
    django.setup()


bootstrap_django()

from django.conf import settings  # noqa: E402

from apps.core.constants import COLOR_CHOICES, SHAPE_CHOICES  # noqa: E402
from apps.core.models import GeographicUnit, LicenseType, State  # noqa: E402

# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
MODEL_ID = "claude-haiku-4-5-20251001"
PRICE = {"input": 0.80, "output": 4.00, "cache_write": 1.00, "cache_read": 0.08}  # USD / 1M tokens

# Cost levers: a smaller long edge than the old 1568 (image tokens scale with area),
# plus trimming the photographed background. Tune MAX_IMAGE_EDGE down and re-measure.
MAX_IMAGE_EDGE = 1120
AUTO_CROP = True

ALLOW_INFERENCE = True       # curated, flagged domain inferences, capped at 'medium'
FUZZY_FLOOR = 88             # below this we never prefill a value; route to a suggestion
GEO_NAME_FLOOR = 90
CURRENT_YEAR = datetime.now().year

RESAMPLE = Image.Resampling.LANCZOS

# License-type dimensions that resolve to LicenseType rows (vs. plain choice fields).
SINGLE_DIMENSIONS = ["residency", "holder_eligibility", "activity_scope", "duration", "material"]


# --------------------------------------------------------------------------- #
# Normalization helper
# --------------------------------------------------------------------------- #
def _norm(text: Any) -> str:
    """Uppercase, strip punctuation, collapse whitespace — for matching only."""
    text = re.sub(r"[^A-Za-z0-9 ]", " ", str(text or ""))
    return re.sub(r"\s+", " ", text).strip().upper()


# --------------------------------------------------------------------------- #
# 1. Reference data provider (DB-backed)
# --------------------------------------------------------------------------- #
class ReferenceData:
    """Snapshot of the live taxonomy, shaped for fast matching.

    Swapping this for a provider backed by a JSON vocab snapshot (in Lambda) leaves
    the resolver unchanged — that is the package/service seam.
    """

    STATE_ALIASES = {
        "PENNA": "PA", "PENN": "PA", "MICH": "MI", "WISC": "WI", "MINN": "MN",
        "MONT": "MT", "CONN": "CT", "MASS": "MA", "TENN": "TN", "CALIF": "CA",
        "ILL": "IL", "IND": "IN", "ORE": "OR", "WASH": "WA",
    }

    def __init__(self) -> None:
        self.states_by_key: dict[str, dict] = {}
        for s in State.objects.all():
            rec = {"id": s.id, "name": s.name, "abbrev": s.code, "min_year": s.min_license_year or 1850}
            self.states_by_key[_norm(s.code)] = rec
            self.states_by_key[_norm(s.name)] = rec

        self.geo_by_state: dict[str, list[dict]] = defaultdict(list)
        self.geo_num: dict[str, dict[str, dict]] = defaultdict(dict)   # abbrev -> {unit_number: rec}
        self.geo_statewide: dict[str, dict] = {}
        for g in GeographicUnit.objects.select_related("state").all():
            if not g.state:
                continue
            ab = g.state.code
            rec = {"id": g.id, "name": g.name, "norm": _norm(g.name), "is_statewide": g.is_statewide}
            if g.is_statewide:
                self.geo_statewide[ab] = rec
            else:
                self.geo_by_state[ab].append(rec)
            if g.unit_number:
                self.geo_num[ab][str(g.unit_number).strip().lstrip("0") or "0"] = rec

        self.lt: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for t in LicenseType.objects.select_related("state").all():
            ab = t.state.code if t.state else ""
            self.lt[(ab, t.category)].append(
                {"id": t.id, "name": t.name, "norm": _norm(t.name), "slug": t.slug}
            )

    def state(self, text: Any) -> dict | None:
        key = _norm(text)
        key = _norm(self.STATE_ALIASES.get(key, key))
        return self.states_by_key.get(key)

    def license_candidates(self, abbrev: str, category: str) -> list[dict]:
        out, seen = [], set()
        for ab in (abbrev, ""):                       # state-specific then universal
            for rec in self.lt.get((ab, category), []):
                if rec["id"] not in seen:
                    out.append(rec)
                    seen.add(rec["id"])
        return out


# --------------------------------------------------------------------------- #
# 2. Curated vocabulary knowledge (small + stable; later movable to DB/constants)
# --------------------------------------------------------------------------- #
# normalized term -> (dimension, canonical). Canonical is matched against the state's
# candidate names, so add-on keywords (Turkey, Bear...) generalize across states.
CONCEPT_ALIASES: dict[str, tuple[str, str]] = {
    # residency
    "RESIDENT": ("residency", "Resident"),
    "NONRESIDENT": ("residency", "Nonresident"), "NON RESIDENT": ("residency", "Nonresident"), "NR": ("residency", "Nonresident"),
    "ALIEN": ("residency", "Alien"), "NONRESIDENT ALIEN": ("residency", "Alien"),
    # holder eligibility
    "ADULT": ("holder_eligibility", "General"), "REGULAR": ("holder_eligibility", "General"), "GENERAL": ("holder_eligibility", "General"),
    "JUNIOR": ("holder_eligibility", "Junior"), "JR": ("holder_eligibility", "Junior"),
    "YOUTH": ("holder_eligibility", "Youth"), "MINOR": ("holder_eligibility", "Youth"),
    "SENIOR": ("holder_eligibility", "Senior"), "SR": ("holder_eligibility", "Senior"),
    "MILITARY": ("holder_eligibility", "Military"), "VETERAN": ("holder_eligibility", "Veteran"), "DISABLED": ("holder_eligibility", "Disabled"),
    # activity scope
    "HUNTER": ("activity_scope", "General Hunting"), "HUNTING": ("activity_scope", "General Hunting"),
    "HUNT": ("activity_scope", "General Hunting"), "RESIDENT HUNTER": ("activity_scope", "General Hunting"),
    "TRAPPING": ("activity_scope", "Trapping"), "TRAPPER": ("activity_scope", "Trapping"),
    "FURBEARER": ("activity_scope", "Trapping"), "FUR BEARER": ("activity_scope", "Trapping"),
    "HUNTING AND FISHING": ("activity_scope", "Combo"), "COMBINATION": ("activity_scope", "Combo"),
    "COMBO": ("activity_scope", "Combo"), "SPORTSMAN": ("activity_scope", "Sportsman"),
    # duration
    "ANNUAL": ("duration", "Annual"), "LIFETIME": ("duration", "Lifetime"),
    "1 DAY": ("duration", "1-day"), "3 DAY": ("duration", "3-day"), "7 DAY": ("duration", "7-day"),
    # add-on type (species / tags / stamps) -> distinctive keyword
    "ANTLERLESS DEER": ("addon_type", "Antlerless Deer"), "ANTLERLESS": ("addon_type", "Antlerless Deer"), "DOE": ("addon_type", "Antlerless Deer"),
    "DMAP": ("addon_type", "DMAP"),
    "TURKEY": ("addon_type", "Turkey"), "TURKEY TAG": ("addon_type", "Turkey"), "SPRING TURKEY": ("addon_type", "Turkey"),
    "BEAR": ("addon_type", "Bear"), "ARCHERY": ("addon_type", "Archery"),
    "MUZZLELOADER": ("addon_type", "Muzzleloader"), "FLINTLOCK": ("addon_type", "Muzzleloader"),
    "PHEASANT": ("addon_type", "Pheasant"), "ELK": ("addon_type", "Elk"),
    "WATERFOWL": ("addon_type", "Waterfowl"), "DUCK": ("addon_type", "Waterfowl"), "MIGRATORY": ("addon_type", "Waterfowl"),
    "TROUT": ("addon_type", "Trout"),
}

# tokens too common to disambiguate an add-on on their own
STOP_TOKENS = {"TAG", "TAGS", "PERMIT", "STAMP", "LICENSE", "BIRD", "SPECIAL", "RECORD", "STATE", "RESIDENT"}

# add-ons that imply a hunting license (used for the activity_scope inference)
HUNTING_ADDON_KEYWORDS = {"ANTLERLESS", "DEER", "TURKEY", "BEAR", "PHEASANT", "ARCHERY", "MUZZLELOADER", "ELK", "DMAP"}

# color text -> COLOR_CHOICES key
COLOR_KEY = {_norm(label): key for key, label in COLOR_CHOICES}
COLOR_ALIASES = {
    "TAN": "brown_tan", "BROWN": "brown_tan", "BEIGE": "brown_tan", "KHAKI": "brown_tan",
    "GOLD": "gold", "GOLDEN": "gold", "YELLOW": "yellow",
    "CREAM": "cream_ivory", "IVORY": "cream_ivory", "OFF WHITE": "cream_ivory",
    "GREY": "gray", "GRAY": "gray", "SILVER": "silver", "ORANGE": "orange",
    "RED": "red", "CRIMSON": "crimson_dark_red", "DARK RED": "crimson_dark_red", "MAROON": "crimson_dark_red",
    "GREEN": "forest_green", "FOREST GREEN": "forest_green", "DARK GREEN": "forest_green", "OLIVE": "forest_green",
    "LIME": "lime_bright_green", "BRIGHT GREEN": "lime_bright_green",
    "BLUE": "blue", "NAVY": "navy", "DARK BLUE": "navy", "WHITE": "white", "BLACK": "black",
    "PINK": "pink", "PURPLE": "purple", "VIOLET": "purple", "MULTI": "multi_color", "MULTICOLOR": "multi_color",
}
SHAPE_KEY = {_norm(label): key for key, label in SHAPE_CHOICES}
COLOR_LABELS = dict(COLOR_CHOICES)
SHAPE_LABELS = dict(SHAPE_CHOICES)


# --------------------------------------------------------------------------- #
# 3. Extractor (image prep + schema + prompt + VLM call)
# --------------------------------------------------------------------------- #
def auto_crop(img: Image.Image, threshold: int = 22, pad: int = 10) -> Image.Image:
    """Trim a near-uniform background border (licenses photographed on a desk)."""
    bg = Image.new("RGB", img.size, img.getpixel((0, 0)))
    diff = ImageChops.difference(img, bg).convert("L").point(lambda p: 255 if p > threshold else 0)
    bbox = diff.getbbox()
    if not bbox:
        return img
    l, t, r, b = bbox
    l, t = max(0, l - pad), max(0, t - pad)
    r, b = min(img.width, r + pad), min(img.height, b + pad)
    if (r - l) < img.width * 0.30 or (b - t) < img.height * 0.30:
        return img  # busy background — don't risk cutting the item
    return img.crop((l, t, r, b))


def prep_image(path: str | Path) -> tuple[str, str]:
    """Flatten, optionally crop, resize, and base64-encode an image for the VLM."""
    with Image.open(path) as im:
        img = im.copy()
    if img.mode in {"RGBA", "LA"} or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        bg = Image.new("RGB", rgba.size, "white")
        bg.paste(rgba, mask=rgba.getchannel("A"))
        img = bg
    else:
        img = img.convert("RGB")
    if AUTO_CROP:
        img = auto_crop(img)
    img.thumbnail((MAX_IMAGE_EDGE, MAX_IMAGE_EDGE), RESAMPLE)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=88, optimize=True)
    return base64.b64encode(buf.getvalue()).decode("utf-8"), "image/jpeg"


EXTRACTION_TOOL = {
    "name": "extract_license_fields",
    "description": "Extract structured fields from an antique US hunting or fishing license image.",
    "input_schema": {
        "type": "object",
        "properties": {
            "state_name_or_abbrev": {"type": ["string", "null"], "description": 'State exactly as printed, incl. historical forms like "PENNA.", "MICH."'},
            "license_year": {"type": ["integer", "null"], "description": "Four-digit year as printed. Only derive a 2-digit year when the century is unambiguous."},
            "era_guess": {"type": ["string", "null"], "enum": ["Pre-1920", "1920s", "1930s", "1940s", "1950s", "1960s", "1970s", "1980s", "1990s", "2000s", None], "description": "Decade only when no explicit year is visible."},
            "geographic_unit_name": {"type": ["string", "null"], "description": 'County/unit name OR number exactly as printed, e.g. "Lancaster", "Co. 36", "COUNTY NUMBER 36", "GMU 12". Transcribe the number; do not convert it to a name. Null if statewide.'},
            "is_statewide": {"type": "boolean", "description": "True only if the license explicitly covers the whole state with no county/unit restriction."},
            "residency": {"type": ["string", "null"], "description": 'Residency exactly as printed; keep any "Non-" prefix, e.g. "Resident", "Non-Resident".'},
            "holder_eligibility": {"type": ["string", "null"], "description": 'Eligibility class, e.g. "Adult", "Junior", "Senior".'},
            "activity_scope": {"type": ["string", "null"], "description": 'Base activity, e.g. "Hunter", "Hunting", "Trapping", "Hunting and Fishing". Do NOT put species tags/stamps here.'},
            "duration": {"type": ["string", "null"], "description": 'Validity period if printed, e.g. "Annual", "7-Day".'},
            "addon_type": {"type": "array", "items": {"type": "string"}, "maxItems": 4, "description": 'Add-on stamps/tags/permits printed on the item — a license can have several, e.g. ["Turkey Tag", "Antlerless Deer"]. Species tags (deer, turkey, bear, duck) belong here, NOT in activity_scope.'},
            "serial_number": {"type": ["string", "null"], "description": 'License/serial number exactly as printed, character-by-character. Some PA tags print a single letter (e.g. "F") ABOVE or beside the number that is part of the serial — include it, e.g. "F 25009". Never infer missing digits.'},
            "material": {"type": ["string", "null"], "enum": ["Paper/Cardstock", "Metal Button", "Metal Tag", "Celluloid", "Fabric/Canvas", "Plastic", None]},
            "shape": {"type": ["string", "null"], "enum": ["Rectangle", "Square", "Button/Disc", "Tag (with hole)", "Strip", "Irregular/Custom", None]},
            "dominant_colors": {"type": "array", "items": {"type": "string"}, "maxItems": 3, "description": 'Up to 3 dominant colors, most prominent first. Prefer single basic color words ("blue", "tan", "gold"), not combos like "yellow/gold".'},
            "raw_text_transcription": {"type": "string", "description": "ONLY text physically printed on the item, in reading order. Never add common license phrases from memory. Omit illegible words rather than guess."},
            "inferred_fields": {"type": "array", "items": {"type": "string"}, "description": 'Names of any fields filled by inference from the license type rather than printed text (e.g. "duration"). Empty if everything was read from the item.'},
            "per_field_confidence": {"type": "object", "description": "Numeric 0.0-1.0 per populated field. Omit null fields."},
        },
        "required": ["raw_text_transcription", "per_field_confidence", "addon_type", "dominant_colors", "inferred_fields"],
    },
}

SYSTEM_PROMPT = """You are an expert cataloger of antique US hunting and fishing licenses.

TRANSCRIPTION (raw_text_transcription) — be strict:
- Include ONLY words, numbers, and marks physically printed on the item, in reading order.
- Never add phrases you expect to be there. If you cannot read something, leave it out.
- Never hallucinate or complete serial numbers; transcribe them character-by-character.
- Some PA tags print a single letter (e.g. "F") above/beside the number — it is part of the serial.

STRUCTURED FIELDS:
- Fill from the printed text whenever possible.
- Species tags and stamps (deer, antlerless, turkey, bear, duck/waterfowl, trout) go in addon_type (a list), NOT activity_scope.
- A license can have multiple add-ons — list them all.
- residency: keep the full "Non-" prefix if present.
- geographic_unit_name: if a county NUMBER is shown ("Co. 36", "COUNTY NUMBER 36"), transcribe the number; do not convert it to a name.

INFERENCE — allowed but must be flagged:
- You MAY infer a field from the license's evident type when it is essentially certain (e.g. a resident hunting tag is Annual; "HUNTER" implies general Hunting).
- For any inferred field: set its confidence <= 0.7 AND list the field name in inferred_fields.
- Do NOT infer state, year, county, or serial number — those must come from printed text.

CONFIDENCE (per_field_confidence, 0.0-1.0): 0.90+ certain from image; 0.60-0.89 partial/inferred; below 0.60 return null instead.

If the item is not a hunting/fishing license, transcribe what is legible and leave unsupported fields null."""


def get_client():
    import anthropic
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
    key = os.getenv("ANTHROPIC_API_KEY")
    return anthropic.Anthropic(api_key=key) if key else None


def extract(path: str | Path, client=None) -> dict[str, Any]:
    """Run one Claude tool-use extraction against a license image."""
    client = client or get_client()
    if client is None:
        return {"error": "ANTHROPIC_API_KEY not set"}
    started = time.perf_counter()
    try:
        b64, media_type = prep_image(path)
        resp = client.messages.create(
            model=MODEL_ID,
            max_tokens=1500,
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            tools=[{**EXTRACTION_TOOL, "cache_control": {"type": "ephemeral"}}],
            tool_choice={"type": "tool", "name": EXTRACTION_TOOL["name"]},
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
                {"type": "text", "text": "Extract fields using the extract_license_fields tool."},
            ]}],
        )
        block = next((b for b in resp.content if getattr(b, "type", None) == "tool_use"), None)
        if block is None:
            return {"error": "no tool_use block returned"}
        u = resp.usage
        usage = {k: int(getattr(u, k, 0) or 0) for k in
                 ["input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"]}
        cost = (usage["input_tokens"] * PRICE["input"] + usage["output_tokens"] * PRICE["output"]
                + usage["cache_creation_input_tokens"] * PRICE["cache_write"]
                + usage["cache_read_input_tokens"] * PRICE["cache_read"]) / 1_000_000
        raw = block.input if isinstance(block.input, dict) else dict(block.input)
        return {"raw": raw, "usage": usage, "cost_usd": round(cost, 6),
                "latency_ms": round((time.perf_counter() - started) * 1000, 1)}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}


# --------------------------------------------------------------------------- #
# 4. Resolver
# --------------------------------------------------------------------------- #
from rapidfuzz import fuzz, process  # noqa: E402

ORDER = ["unmatched", "low", "medium", "high"]


def _cap(tier: str, max_tier: str) -> str:
    return ORDER[min(ORDER.index(tier), ORDER.index(max_tier))]


def _min_tier(tiers: list[str]) -> str:
    return ORDER[min((ORDER.index(t) for t in tiers), default=0)] if tiers else "unmatched"


def tier_for(conf: float, score: int) -> str:
    if conf >= 0.85 and score >= 95:
        return "high"
    if conf >= 0.65 and score >= FUZZY_FLOOR:
        return "medium"
    if conf >= 0.40 and score >= FUZZY_FLOOR:
        return "low"
    return "unmatched"


def conf_of(raw: dict, field: str) -> float:
    m = raw.get("per_field_confidence") or {}
    v = m.get(field, 0)
    if isinstance(v, dict):
        v = v.get("value", v.get("confidence", 0))
    try:
        return max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        return 0.0


def _blank(source: Any = None, conf: float = 0.0) -> dict:
    return {"value": None, "name": None, "source_text": source, "score": 0, "conf": conf, "tier": "unmatched", "inferred": False}


def _hit(c: dict, source: Any, conf: float, score: int) -> dict:
    return {"value": c["id"], "name": c["name"], "source_text": source, "score": score,
            "conf": conf, "tier": tier_for(conf, score), "inferred": False}


def match_vocab(text: Any, candidates: list[dict], conf: float) -> dict:
    """Layered match: exact -> distinctive-token overlap -> floored fuzzy.

    Returns a LicenseType id+name, or a blank (so the form leaves it empty and the
    raw text becomes a suggestion) when nothing clears the floor. Never prefills a
    low-confidence guess.
    """
    if not text or not candidates:
        return _blank(text, conf)
    nt = _norm(text)
    for c in candidates:                                   # 1. exact
        if c["norm"] == nt:
            return _hit(c, text, conf, 100)
    src = set(nt.split()) - STOP_TOKENS                    # 2. distinctive-token overlap
    if src:
        scored = [(len((set(c["norm"].split()) - STOP_TOKENS) & src), c) for c in candidates]
        scored = [(ov, c) for ov, c in scored if ov]
        if scored:
            best = max(ov for ov, _ in scored)
            top = [c for ov, c in scored if ov == best]
            if len(top) == 1:
                return _hit(top[0], text, conf, 92)
            hit = process.extractOne(nt, [c["norm"] for c in top], scorer=fuzz.token_sort_ratio)
            return _hit(top[hit[2]], text, conf, max(FUZZY_FLOOR, int(hit[1])))
    hit = process.extractOne(nt, [c["norm"] for c in candidates], scorer=fuzz.token_sort_ratio)  # 3. fuzzy floor
    if hit and hit[1] >= FUZZY_FLOOR:
        return _hit(candidates[hit[2]], text, conf, int(hit[1]))
    return _blank(text, conf)


def _direct(value: Any, conf: float, max_tier: str = "high") -> dict:
    missing = value is None or (isinstance(value, str) and not value.strip()) or (isinstance(value, list) and not value)
    if missing:
        return _blank(value, conf)
    name = ", ".join(map(str, value)) if isinstance(value, list) else value
    return {"value": value, "name": name, "source_text": value, "score": 100,
            "conf": conf, "tier": _cap(tier_for(conf, 100), max_tier), "inferred": False}


COUNTY_NUM_RE = re.compile(r"(?:CO|COUNTY)\.?\s*(?:NUMBER|NUM|NO|#)?\s*0*(\d{1,3})", re.I)


def resolve_geo(raw: dict, abbrev: str, ref: ReferenceData) -> dict:
    geo_text = raw.get("geographic_unit_name")
    conf = conf_of(raw, "geographic_unit_name")
    if raw.get("is_statewide") and abbrev in ref.geo_statewide:
        sc = conf_of(raw, "is_statewide") or 0.8
        rec = ref.geo_statewide[abbrev]
        return {"value": rec["id"], "name": rec["name"], "source_text": geo_text or "Statewide",
                "score": 100, "conf": sc, "tier": tier_for(sc, 100), "inferred": False}
    if not abbrev:
        return _blank(geo_text, conf)
    # 1. county number — from the geo field, else scan the raw transcription
    m = COUNTY_NUM_RE.search(str(geo_text or "")) or COUNTY_NUM_RE.search(str(raw.get("raw_text_transcription") or ""))
    if m:
        num = m.group(1).lstrip("0") or "0"
        rec = ref.geo_num.get(abbrev, {}).get(num)
        if rec:
            c = max(conf, 0.8)
            return {"value": rec["id"], "name": rec["name"], "source_text": geo_text or f"Co. {num}",
                    "score": 100, "conf": c, "tier": tier_for(c, 100), "inferred": False}
    # 2. name match
    if geo_text:
        cleaned = re.sub(r"\b(COUNTY|CO|PARISH|GMU|WMU|WMD|DPA)\b", " ", _norm(geo_text)).strip() or _norm(geo_text)
        cands = ref.geo_by_state.get(abbrev, [])
        if cands:
            hit = process.extractOne(cleaned, [c["norm"] for c in cands], scorer=fuzz.WRatio)
            if hit and hit[1] >= GEO_NAME_FLOOR:
                rec = cands[hit[2]]
                return {"value": rec["id"], "name": rec["name"], "source_text": geo_text,
                        "score": int(hit[1]), "conf": conf, "tier": tier_for(conf, int(hit[1])), "inferred": False}
    return _blank(geo_text, conf)


def resolve_year(raw: dict, state: dict | None) -> dict:
    y = raw.get("license_year")
    conf = conf_of(raw, "license_year")
    if y in (None, ""):
        return _blank(y, conf)
    res = {"value": y, "name": str(y), "source_text": y, "score": 100,
           "conf": conf, "tier": tier_for(conf, 100), "inferred": False}
    try:
        yi = int(y)
        min_year = state["min_year"] if state else 1850
        if yi < min_year or yi > CURRENT_YEAR:
            res["tier"] = "unmatched"
    except (TypeError, ValueError):
        pass
    return res


def resolve_dimension(raw: dict, field: str, abbrev: str, ref: ReferenceData) -> tuple[dict, tuple | None]:
    """Resolve a single license-type dimension. Returns (result, reroute) where reroute
    is (target_dim, canonical, source_text, conf) if the value belongs in another dimension."""
    text = raw.get(field)
    conf = conf_of(raw, field)
    if not text:
        return _blank(None, conf), None
    alias = CONCEPT_ALIASES.get(_norm(text))
    if alias:
        dim, canonical = alias
        if dim != field:
            return _blank(text, conf), (dim, canonical, text, conf)   # belongs elsewhere
        return match_vocab(canonical, ref.license_candidates(abbrev, dim), conf), None
    return match_vocab(text, ref.license_candidates(abbrev, field), conf), None


def resolve_addons(raw: dict, abbrev: str, ref: ReferenceData, reroutes: list[tuple]) -> dict:
    cands = ref.license_candidates(abbrev, "addon_type")
    base_conf = conf_of(raw, "addon_type")
    sources: list[tuple[str, float, bool]] = [(it, base_conf, False) for it in (raw.get("addon_type") or [])]
    for dim, canonical, text, conf in reroutes:
        if dim == "addon_type":
            sources.append((text, conf, True))            # came in under the wrong dimension
    out, seen = [], set()
    for text, conf, rerouted in sources:
        alias = CONCEPT_ALIASES.get(_norm(text))
        query = alias[1] if (alias and alias[0] == "addon_type") else text
        res = match_vocab(query, cands, conf)
        res["source_text"] = text
        if rerouted and res["value"] is not None:
            res["inferred"] = True
        key = res["value"] if res["value"] is not None else _norm(text)
        if key in seen:
            continue
        seen.add(key)
        out.append(res)
    if not out:
        return _blank(None, base_conf)
    matched = [r for r in out if r["value"] is not None]
    return {
        "value": [r["value"] for r in matched],
        "name": ", ".join(r["name"] for r in matched) or None,
        "source_text": ", ".join(str(r["source_text"]) for r in out if r["source_text"]),
        "score": min((r["score"] for r in out), default=0),
        "conf": base_conf,
        "tier": _min_tier([r["tier"] for r in out]),
        "inferred": any(r["inferred"] for r in out),
        "items": out,
    }


def resolve_colors(values: Any, conf: float) -> dict:
    if not values:
        return _blank(values, conf)
    keys, unmatched = [], []
    for v in values:
        for token in re.split(r"[\/,&]| and ", str(v)):
            t = _norm(token)
            if not t:
                continue
            key = COLOR_KEY.get(t) or COLOR_ALIASES.get(t) or next((k for a, k in COLOR_ALIASES.items() if a in t), None)
            if key and key not in keys:
                keys.append(key)
            elif not key:
                unmatched.append(token.strip())
    keys = keys[:3]
    if not keys:
        return {**_blank(values, conf), "unmatched": unmatched}
    return {"value": keys, "name": ", ".join(COLOR_LABELS[k] for k in keys),
            "source_text": ", ".join(map(str, values)), "score": 100, "conf": conf,
            "tier": _cap(tier_for(conf, 100), "medium"), "inferred": False, "unmatched": unmatched}


def resolve_shape(value: Any, conf: float) -> dict:
    if not value:
        return _blank(value, conf)
    key = SHAPE_KEY.get(_norm(value))
    if not key:
        return _blank(value, conf)
    return {"value": key, "name": SHAPE_LABELS[key], "source_text": value, "score": 100,
            "conf": conf, "tier": tier_for(conf, 100), "inferred": False}


def apply_inferences(fields: dict, abbrev: str, ref: ReferenceData) -> None:
    """Curated, flagged inferences for EMPTY fields only (ALLOW_INFERENCE gate)."""
    addons = fields.get("addon_type", {})
    addon_text = _norm(addons.get("source_text"))
    hunting_addon = bool(addons.get("value")) and any(k in addon_text for k in HUNTING_ADDON_KEYWORDS)

    act = fields.get("activity_scope", {})
    if act.get("value") is None and hunting_addon:
        gh = match_vocab("General Hunting", ref.license_candidates(abbrev, "activity_scope"), 0.7)
        if gh["value"] is not None:
            gh.update({"inferred": True, "tier": _cap(gh["tier"], "medium"), "source_text": "(inferred from add-ons)"})
            fields["activity_scope"] = gh

    dur = fields.get("duration", {})
    yr = fields.get("license_year", {}).get("value")
    act_now = fields.get("activity_scope", {})
    if (dur.get("value") is None and isinstance(yr, int) and yr < 1980 and act_now.get("value") is not None):
        ann = match_vocab("Annual", ref.license_candidates(abbrev, "duration"), 0.7)
        if ann["value"] is not None:
            ann.update({"inferred": True, "tier": _cap(ann["tier"], "medium"), "source_text": "(inferred: antique tag)"})
            fields["duration"] = ann


def resolve(raw: dict, ref: ReferenceData) -> dict:
    """Resolve a raw VLM extraction into a tier-tagged, form-ready payload."""
    state = ref.state(raw.get("state_name_or_abbrev"))
    sconf = conf_of(raw, "state_name_or_abbrev")
    abbrev = state["abbrev"] if state else ""

    fields: dict[str, dict] = {}
    fields["state"] = (
        {"value": state["id"], "name": state["name"], "source_text": raw.get("state_name_or_abbrev"),
         "score": 100, "conf": sconf, "tier": tier_for(sconf, 100), "inferred": False}
        if state else _blank(raw.get("state_name_or_abbrev"), sconf)
    )
    fields["geographic_unit"] = resolve_geo(raw, abbrev, ref)
    fields["license_year"] = resolve_year(raw, state)
    fields["era_guess"] = _direct(raw.get("era_guess"), conf_of(raw, "era_guess"), max_tier="medium")
    fields["serial_number"] = _direct(raw.get("serial_number"), conf_of(raw, "serial_number"), max_tier="low")
    fields["is_statewide"] = _direct(raw.get("is_statewide"), conf_of(raw, "is_statewide"))

    reroutes: list[tuple] = []
    for field in SINGLE_DIMENSIONS:
        res, rr = resolve_dimension(raw, field, abbrev, ref)
        fields[field] = res
        if rr:
            reroutes.append(rr)

    fields["addon_type"] = resolve_addons(raw, abbrev, ref, reroutes)
    fields["colors"] = resolve_colors(raw.get("dominant_colors"), conf_of(raw, "dominant_colors"))
    fields["shape"] = resolve_shape(raw.get("shape"), conf_of(raw, "shape"))

    for f in set(raw.get("inferred_fields") or []):       # honor the model's own inference flags
        if f in fields and fields[f].get("value") is not None:
            fields[f]["inferred"] = True
            fields[f]["tier"] = _cap(fields[f]["tier"], "medium")

    if ALLOW_INFERENCE:
        apply_inferences(fields, abbrev, ref)

    return {"state_abbrev": abbrev, "fields": fields, "raw_text": raw.get("raw_text_transcription", "")}
