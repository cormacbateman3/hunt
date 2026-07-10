Image Prefill - Dev Plan
1. Architecture
Three components, clean seam between them:
A. prefill/ Python package — pure logic, no Django, no AWS. Takes (image_bytes, controlled_vocab_context) → returns structured extraction JSON. Runs identically in Lambda and in local Django.
B. Lambda handler — thin wrapper around the package. Reads image from S3, calls Bedrock (Claude Haiku 4.5), returns JSON. ~40 lines.
C. Django service layer — receives Lambda response, resolves raw values to DB entities (State, GeographicUnit, LicenseType), assigns confidence tiers, returns prefill payload to frontend.
This keeps the VLM call at the edge (cheap, stateless, scalable) and the taxonomy matching in Django (where the DB lives).
2. Request Flow
Async with polling. The sync path feels snappy in dev but cold-start + VLM latency = 3–8s in prod, which is too long to block a form.
1.	User uploads image to POST /api/prefill/jobs/ — Django saves image to S3, creates PrefillJob(status=pending), invokes Lambda asynchronously with the S3 key and job ID, returns job_id.
2.	Lambda resizes image (max 1568px long edge — Claude's optimal), calls Bedrock with structured prompt, writes raw extraction back to PrefillJob.raw_extraction, sets status to resolving.
3.	Django post-processes: resolves raw → DB entities, computes confidence tiers, writes PrefillJob.resolved_payload, sets status to complete.
4.	Frontend polls GET /api/prefill/jobs/{job_id}/ every 750ms. On complete, applies payload to form using the tier rules.
Typical end-to-end: 2–4s. Frontend shows a subtle "Analyzing image…" shimmer on the dimension fields during this window.
3. Data Model
New models in apps/core/ (or apps/prefill/ if you want it isolated):
class PrefillJob(models.Model):
    STATUS = [('pending','pending'),('resolving','resolving'),
              ('complete','complete'),('failed','failed')]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    image_s3_key = models.CharField(max_length=500)
    source_form = models.CharField(max_length=20, choices=[('listing','listing'),('collection','collection')])
    status = models.CharField(max_length=20, choices=STATUS, default='pending')
    raw_extraction = models.JSONField(null=True, blank=True)      # VLM output
    resolved_payload = models.JSONField(null=True, blank=True)    # tier-tagged, form-ready
    model_version = models.CharField(max_length=50, blank=True)   # e.g. "claude-haiku-4-5"
    prompt_version = models.CharField(max_length=20, blank=True)  # for A/B and debugging
    cost_usd = models.DecimalField(max_digits=8, decimal_places=5, null=True)
    latency_ms = models.IntegerField(null=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True)
    # Audit linkage once form is saved:
    resulting_listing = models.ForeignKey('listings.Listing', null=True, blank=True, on_delete=models.SET_NULL)
    resulting_collection_item = models.ForeignKey('collections.CollectionItem', null=True, blank=True, on_delete=models.SET_NULL)

class PrefillCorrection(models.Model):
    """Logged diff between what AI suggested and what the user submitted. Gold for future tuning."""
    job = models.ForeignKey(PrefillJob, on_delete=models.CASCADE, related_name='corrections')
    field_name = models.CharField(max_length=50)
    suggested_value = models.JSONField()     # can be scalar or list for M2M
    final_value = models.JSONField()
    tier = models.CharField(max_length=10)   # 'high' | 'medium' | 'low' | 'unmatched'
    was_accepted = models.BooleanField()
    was_cleared = models.BooleanField(default=False)
Rate limit: max 30 PrefillJobs per user per hour. Enforce in the view.
4. The VLM Call
Model: Claude Haiku 4.5 via AWS Bedrock (anthropic.claude-haiku-4-5). Keeps you in AWS, no extra vendor. If Bedrock region/quota is a blocker, fall back to the Anthropic API — the request shape is identical.
Cost: ~$0.005–0.008 per image including vision tokens + schema prompt + output. At 1,000 prefills/month ≈ $5–8/month.
Prompt strategy — two passes, one call. First pass the model identifies state + obvious fields in one call. You send all states but only a short hint for license types ("will be narrowed to state"). Once the state is identified, your Django matcher filters LicenseType + GeographicUnit to just that state — no second model call needed because the first call also returns raw names that your matcher resolves against the narrowed set.
Tool-use schema (enforces output shape):
EXTRACTION_TOOL = {
    "name": "extract_license_fields",
    "description": "Extract fields from an antique hunting/fishing license image.",
    "input_schema": {
        "type": "object",
        "properties": {
            "state_name_or_abbrev": {"type": ["string", "null"]},
            "license_year": {"type": ["integer", "null"]},
            "era_guess": {"type": ["string", "null"], "enum": ["Pre-1920","1920s","1930s","1940s","1950s","1960s","1970s","1980s","1990s","2000s", None]},
            "geographic_unit_name": {"type": ["string","null"], "description": "County, WMU, GMU, etc. as written on the license. Null if statewide."},
            "is_statewide": {"type": "boolean"},
            "residency": {"type": ["string","null"], "description": "Resident / Nonresident / Alien etc."},
            "holder_eligibility": {"type": ["string","null"]},
            "activity_scope": {"type": ["string","null"]},
            "duration": {"type": ["string","null"]},
            "addon_type": {"type": ["string","null"]},
            "serial_number": {"type": ["string","null"]},
            "material": {"type": ["string","null"], "enum": ["Paper/Cardstock","Metal Button","Metal Tag","Celluloid","Fabric/Canvas","Plastic", None]},
            "shape": {"type": ["string","null"], "enum": ["Rectangle","Square","Button/Disc","Tag (with hole)","Strip","Irregular/Custom", None]},
            "dominant_colors": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
            "condition_visual": {"type": ["string","null"], "enum": ["poor","fair","good","very_good","excellent","mint", None]},
            "raw_text_transcription": {"type": "string", "description": "Everything legible on the license, used for audit and suggestion fallback."},
            "per_field_confidence": {
                "type": "object",
                "description": "Self-rated confidence 0.0-1.0 per extracted field."
            }
        },
        "required": ["raw_text_transcription", "per_field_confidence"]
    }
}
Key prompt rules in the system message:
•	"Return null for any field you cannot read with reasonable confidence. Do not guess."
•	"For per_field_confidence: 0.9+ = text is clearly visible and you are certain; 0.6–0.9 = partially legible or inferred from context; below 0.6 = guess."
•	"Serial numbers are often handwritten — transcribe exactly as you see them, character by character, never infer missing digits."
•	"For raw_text_transcription include everything, even text you couldn't map to a field — this helps humans verify."
Version the prompt string and store its hash in PrefillJob.prompt_version. When you iterate, you can measure correction rates per version.
5. Resolution & Confidence Tiers
After the VLM returns, Django runs resolve_extraction(raw) → resolved_payload. This is where taxonomy matching lives.
Per-field resolution rules:
Field	Resolution
license_year	Integer. High if VLM confidence ≥0.85 AND year is within State.min_license_year to current year. Medium if outside that window.
era_label	Auto-derived from year if present; else use era_guess with medium tier.
state	Exact match on State.name or State.code via iexact. High if exact + VLM confidence ≥0.85.
county_ref	GeographicUnit.objects.filter(state=X).filter(name__iexact=raw). Fuzzy fallback with rapidfuzz.fuzz.WRatio ≥90 → medium, ≥80 → low, else unmatched. If is_statewide=True from VLM, resolve to the Statewide row.
license_types (M2M)	Match each dimension (residency, duration, eligibility, activity_scope, addon_type) independently against LicenseType.objects.filter(state=X, category=Y, is_system_value=True). Same fuzzy thresholds.
resident_status	Controlled choices — exact or fuzzy on choices list.
condition_grade	Always medium tier at best — the user should physically verify condition. Never high.
serial_number	Always low tier. Handwriting + hallucination risk. Always shown as ghost suggestion, never auto-filled.
shape, colors, material	Controlled vocab, exact match.
Tier thresholds (combine VLM self-confidence with DB match quality):
def tier_for(vlm_conf, db_match_score):
    if vlm_conf >= 0.85 and db_match_score >= 95:  return "high"
    if vlm_conf >= 0.65 and db_match_score >= 80:  return "medium"
    if vlm_conf >= 0.40:                            return "low"
    return "unmatched"
These thresholds are stored as constants and will be tuned from correction data. Expose them in Django settings so you can adjust without a deploy.
Payload shape returned to frontend:
{
  "status": "complete",
  "fields": {
    "license_year": { "tier": "high", "value": 1924, "source_text": "1924" },
    "state": { "tier": "high", "value": {"id": 38, "name": "Pennsylvania"}, "source_text": "Commonwealth of Pennsylvania" },
    "county_ref": { "tier": "medium", "value": {"id": 1203, "name": "Bucks"}, "source_text": "Bucks Co.", "match_score": 88 },
    "license_types": [
      { "tier": "high", "value": {"id": 501, "name": "Resident", "category": "residency"}, "source_text": "Resident" },
      { "tier": "low", "value": null, "source_text": "Antlerless Deer Permit", "suggestion_eligible": true }
    ],
    "serial_number": { "tier": "low", "value": null, "source_text": "A-44921" }
  },
  "raw_text": "...",
  "unmatched": [
    { "field": "license_types", "source_text": "Antlerless Deer Permit", "category_guess": "addon" }
  ]
}
6. Handling Unmatched Extractions
Use your existing ReferenceDataSuggestion flow. When resolution can't find a DB entity for extracted text:
UI: a dismissable panel under the form titled "We read these values but couldn't match them":
We extracted "Antlerless Deer Permit" from your image but don't have this value in our system yet. [ Suggest this value ] [ Ignore ]
On "Suggest this value": create a ReferenceDataSuggestion:
•	user = current user
•	suggestion_type = "new_value"
•	target_model = "license_type" (or whichever)
•	proposed_value = "Antlerless Deer Permit"
•	source_or_evidence = f"Extracted by image prefill from PrefillJob #{job.id}"
•	status = "pending"
Also: if the extracted value has VLM confidence ≥0.85 AND three or more distinct users have had the same unmatched extraction, auto-create a high-priority suggestion flagged for admin. This is your passive taxonomy-improvement signal.
Important: never silently inject unmatched text into LicenseType or GeographicUnit — that pollutes filters. Always route through the suggestion queue per your existing Filter Cleanliness Rule.
7. Frontend Behavior
Three render states per field, driven by tier:
high      → value prefilled, normal styling, no indicator
medium    → value prefilled, small "✨ AI-suggested" badge next to label,
            one-click clear button (x) on the right of the input
low       → empty field, ghost-text placeholder "Did you mean: Bucks?"
            clicking the placeholder accepts; typing replaces it
unmatched → empty field + entry in the "Couldn't match" panel
Critical behavior rules:
•	Never overwrite user-typed content. If a field has been edited since page load, skip prefill for that field. Track this client-side with a dirty flag per field.
•	Make the clear button visible, not hidden. On medium-tier prefills, users should be able to reject with one click.
•	Surface the source text on hover. "AI read this as 'Bucks Co.' from your image" — builds trust and helps verification.
•	Disclosure copy at top of form (both listing and collection): "Fields below were suggested from your image. Please verify — AI suggestions can be wrong, and listings are your responsibility."
•	Log corrections on form submit. Diff the final form values against the prefill payload. For every changed field, create a PrefillCorrection row.
8. Lambda Implementation
# lambda/prefill_handler.py
import boto3, json, os
from prefill.extractor import extract_license_fields  # your shared package

s3 = boto3.client('s3')
bedrock = boto3.client('bedrock-runtime', region_name=os.environ['BEDROCK_REGION'])

def handler(event, context):
    job_id = event['job_id']
    s3_key = event['s3_key']
    bucket = os.environ['IMAGE_BUCKET']
    
    img = s3.get_object(Bucket=bucket, Key=s3_key)['Body'].read()
    result = extract_license_fields(img, bedrock_client=bedrock)
    
    # POST back to Django with job result; Django finalizes resolution.
    return {
        'job_id': job_id,
        'raw_extraction': result.raw,
        'model_version': result.model_version,
        'cost_usd': result.cost_usd,
        'latency_ms': result.latency_ms,
    }
Deploy config:
•	Runtime: Python 3.12
•	Memory: 1024 MB
•	Timeout: 30s
•	Concurrency cap: 10 (prevents runaway costs)
•	Invocation: async from Django via boto3.client('lambda').invoke(InvocationType='Event', ...). Lambda writes results back to Django via a signed POST to an internal webhook, or Django polls DynamoDB / S3 for the result JSON — pick whichever matches your existing patterns. Webhook is cleaner.
•	IAM: s3:GetObject on image bucket, bedrock:InvokeModel on Haiku model ARN, outbound HTTPS to your Django webhook.
•	Env vars: BEDROCK_REGION, IMAGE_BUCKET, DJANGO_WEBHOOK_URL, DJANGO_WEBHOOK_SECRET.
Local dev parity: Django checks settings.PREFILL_BACKEND — if "local", it imports prefill.extractor directly and runs it in-process (uses Anthropic API key from .env). If "lambda", it invokes Lambda. Same prefill package in both paths — zero code drift between dev and prod.
9. Observability
Log to PrefillJob: model, prompt version, cost, latency, per-field tier distribution. Add a Django admin view "Prefill Analytics" showing:
•	Prefills per day, cost per day
•	Tier distribution (what % high vs medium vs low vs unmatched)
•	Top 20 unmatched extractions (drives taxonomy improvements)
•	Correction rate per field (if final_value != suggested_value, that field's accuracy is down)
•	Correction rate per prompt version (regression guard when iterating prompt)
10. Security & Abuse
•	Rate limit: 30 prefill jobs/user/hour, 200/day. Enforce in the view before Lambda invoke.
•	Image validation: reject non-image MIME, >10MB files, dimensions <200px before Lambda.
•	PII scrub: raw_text often contains names and addresses from old licenses. Don't log raw_text in CloudWatch. Keep it in the DB where it's access-controlled.
•	Webhook auth: HMAC-sign Lambda → Django callbacks with a shared secret.
11. Rollout
Phase 0 — shared package + Lambda skeleton (1–2 days). Build prefill/ package, stub Lambda, wire local Django → package path. No UI yet. Unit tests on matcher with synthetic raw extractions.
Phase 1 — internal eval (2–3 days). Admin-only feature flag. Collect 30–50 real images across materials (paper, metal button, celluloid, handwritten). Run prefill, measure tier accuracy by hand. Tune prompt and thresholds.
Phase 2 — collection form beta (1 week). Ship to collection form first (lower stakes). Opt-in via user setting. Log all corrections. Run for 2–3 weeks, aim for <15% correction rate on high-tier and <40% on medium-tier fields.
Phase 3 — listing form + default on (3–5 days). Extend to listing form. Flip default to on. Keep opt-out in user settings. Add the prominent verification disclosure copy.
Phase 4 — iterate from data. Use PrefillCorrection + top unmatched extractions to tune prompt, promote admin-approved suggestions, and consider fine-tuning only if volume justifies it (unlikely before 10k+ prefills).
12. Out of Scope for v1
•	Image preprocessing (crop/deskew) — Haiku handles reasonable variation. Revisit only if accuracy on angled/background-heavy photos is poor.
•	Fine-tuning — too early without correction volume.
•	Multi-image prefill — one image per job for v1. If user uploads 4 images, use the one marked as featured.
•	Auto-populating title/description — let the user write these; AI-generated titles feel spammy in collector marketplaces.
________________________________________
That's the full plan. The two pieces most worth landing cleanly up front are (a) the prefill/ package boundary — same code in Lambda and Django, no drift — and (b) the PrefillJob + PrefillCorrection schema, because those are what let you prove the feature is working and iterate on it. Everything else can flex.
