"""KeystoneBid image-prefill core — pure logic, no Django.

    extractor -> prep_image / extract          (VLM call; prompts from prefill/config/)
    resolver  -> resolve(raw, vocab, client)   (raw extraction -> tier-tagged payload)

The vocab provider lives in apps.prefill.services.ReferenceData (Django ORM);
anything exposing the same candidate-dict shape works — Lambda later ships a JSON
snapshot instead. Prompts, extraction schema, aliases, and knobs are editable files
in prefill/config/, hashed together as PROMPT_VERSION (stored on PrefillJob).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops

from apps.core.constants import COLOR_CHOICES, SHAPE_CHOICES

PROJECT_ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- #
# Config — model params, prompts, extraction schema, and aliases live in
# prefill/config/ as editable files (context management: nothing prompt-like is
# hardcoded here). PROMPT_VERSION hashes the prompt+schema combination and is
# what PrefillJob.prompt_version will store in 10.5.
# --------------------------------------------------------------------------- #
CONFIG_DIR = Path(__file__).resolve().parent / "config"


def reload_config() -> str:
    """(Re)load params, prompts, schema, and aliases from prefill/config/.

    Call from the notebook after editing those files (autoreload only tracks
    .py). Returns the new PROMPT_VERSION."""
    global MODEL_ID, PRICE, MAX_IMAGE_EDGE, AUTO_CROP, ALLOW_INFERENCE, SECOND_PASS
    global FUZZY_FLOOR, GEO_NAME_FLOOR, SYSTEM_PROMPT, EXTRACTION_TOOL
    global SECOND_PASS_PROMPT, CONCEPT_ALIASES, PROMPT_VERSION
    cfg = json.loads((CONFIG_DIR / "config.json").read_text(encoding="utf-8"))
    MODEL_ID = cfg["model_id"]
    PRICE = cfg["price_per_mtok"]              # USD / 1M tokens
    MAX_IMAGE_EDGE = cfg["max_image_edge"]     # 1568 = Claude vision optimum; lower = cheaper
    AUTO_CROP = cfg["auto_crop"]
    ALLOW_INFERENCE = cfg["allow_inference"]   # curated, flagged inferences, capped at 'medium'
    SECOND_PASS = cfg["second_pass"]           # constrained re-match, fires on misses only
    FUZZY_FLOOR = cfg["fuzzy_floor"]           # below this we never prefill; route to a suggestion
    GEO_NAME_FLOOR = cfg["geo_name_floor"]
    SYSTEM_PROMPT = (CONFIG_DIR / "system_prompt.md").read_text(encoding="utf-8")
    EXTRACTION_TOOL = json.loads((CONFIG_DIR / "extraction_tool.json").read_text(encoding="utf-8"))
    SECOND_PASS_PROMPT = (CONFIG_DIR / "second_pass_prompt.md").read_text(encoding="utf-8")
    CONCEPT_ALIASES = {k: tuple(v) for k, v in json.loads(
        (CONFIG_DIR / "concept_aliases.json").read_text(encoding="utf-8")).items()}
    PROMPT_VERSION = hashlib.sha1(
        (SYSTEM_PROMPT + json.dumps(EXTRACTION_TOOL, sort_keys=True) + SECOND_PASS_PROMPT).encode("utf-8")
    ).hexdigest()[:10]
    return PROMPT_VERSION


reload_config()

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
# 2. Curated vocabulary knowledge
# --------------------------------------------------------------------------- #
# CONCEPT_ALIASES (normalized term -> (dimension, canonical)) is loaded from
# prefill/config/concept_aliases.json by reload_config(). Canonical is matched
# against the state's candidate names, so add-on keywords generalize across states.

def _alias(text: Any) -> tuple[str, str] | None:
    """Alias lookup that also tries the space-collapsed key (MUZZLE LOADER -> MUZZLELOADER)."""
    nt = _norm(text)
    return CONCEPT_ALIASES.get(nt) or CONCEPT_ALIASES.get(nt.replace(" ", ""))


# tokens too common to disambiguate an add-on on their own
STOP_TOKENS = {"TAG", "TAGS", "PERMIT", "STAMP", "LICENSE", "BIRD", "SPECIAL", "RECORD", "STATE", "RESIDENT"}

# instrument words printed on artifacts -> instrument facet value
INSTRUMENT_WORDS = {
    "TAG": "tag", "TAGS": "tag", "STAMP": "stamp", "PERMIT": "permit",
    "LICENSE": "license", "LICENCE": "license", "CERTIFICATION": "certification", "FEE": "fee",
}

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


# EXTRACTION_TOOL and SYSTEM_PROMPT are loaded from prefill/config/
# (extraction_tool.json, system_prompt.md) by reload_config().


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
                "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                "prompt_version": PROMPT_VERSION}
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
        conf = max(0.0, min(1.0, float(v)))
    except (TypeError, ValueError):
        conf = 0.0
    # Inferred-but-unscored: the model listed the field in inferred_fields but
    # omitted it from per_field_confidence — 0 would wrongly bury a real value.
    if conf == 0.0 and field in set(raw.get("inferred_fields") or []):
        return 0.65
    return conf


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
    alias = _alias(text)
    if alias:
        dim, canonical = alias
        if dim != field:
            return _blank(text, conf), (dim, canonical, text, conf)   # belongs elsewhere
        return match_vocab(canonical, ref.license_candidates(abbrev, dim), conf), None
    return match_vocab(text, ref.license_candidates(abbrev, field), conf), None


def _addon_in_range(c: dict, year: int | None) -> bool:
    if not year:
        return True
    if c.get("first_year") and year < c["first_year"]:
        return False
    if c.get("last_year") and year > c["last_year"]:
        return False
    return True


def match_addon_item(text: Any, conf: float, candidates: list[dict], year: int | None) -> dict:
    """Add-on matcher: era gate -> exact name -> species facet -> layered name fallback.

    Candidates outside first_year/last_year for a resolved year are rejected outright —
    a modern permit can never match a mid-century artifact.
    """
    if not text or not candidates:
        return _blank(text, conf)
    cands = [c for c in candidates if _addon_in_range(c, year)]
    if not cands:
        return _blank(text, conf)

    alias = _alias(text)
    query = alias[1] if (alias and alias[0] == "addon_type") else str(text)
    nt = _norm(query)

    for c in cands:                                        # 1. exact name
        if c["norm"] == nt:
            return _hit(c, text, conf, 100)

    # 2. species facet first: what the artifact is about beats fuzzy name overlap
    orig_tokens = set(_norm(text).split())
    instrument = next((INSTRUMENT_WORDS[t] for t in orig_tokens if t in INSTRUMENT_WORDS), "")
    species_tokens = set(nt.split()) - set(INSTRUMENT_WORDS) - STOP_TOKENS
    if species_tokens:
        scored = []
        for c in cands:
            facet = set(c.get("species_norm", "").split())
            if not facet:
                continue
            if facet == species_tokens:
                s = 3
            elif species_tokens <= facet or facet <= species_tokens:
                s = 2
            elif facet & species_tokens:
                s = 1
            else:
                continue
            if instrument and c.get("instrument") == instrument:
                s += 2                                     # printed instrument word agrees
            elif instrument and c.get("instrument") and c["instrument"] != instrument:
                s -= 1
            scored.append((s, c))
        if scored:
            best = max(s for s, _ in scored)
            top = [c for s, c in scored if s == best]
            if best >= 3:
                if len(top) == 1:
                    return _hit(top[0], text, conf, 95)
                hit = process.extractOne(nt, [c["norm"] for c in top], scorer=fuzz.token_sort_ratio)
                return _hit(top[hit[2]], text, conf, 92)

    res = match_vocab(query, cands, conf)                  # 3. layered name fallback
    res["source_text"] = text
    return res


SECOND_PASS_TOOL = {
    "name": "match_addons",
    "description": "Match extracted add-on texts against the closed candidate list.",
    "input_schema": {
        "type": "object",
        "properties": {
            "matches": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "candidate_id": {"type": ["integer", "null"]},
                    },
                    "required": ["text", "candidate_id"],
                },
            }
        },
        "required": ["matches"],
    },
}


def second_pass_addons(client, transcription: str, unmatched: list[str],
                       candidates: list[dict], year: int | None) -> tuple[dict[str, dict], float]:
    """Constrained re-match for add-ons that missed: a text-only call choosing from a
    closed id list with an explicit none-option. Returns ({text: candidate}, cost)."""
    if client is None or not unmatched or not candidates:
        return {}, 0.0
    by_id = {c["id"]: c for c in candidates}
    listing = "\n".join(
        f'{c["id"]}: {c["name"]}' + (f' [{c["species"]}]' if c.get("species") else "")
        for c in candidates
    )
    prompt = SECOND_PASS_PROMPT.format(
        year_note=f" The item is from {year}." if year else "",
        texts="\n".join(f"- {t}" for t in unmatched),
        candidates=listing,
    )
    try:
        resp = client.messages.create(
            model=MODEL_ID,
            max_tokens=300,
            tools=[SECOND_PASS_TOOL],
            tool_choice={"type": "tool", "name": SECOND_PASS_TOOL["name"]},
            messages=[{"role": "user", "content": prompt}],
        )
        block = next((b for b in resp.content if getattr(b, "type", None) == "tool_use"), None)
        if block is None:
            return {}, 0.0
        u = resp.usage
        cost = (int(u.input_tokens or 0) * PRICE["input"] + int(u.output_tokens or 0) * PRICE["output"]) / 1_000_000
        data = block.input if isinstance(block.input, dict) else dict(block.input)
        out = {}
        for m in data.get("matches") or []:
            cand = by_id.get(m.get("candidate_id"))
            if cand is not None and m.get("text"):
                out[_norm(m["text"])] = cand
        return out, round(cost, 6)
    except Exception:  # noqa: BLE001
        return {}, 0.0


def resolve_addons(raw: dict, abbrev: str, ref: ReferenceData, reroutes: list[tuple],
                   year: int | None = None, client=None) -> dict:
    cands = ref.license_candidates(abbrev, "addon_type")
    base_conf = conf_of(raw, "addon_type")
    sources: list[tuple[str, float, bool]] = [(it, base_conf, False) for it in (raw.get("addon_type") or [])]
    for dim, canonical, text, conf in reroutes:
        if dim == "addon_type":
            sources.append((text, conf, True))            # came in under the wrong dimension
    out, seen = [], set()
    for text, conf, rerouted in sources:
        res = match_addon_item(text, conf, cands, year)
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

    # Second pass: only for items that missed, against the era-gated candidate list.
    sp_cost = 0.0
    misses = [r for r in out if r["value"] is None and r.get("source_text")]
    if SECOND_PASS and client is not None and misses:
        gated = [c for c in cands if _addon_in_range(c, year)]
        mapping, sp_cost = second_pass_addons(
            client, raw.get("raw_text_transcription", ""),
            [str(r["source_text"]) for r in misses], gated, year,
        )
        for r in misses:
            cand = mapping.get(_norm(r["source_text"]))
            if cand is not None and cand["id"] not in {x["value"] for x in out if x["value"] is not None}:
                r.update(_hit(cand, r["source_text"], max(r["conf"], 0.7), 90))
                r["tier"] = _cap(r["tier"], "medium")     # model-chosen from a closed set
                r["second_pass"] = True

    # Per-item results are the contract; the aggregate reflects the BEST match so a
    # good item is never hidden by an unmatched sibling (the old _min_tier bug).
    matched = [r for r in out if r["value"] is not None]
    return {
        "value": [r["value"] for r in matched],
        "name": ", ".join(r["name"] for r in matched) or None,
        "source_text": ", ".join(str(r["source_text"]) for r in out if r["source_text"]),
        "score": max((r["score"] for r in matched), default=0),
        "conf": base_conf,
        "tier": ORDER[max((ORDER.index(r["tier"]) for r in matched), default=0)],
        "inferred": any(r["inferred"] for r in out),
        "items": out,
        "second_pass_cost_usd": sp_cost,
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


SERIAL_INTERIOR_O_RE = re.compile(r"(?<=\d)O(?=\d)")


def validate_serial(field: dict, abbrev: str) -> dict:
    """Domain prior: PA back-tag serials are digits with at most one letter, so an
    interior O between digits is almost certainly a zero. Auto-correct and flag."""
    val = field.get("value")
    if not val or abbrev != "PA":
        return field
    s = str(val).strip().upper()
    corrected = SERIAL_INTERIOR_O_RE.sub("0", s)
    if corrected != s:
        field = dict(field)
        field.update({"value": corrected, "name": corrected, "corrected_from": s, "tier": "low"})
    return field


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


def resolve(raw: dict, ref: ReferenceData, client=None) -> dict:
    """Resolve a raw VLM extraction into a tier-tagged, form-ready payload.

    `client` is optional — when present, unmatched add-ons get the constrained
    second-pass re-match (SECOND_PASS gate)."""
    kind = str(raw.get("item_kind") or "unknown").lower()
    state = ref.state(raw.get("state_name_or_abbrev"))
    sconf = conf_of(raw, "state_name_or_abbrev")
    state_inferred = False

    # Domain prior: the "Co. NN / COUNTY NUMBER NN" format is uniquely PA
    # (1913-1937 county-numbered tags) — resolves state even when no state name was read.
    if state is None:
        blob = f'{raw.get("geographic_unit_name") or ""} {raw.get("raw_text_transcription") or ""}'
        if COUNTY_NUM_RE.search(blob):
            state = ref.states_by_key.get("PA")
            if state:
                state_inferred = True
                sconf = max(sconf, 0.7)
    abbrev = state["abbrev"] if state else ""

    fields: dict[str, dict] = {}
    if state:
        fields["state"] = {
            "value": state["id"], "name": state["name"],
            "source_text": raw.get("state_name_or_abbrev") or ("(inferred: COUNTY NUMBER format => PA)" if state_inferred else None),
            "score": 100, "conf": sconf,
            "tier": _cap(tier_for(sconf, 100), "medium") if state_inferred else tier_for(sconf, 100),
            "inferred": state_inferred,
        }
    else:
        fields["state"] = _blank(raw.get("state_name_or_abbrev"), sconf)
    fields["geographic_unit"] = resolve_geo(raw, abbrev, ref)
    fields["license_year"] = resolve_year(raw, state)

    year_value = fields["license_year"]["value"]
    year_ok = year_value is not None and fields["license_year"]["tier"] != "unmatched"
    year = int(year_value) if year_ok else None

    # era is redundant (and confusing to render) once a real year resolved
    fields["era_guess"] = _blank(None, 0.0) if year_ok else _direct(
        raw.get("era_guess"), conf_of(raw, "era_guess"), max_tier="medium",
    )
    fields["serial_number"] = validate_serial(
        _direct(raw.get("serial_number"), conf_of(raw, "serial_number"), max_tier="low"), abbrev,
    )
    fields["is_statewide"] = _direct(raw.get("is_statewide"), conf_of(raw, "is_statewide"))
    fields["item_kind"] = _direct(
        kind if kind in {"license", "addon"} else None, conf_of(raw, "item_kind"),
    )

    reroutes: list[tuple] = []
    for field in SINGLE_DIMENSIONS:
        # A standalone add-on has no activity scope or duration of its own —
        # never prefill them (acceptance #8); the addon_type IS the item.
        if kind == "addon" and field in {"activity_scope", "duration"}:
            fields[field] = _blank(None, 0.0)
            continue
        res, rr = resolve_dimension(raw, field, abbrev, ref)
        fields[field] = res
        if rr:
            reroutes.append(rr)

    fields["addon_type"] = resolve_addons(raw, abbrev, ref, reroutes, year=year, client=client)
    fields["colors"] = resolve_colors(raw.get("dominant_colors"), conf_of(raw, "dominant_colors"))
    fields["shape"] = resolve_shape(raw.get("shape"), conf_of(raw, "shape"))

    for f in set(raw.get("inferred_fields") or []):       # honor the model's own inference flags
        if f in fields and fields[f].get("value") is not None:
            fields[f]["inferred"] = True
            fields[f]["tier"] = _cap(fields[f]["tier"], "medium")

    if ALLOW_INFERENCE and kind != "addon":
        apply_inferences(fields, abbrev, ref)

    return {
        "state_abbrev": abbrev,
        "item_kind": kind,
        "lot_detected": kind == "lot",                    # UI guidance only — never written to the DB
        "fields": fields,
        "raw_text": raw.get("raw_text_transcription", ""),
        "context_text": raw.get("context_text") or "",
        "second_pass_cost_usd": fields["addon_type"].get("second_pass_cost_usd", 0.0),
    }
