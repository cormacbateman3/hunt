/* KeystoneBid image prefill — the ledger (Add Item Ideas 4a–4e).
 *
 * Wire-up (per form):
 *   KBPrefill.init({
 *     createUrl, correctionsUrlTemplate, suggestionUrl, source: 'collection'|'listing',
 *     fileInput: '#id_featured_image',
 *     jobIdInput: '#prefill-job-id',
 *     panel: '#prefill-panel',
 *     form: 'form',
 *     fields: { state: {sel:'#id_state', kind:'select'}, ... },
 *     lines: {bench:[...], object:[...], lookup:{...}, closing:[...], winks:[...],
 *             still_reading:'...', reduced_motion:'Reading'},   // ledger_lines.json
 *     forYou: [{name:'condition', kind:'radio', groupName:'condition_grade'}, ...],
 *     overlayHost: '[data-slot="front"]',   // where the scan animation plays
 *   });
 *
 * The contract, from the drawing:
 *   - No job → no panel. pending/resolving → typed line + rows arriving.
 *     complete → tally replaces the line. failed → couldn't-read card, panel stays.
 *   - High/medium rows: green ✓ with "change". Flagged rows: amber with a
 *     ✓/× pair. ✓ accepts, × clears the field. Both write a PrefillCorrection
 *     on click, with five seconds of undo. Low: a "Use it" chip. Unmatched:
 *     the word it read, and "Suggest it".
 *   - While reading, only the read's target fields lock (aria-busy); the
 *     condition pair, material and anything price-shaped never lock, and
 *     Save is never blocked. Unlock on complete, failed, or the 12s mark.
 *   - Four lines × 1.5s; return early → cut to the closing line. Past 8s
 *     hold; past 12s say still-reading plainly. One wink per read, never on
 *     a flagged or failed read, never on a collector's first.
 *   - Never overwrites a field the user has edited (dirty tracking).
 */
(function () {
    'use strict';

    const FIELD_LABELS = {
        item_kind: 'Item kind', state: 'State', license_year: 'Year', era_guess: 'Era',
        geographic_unit: 'County / unit', residency: 'Residency', holder_eligibility: 'Who it was for',
        activity_scope: 'What it allowed', duration: 'How long it lasted', material: 'Material',
        addon_type: 'Add-on', shape: 'Shape', colors: 'Colours', serial_number: 'Serial',
    };

    // Fields the read may fill but must wait for lookup-built options.
    const DEFERRED = ['geographic_unit', 'residency', 'holder_eligibility',
                      'activity_scope', 'duration', 'material', 'addon_type'];

    const LINE_MS = 1500;      // one line's slot
    const HOLD_MS = 8000;      // past this, hold the last line
    const PLAIN_MS = 12000;    // past this, say it plainly and unlock
    const UNDO_MS = 5000;

    function csrfToken() {
        const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (input && input.value) return input.value;
        const m = document.cookie.match('(^|;)\\s*csrftoken\\s*=\\s*([^;]+)');
        return m ? decodeURIComponent(m.pop()) : '';
    }

    function el(sel) {
        if (!sel || sel === '#') return null;
        try { return document.querySelector(sel); } catch (err) { return null; }
    }

    function esc(value) {
        return String(value ?? '')
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    /* Deterministic per-job picks — a retry (new job id) reads differently. */
    function seeded(seed) {
        let s = (seed || 1) >>> 0;
        return () => {
            s = (s * 1664525 + 1013904223) >>> 0;
            return s / 4294967296;
        };
    }

    function pick(rand, list) {
        if (!list || !list.length) return '';
        return list[Math.floor(rand() * list.length)] || '';
    }

    class Prefill {
        constructor(cfg) {
            this.cfg = cfg;
            this.lines = cfg.lines || null;
            this.jobId = null;
            this.payload = null;
            this.facts = {};
            this.applied = {};   // field -> {suggested, tier, name, flagged}
            this.cleared = {};
            this.dirty = {};
            this.initial = {};
            this.applying = false;
            this.rows = [];      // ledger rows in resolution order
            this.pendingCorrections = {};   // field -> {timer, body, undo}
            this.sentCorrections = {};      // field -> final we already logged
            this.attempt = 0;
            this.reducedMotion = window.matchMedia
                && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

            this.panel = el(cfg.panel);
            this.fileInput = el(cfg.fileInput);
            this.form = el(cfg.form) || (this.fileInput && this.fileInput.form);
            if (!this.fileInput || !this.form) return;

            for (const [field, spec] of Object.entries(cfg.fields)) {
                const node = this.node(field);
                if (!node) continue;
                this.initial[field] = this.read(field);
                if (cfg.protectInitial && this.initial[field]) this.dirty[field] = true;
                const mark = () => { if (!this.applying) this.dirty[field] = true; };
                ((spec.kind === 'radio' || spec.kind === 'checklist') ? this.group(field) : [node]).forEach(n => {
                    n.addEventListener('input', mark);
                    n.addEventListener('change', mark);
                });
            }

            // The "for you" fields feed the tally and never lock.
            (cfg.forYou || []).forEach(spec => {
                this.forYouNodes(spec).forEach(n => {
                    n.addEventListener('input', () => this.renderTally());
                    n.addEventListener('change', () => this.renderTally());
                });
            });

            this.fileInput.addEventListener('change', () => {
                const file = this.fileInput.files && this.fileInput.files[0];
                if (!file) {
                    // The front photograph was removed. Mid-read that means
                    // the evidence is gone — abort rather than apply values
                    // from a photograph that no longer exists. A settled
                    // ledger stays: its rows describe values already in
                    // the form.
                    if (this.locked) this.abort();
                    return;
                }
                const key = file.name + ':' + file.size;
                if (key === this.lastFileKey) return;
                this.lastFileKey = key;
                this.lastFile = file;
                this.start(file);
            });

            this.form.addEventListener('submit', () => {
                this.flushCorrections(true);
                this.logCorrections();
            });
            window.addEventListener('pagehide', () => this.flushCorrections(true));

            // A failed submit reloads the page, but the read already
            // happened — the server hands the job back and the ledger
            // settles straight in, describing the values the form kept.
            if (cfg.resume) this.resumeFromState(cfg.resume);
        }

        resumeFromState(state) {
            if (!state || state.status !== 'complete' || !state.payload) return;
            this.jobId = state.job_id;
            const jobInput = el(this.cfg.jobIdInput);
            if (jobInput) jobInput.value = state.job_id;
            this.payload = state.payload;
            this.facts = state.line_facts || {};
            this.rand = seeded((state.job_id || 1) * 2654435761);
            this.lowHints = [];
            this.missHints = [];
            this.extraHints = [];
            this.lotHint = !!state.payload.lot_detected;
            for (const [field, data] of Object.entries(state.payload.fields || {})) {
                const spec = this.cfg.fields[field];
                if (!spec || field === 'addon_type') continue;
                if (!data || data.value === null || data.value === undefined) continue;
                const current = this.read(field);
                if (String(data.value) === String(current) || (data.name && data.name === current)) {
                    const flagged = data.check !== undefined
                        ? !!data.check
                        : (!!data.inferred || !!data.second_pass);
                    // Submitting was the quiet confirmation — flagged rows
                    // come back accepted rather than re-amber.
                    this.applied[field] = {
                        suggested: data.value, tier: data.tier, name: data.name,
                        flagged, accepted: flagged || undefined,
                    };
                    this.rows.push(field);
                } else if (data.tier === 'low') {
                    this.lowHints.push({ field, data });
                }
            }
            for (const miss of state.payload.unmatched || []) {
                if (!this.missHints.some(h => h.source === miss.source_text)) {
                    this.missHints.push({ field: miss.field, source: String(miss.source_text) });
                }
            }
            this.reveal();
            this.settle();
        }

        /* ── field plumbing ──────────────────────────────────────────── */

        node(field) {
            const spec = this.cfg.fields[field];
            if (!spec) return null;
            if (spec.kind === 'radio' || spec.kind === 'checklist') return this.group(field)[0] || null;
            return el(spec.sel);
        }

        group(field) {
            const spec = this.cfg.fields[field];
            return Array.from(this.form.querySelectorAll(`input[name=${spec.name}]`));
        }

        radios(field) { return this.group(field); }

        read(field) {
            const spec = this.cfg.fields[field];
            if (spec.kind === 'radio') {
                const checked = this.radios(field).find(r => r.checked);
                return checked ? checked.value : '';
            }
            if (spec.kind === 'checklist') {
                return this.group(field).filter(i => i.checked).map(i => i.value).join(',');
            }
            const node = el(spec.sel);
            if (!node) return '';
            if (spec.kind === 'multiselect') {
                return Array.from(node.selectedOptions || []).map(o => o.value).join(',');
            }
            return node.value;
        }

        forYouNodes(spec) {
            if (spec.kind === 'radio') {
                return Array.from(this.form.querySelectorAll(`input[name=${spec.groupName}]`));
            }
            const node = el(spec.sel);
            return node ? [node] : [];
        }

        forYouEmpty(spec) {
            if (spec.kind === 'radio') {
                // A checked "Not set" rung is still an empty answer.
                return !this.forYouNodes(spec).some(n => n.checked && n.value);
            }
            const node = this.forYouNodes(spec)[0];
            return !node || !String(node.value || '').trim();
        }

        fieldLabel(field) {
            const spec = this.cfg.fields[field] || {};
            // The drawing: row labels come from the form's labels.
            const drawn = this.form.querySelector(`[data-taxonomy-label="${field}"]`);
            if (drawn) return drawn.textContent.trim();
            if (spec.sel) {
                const node = el(spec.sel);
                if (node && node.id) {
                    const label = this.form.querySelector(`label[for="${node.id}"]`);
                    if (label) return label.textContent.trim().replace(/\s+/g, ' ');
                }
            }
            return FIELD_LABELS[field] || field;
        }

        wrapOf(field) {
            const spec = this.cfg.fields[field] || {};
            const anchor = (spec.kind === 'radio' || spec.kind === 'checklist')
                ? (this.group(field)[0] || {}).parentElement
                : el(spec.sel);
            return anchor ? anchor.closest('.if-field') : null;
        }

        /* ── the lock (4e): only the read's targets, never the rest ───── */

        lockFields() {
            for (const field of Object.keys(this.cfg.fields)) {
                const spec = this.cfg.fields[field];
                const nodes = (spec.kind === 'radio' || spec.kind === 'checklist')
                    ? this.group(field) : [el(spec.sel)].filter(Boolean);
                nodes.forEach(n => { n.disabled = true; });
                const wrap = this.wrapOf(field);
                if (wrap) {
                    wrap.classList.add('is-reading');
                    wrap.setAttribute('aria-busy', 'true');
                }
            }
            this.locked = true;
        }

        unlockFields() {
            if (!this.locked) return;
            for (const field of Object.keys(this.cfg.fields)) {
                const spec = this.cfg.fields[field];
                const nodes = (spec.kind === 'radio' || spec.kind === 'checklist')
                    ? this.group(field) : [el(spec.sel)].filter(Boolean);
                nodes.forEach(n => { n.disabled = false; });
                const wrap = this.wrapOf(field);
                if (wrap) {
                    wrap.classList.remove('is-reading');
                    wrap.removeAttribute('aria-busy');
                }
            }
            this.locked = false;
        }

        settleFlash(field) {
            const wrap = this.wrapOf(field);
            if (!wrap) return;
            wrap.classList.add('is-settled');
            setTimeout(() => wrap.classList.remove('is-settled'), 1400);
        }

        /* ── the panel frame ─────────────────────────────────────────── */

        reveal() {
            const card = this.panel && this.panel.closest('[data-prefill-card]');
            if (card) card.hidden = false;
        }

        frame(metaText) {
            // The header lives outside this.panel in the template; only the
            // meta slot is ours to change.
            const card = this.panel && this.panel.closest('[data-prefill-card]');
            if (!card) return;
            const meta = card.querySelector('.if-panel-meta');
            if (meta && metaText != null) meta.textContent = metaText;
        }

        /* A run that is no longer current must change nothing. */
        abort() {
            this.runToken = (this.runToken || 0) + 1;
            this.stopShow();
            this.unlockFields();
            const card = this.panel && this.panel.closest('[data-prefill-card]');
            if (card) card.hidden = true;   // back to state 1: no photograph, no ledger
            if (this.panel) this.panel.innerHTML = '';
            this.lastFileKey = null;
        }

        /* ── the show: typed lines, one caret (4b/4d) ───────────────── */

        startShow(seedBase) {
            this.reveal();
            // The read announces itself where it happens — if the ledger
            // sits below the fold when the upload lands, bring it up.
            const card = this.panel && this.panel.closest('[data-prefill-card]');
            if (card) {
                card.scrollIntoView({
                    block: 'nearest',
                    behavior: this.reducedMotion ? 'auto' : 'smooth',
                });
            }
            this.frame('writing');
            this.showDone = false;
            this.showStart = Date.now();
            this.panel.innerHTML =
                '<div class="pf-line" data-pf-line><span class="pf-line-text"></span><span class="pf-caret" aria-hidden="true"></span></div>' +
                '<div class="pf-rows" data-pf-rows></div>';
            this.lineEl = this.panel.querySelector('.pf-line-text');
            this.rowsEl = this.panel.querySelector('[data-pf-rows]');

            if (!this.lines || this.reducedMotion) {
                this.lineEl.textContent = (this.lines && this.lines.reduced_motion) || 'Reading';
                const caret = this.panel.querySelector('.pf-caret');
                if (caret) caret.hidden = true;
                return;
            }
            this.rand = seeded(seedBase);
            this.queue = [pick(this.rand, this.lines.bench)];
            this.lineIndex = 0;
            this.typed = 0;
            this.cutting = false;
            this.showTimer = setInterval(() => this.tickShow(), 50);
            this.startOverlay(seedBase);
        }

        planRemainingLines() {
            // Slots two and three: object lines, upgraded to lookup lines
            // when the fact has landed. Slot four: the wink or a closing.
            if (!this.lines) return;
            const rand = this.rand;
            const facts = this.facts || {};
            const lookups = [];
            if (facts.era_fact) lookups.push(facts.era_fact);
            if (facts.unit_plural && facts.state_name
                && !/count(y|ies)/i.test(facts.unit_label || '')) {
                lookups.push(pick(rand, this.lines.lookup.unit)
                    .replace('{state_name}', facts.state_name)
                    .replace('{unit_plural}', facts.unit_plural));
            }
            if (facts.county_name && facts.site_count > 1) {
                lookups.push((this.lines.lookup.counts[0] || '')
                    .replace('{site_count}', String(facts.site_count))
                    .replace('{county_name}', facts.county_name));
            } else if (facts.county_name && facts.site_count === 0) {
                lookups.push(this.lines.lookup.counts[1] || '');
            }
            const two = lookups.length ? lookups[0] : pick(rand, this.lines.object);
            const three = lookups.length > 1 ? lookups[1] : pick(rand, this.lines.object);
            this.queue.push(two, three);

            // One wink per read — never on a flagged or failed read, never
            // on a collector's first of anything (4d/4e).
            const anyFlagged = Object.values(this.applied).some(a => a.flagged);
            const anyLow = (this.lowHints || []).length > 0;
            const first = facts.my_county_count === 0;
            if (!anyFlagged && !anyLow && !first && this.lines.winks.length) {
                this.queue.push(pick(rand, this.lines.winks));
            } else {
                this.queue.push(pick(rand, this.lines.closing));
            }
        }

        tickShow() {
            if (!this.lineEl) return;
            const elapsed = Date.now() - this.showStart;

            if (this.showDone && !this.cutting) {
                // The job returned — cut to the closing line, never pad.
                this.cutting = true;
                this.queue = [this.closingLine()];
                this.lineIndex = 0;
                this.typed = 0;
            }
            if (elapsed > PLAIN_MS && !this.showDone) {
                this.lineEl.textContent = this.lines.still_reading;
                this.unlockFields();
                return;
            }

            const msg = this.queue[this.lineIndex] || '';
            if (this.typed < msg.length) {
                this.typed = Math.min(msg.length, this.typed + 3);
                this.lineEl.textContent = msg.slice(0, this.typed);
                return;
            }
            if (this.cutting) {
                if (!this.cutAt) this.cutAt = Date.now();
                if (Date.now() - this.cutAt > 900) this.settle();
                return;
            }
            // Line finished — move on after its slot, but past 8s hold.
            if (elapsed > HOLD_MS) return;
            const slotEnd = (this.lineIndex + 1) * LINE_MS;
            if (elapsed >= slotEnd && this.lineIndex < this.queue.length - 1) {
                this.lineIndex += 1;
                this.typed = 0;
            }
        }

        closingLine() {
            if (!this.lines) return '';
            const anyFlagged = Object.values(this.applied).some(a => a.flagged);
            const anyLow = (this.lowHints || []).length > 0;
            const first = (this.facts || {}).my_county_count === 0;
            if (!anyFlagged && !anyLow && !first && !this.winked && this.lines.winks.length) {
                this.winked = true;
                return pick(this.rand || seeded(1), this.lines.winks);
            }
            return pick(this.rand || seeded(1), this.lines.closing);
        }

        stopShow() {
            if (this.showTimer) { clearInterval(this.showTimer); this.showTimer = null; }
            this.stopOverlay();
        }

        /* ── the scan animation on the front slot (4b) ──────────────── */

        startOverlay(seed) {
            const host = el(this.cfg.overlayHost);
            if (!host) return;
            this.stopOverlay();
            const variant = this.reducedMotion ? 3 : (seed % 3);
            const overlay = document.createElement('div');
            overlay.className = 'pf-scan pf-scan--' + ['loupe', 'grid', 'sleeve', 'still'][variant];
            overlay.setAttribute('aria-hidden', 'true');
            if (variant === 0) {
                overlay.innerHTML = '<span class="pf-scan-tick pf-scan-tick--tl"></span>'
                    + '<span class="pf-scan-tick pf-scan-tick--br"></span>'
                    + '<span class="pf-loupe"></span>';
            } else if (variant === 1) {
                overlay.innerHTML = '<span class="pf-scan-sheet"></span><span class="pf-scan-sweep"></span>'
                    + '<span class="pf-scan-word">READING</span>';
            } else if (variant === 2) {
                overlay.innerHTML = '<span class="pf-sleeve"></span>';
            } else {
                overlay.innerHTML = '<span class="pf-scan-word">READING</span>';
            }
            host.appendChild(overlay);
            this.overlay = overlay;
        }

        stopOverlay() {
            if (this.overlay) { this.overlay.remove(); this.overlay = null; }
        }

        /* ── the run ─────────────────────────────────────────────────── */

        async fetchJSON(url, opts) {
            const resp = await fetch(url, opts);
            let data;
            try {
                data = await resp.json();
            } catch (err) {
                throw new Error('server error (HTTP ' + resp.status + ')');
            }
            if (!resp.ok) throw new Error(data.error || 'server error (HTTP ' + resp.status + ')');
            return data;
        }

        async start(file) {
            // One live run at a time: a replaced photograph or a removed one
            // bumps the token, and the stale run's awaited results are
            // dropped on the floor instead of applied to the wrong item.
            const token = this.runToken = (this.runToken || 0) + 1;
            this.attempt += 1;
            this.applied = {};
            this.cleared = {};
            this.rows = [];
            this.winked = false;
            this.facts = {};
            this.startShow(this.attempt * 7919);
            this.lockFields();

            const body = new FormData();
            body.append('image', file);
            body.append('source_form', this.cfg.source);
            let state;
            try {
                state = await this.fetchJSON(this.cfg.createUrl, {
                    method: 'POST', body,
                    headers: { 'X-CSRFToken': csrfToken() },
                });
                for (let i = 0; i < 40 && (state.status === 'pending' || state.status === 'resolving'); i++) {
                    if (token !== this.runToken) return;
                    await new Promise(r => setTimeout(r, 750));
                    state = await this.fetchJSON(this.cfg.createUrl + state.job_id + '/');
                }
            } catch (err) {
                if (token !== this.runToken) return;
                this.failed('Prefill unavailable: ' + err.message);
                return;
            }
            if (token !== this.runToken) return;
            if (state.status !== 'complete') {
                this.failed(state.error || '');
                return;
            }
            this.jobId = state.job_id;
            const jobInput = el(this.cfg.jobIdInput);
            if (jobInput) jobInput.value = state.job_id;
            this.payload = state.payload;
            this.facts = state.line_facts || {};
            // Reseed the LINES on the job id so a retry reads differently
            // (4b/4e). The overlay is NOT reseeded: one instrument per run
            // — on the local backend the job id only arrives when the read
            // is already done, and swapping the loupe for the scan
            // mid-look reads as a glitch. The attempt seed varies it
            // between runs instead, which is the intent of "a retry shows
            // a different one".
            this.rand = seeded(state.job_id * 2654435761);
            await this.apply(state.payload);
            if (token !== this.runToken) return;
            this.stageRows();
            this.planRemainingLines();
            this.showDone = true;
            if (!this.showTimer) this.settle();   // reduced motion goes straight in
        }

        /* Rows arrive one at a time while the clerk is still talking (4c:
           "each resolved field adds a row, so the panel grows to the size
           of the answer") — the values are already in the form; this is
           the ledger writing them down at a hand's pace. Each row's field
           flashes as its line lands. */
        stageRows() {
            this.clearStagedRows();
            if (!this.rowsEl) return;
            this.stagedTimers = [];
            this.rows.forEach((field, i) => {
                this.stagedTimers.push(setTimeout(() => {
                    const info = this.applied[field];
                    if (!info || !this.rowsEl) return;
                    const shell = document.createElement('div');
                    shell.innerHTML = this.rowHTML(field, info);
                    if (shell.firstChild) this.rowsEl.appendChild(shell.firstChild);
                    this.settleFlash(field);
                }, 350 + i * 380));
            });
        }

        clearStagedRows() {
            (this.stagedTimers || []).forEach(t => clearTimeout(t));
            this.stagedTimers = [];
        }

        async apply(payload) {
            this.applying = true;
            this.lowHints = [];
            this.missHints = [];
            this.extraHints = [];
            this.lotHint = !!payload.lot_detected;
            try {
                const fields = payload.fields || {};
                const order = Object.keys(this.cfg.fields)
                    .sort((a, b) => (a === 'state' ? -1 : b === 'state' ? 1 : 0));
                for (const field of order) {
                    if (field === 'addon_type') continue;
                    const data = fields[field];
                    if (!data) continue;
                    await this.applyField(field, data);
                }
                await this.applyAddons(fields.addon_type);
                for (const miss of payload.unmatched || []) {
                    if (!this.missHints.some(h => h.source === miss.source_text)) {
                        this.missHints.push({ field: miss.field, source: String(miss.source_text) });
                    }
                }
            } finally {
                this.applying = false;
            }
        }

        async applyField(field, data) {
            const spec = this.cfg.fields[field];
            if (!spec || data.value === null || data.value === undefined) {
                if (data && data.source_text && data.tier === 'unmatched') {
                    this.missHints.push({ field, source: String(data.source_text) });
                }
                return;
            }
            if (data.tier === 'low') {
                this.lowHints.push({ field, data });
                return;
            }
            if (data.tier !== 'high' && data.tier !== 'medium') return;
            if (this.dirty[field]) {
                // Never overwrite something the seller wrote (or carried in
                // from their shelf record). If the photograph disagrees,
                // the value is *offered* — a ○ "Use it" row — not applied.
                const current = this.read(field);
                if (String(data.value) !== String(current) && data.name !== current) {
                    this.lowHints.push({ field, data, conflict: true });
                }
                return;
            }
            const ok = await this.set(field, data);
            if (!ok) {
                this.missHints.push({ field, source: String(data.source_text || data.name || '') });
                return;
            }
            // 4e: high AND medium render green with "change". Amber (the
            // ✓/× pair) is reserved for near-floor matches, second-pass
            // rescues and inferences — the server says which, per field.
            const flagged = data.check !== undefined
                ? !!data.check
                : (!!data.inferred || !!data.second_pass);
            this.applied[field] = { suggested: data.value, tier: data.tier, name: data.name, flagged };
            this.rows.push(field);
            if (flagged) this.flagField(field, data);
        }

        async applyAddons(addonField) {
            const items = (addonField && addonField.items) || [];
            if (!items.length) return;
            const matched = items.filter(i => i.value !== null && (i.tier === 'high' || i.tier === 'medium'));
            const spec = this.cfg.fields.addon_type || {};
            const itemFlag = (i) => (i.check !== undefined ? !!i.check : (!!i.inferred || !!i.second_pass));
            if (matched.length && !this.dirty.addon_type) {
                if (spec.kind === 'checklist') {
                    const ok = await this.set('addon_type', { value: matched.map(i => i.value) });
                    if (ok) {
                        const flagged = matched.some(itemFlag);
                        this.applied.addon_type = {
                            suggested: matched.map(i => i.value),
                            tier: matched.some(i => i.tier === 'medium') ? 'medium' : 'high',
                            name: matched.map(i => i.name).join(', '),
                            flagged,
                        };
                        this.rows.push('addon_type');
                        if (flagged) this.flagField('addon_type', {
                            source_text: matched.map(i => i.source_text).join(', '), name: '' });
                    }
                } else {
                    const best = matched[0];
                    const ok = await this.set('addon_type', best);
                    if (ok) {
                        const flagged = itemFlag(best);
                        this.applied.addon_type = { suggested: best.value, tier: best.tier, name: best.name, flagged };
                        this.rows.push('addon_type');
                        if (flagged) this.flagField('addon_type', best);
                    }
                    for (const item of matched.slice(1)) {
                        this.extraHints.push({ name: item.name, tier: item.tier });
                    }
                }
            }
            for (const item of items.filter(i => i.value === null && i.source_text)) {
                this.missHints.push({ field: 'addon_type', source: String(item.source_text) });
            }
        }

        async set(field, data) {
            const spec = this.cfg.fields[field];
            if (spec.kind === 'checklist') {
                const values = (Array.isArray(data.value) ? data.value : [data.value]).map(String);
                await this.waitForGroupValue(field, values[0]);
                let hit = false;
                this.group(field).forEach((input) => {
                    if (values.includes(input.value)) {
                        input.checked = true;
                        hit = true;
                        input.dispatchEvent(new Event('change', { bubbles: true }));
                    }
                });
                return hit;
            }
            if (spec.kind === 'radio') {
                const radio = this.radios(field).find(r => r.value === String(data.value));
                if (!radio) return false;
                radio.checked = true;
                radio.dispatchEvent(new Event('change', { bubbles: true }));
                return true;
            }
            const node = el(spec.sel);
            if (!node) return false;
            if (spec.kind === 'multiselect') {
                const values = Array.isArray(data.value) ? data.value.map(String) : [String(data.value)];
                let hit = false;
                for (const opt of node.options) {
                    opt.selected = values.includes(opt.value);
                    hit = hit || opt.selected;
                }
                node.dispatchEvent(new Event('change', { bubbles: true }));
                return hit;
            }
            if (spec.kind === 'select') {
                const value = String(data.value);
                if (DEFERRED.includes(field)) {
                    const found = await this.waitForOption(node, value);
                    if (!found) return false;
                } else if (!node.querySelector(`option[value="${value}"]`)) {
                    return false;
                }
                node.value = value;
                node.dispatchEvent(new Event('change', { bubbles: true }));
                return true;
            }
            node.value = data.value;
            node.dispatchEvent(new Event('input', { bubbles: true }));
            node.dispatchEvent(new Event('change', { bubbles: true }));
            return true;
        }

        waitForGroupValue(field, value, tries = 30) {
            return new Promise(resolve => {
                const check = n => {
                    if (this.group(field).some(i => i.value === String(value))) return resolve(true);
                    if (n <= 0) return resolve(false);
                    setTimeout(() => check(n - 1), 100);
                };
                check(tries);
            });
        }

        waitForOption(node, value, tries = 30) {
            return new Promise(resolve => {
                const check = n => {
                    if (node.querySelector(`option[value="${value}"]`)) return resolve(true);
                    if (n <= 0) return resolve(false);
                    setTimeout(() => check(n - 1), 100);
                };
                check(tries);
            });
        }

        /* The brass flag on the field itself — turn 6b's check-this state. */
        flagField(field, data) {
            const wrap = this.wrapOf(field);
            if (wrap) {
                wrap.classList.add('is-flagged');
                wrap.title = 'Read from the photograph as: ' + (data.source_text || data.name || '');
            }
        }

        unflagField(field) {
            const wrap = this.wrapOf(field);
            if (wrap) {
                wrap.classList.remove('is-flagged');
                wrap.removeAttribute('title');
            }
        }

        /* ── settle: rows and the tally (4a/4c) ──────────────────────── */

        /* A read the backend couldn't match may still name something that
           exists in the form's own options — "Nonresident" beside a
           Non-Resident option, "Statewide" beside the statewide row. That
           is a value to offer (○ Use it), not a word to file away
           (Suggest it). Suggest-it stays for the genuinely unknown. */
        recoverMisses() {
            const keep = [];
            for (const h of this.missHints || []) {
                const spec = this.cfg.fields[h.field];
                const hit = spec && this.optionFor(h.field, h.source);
                if (hit) this.lowHints.push({ field: h.field, data: { value: hit.value, name: hit.name } });
                else keep.push(h);
            }
            this.missHints = keep;
        }

        optionFor(field, text) {
            const spec = this.cfg.fields[field];
            const wanted = String(text || '').toLowerCase().replace(/[^a-z0-9]/g, '');
            if (!wanted) return null;
            const match = (label, value) => {
                const norm = String(label || '').toLowerCase().replace(/[^a-z0-9]/g, '');
                return norm && norm === wanted ? { value, name: label } : null;
            };
            if (spec.kind === 'radio' || spec.kind === 'checklist') {
                for (const input of this.group(field)) {
                    const label = input.closest('label');
                    const hit = match(label ? label.textContent.trim() : input.value, input.value);
                    if (hit) return hit;
                }
                return null;
            }
            const node = el(spec.sel);
            if (!node || !node.options) return null;
            for (const opt of node.options) {
                if (!opt.value) continue;
                const hit = match(opt.text.trim(), opt.value);
                if (hit) return hit;
            }
            return null;
        }

        settle() {
            this.clearStagedRows();
            this.stopShow();
            this.unlockFields();
            this.recoverMisses();
            this.frame('tap any line to change it');
            this.panel.innerHTML =
                '<div class="pf-tally" data-pf-tally></div>' +
                '<div class="pf-rows" data-pf-rows></div>' +
                // 4a's settled foot: the caveat on the left, the retry on
                // the right — a changed photograph or a second opinion has
                // a home without waiting for a failure.
                '<div class="pf-footbar">' +
                '<span>Clearing a line empties the field.</span>' +
                '<button type="button" class="pf-reread" data-pf-reread>Read again</button>' +
                '</div>';
            this.rowsEl = this.panel.querySelector('[data-pf-rows]');
            const reread = this.panel.querySelector('[data-pf-reread]');
            if (reread) reread.addEventListener('click', () => {
                if (this.lastFile) this.start(this.lastFile);
            });
            this.renderRows();
            this.renderTally();
        }

        failed(message) {
            this.stopShow();
            this.unlockFields();
            this.reveal();
            this.frame('');
            this.panel.innerHTML =
                '<div class="pf-failed">' +
                '<strong>Couldn&rsquo;t read this one.</strong>' +
                '<span>Fill it in yourself and it lands in the ledger the same way. ' +
                'A straighter, brighter photograph of the front usually does it.</span>' +
                (message ? `<span class="pf-failed-why">${esc(message)}</span>` : '') +
                '<button type="button" class="pf-act" data-pf-retry>Read again</button>' +
                '</div>';
            const retry = this.panel.querySelector('[data-pf-retry]');
            if (retry) retry.addEventListener('click', () => {
                if (this.lastFile) this.start(this.lastFile);
            });
        }

        rowHTML(field, info) {
            const label = esc(this.fieldLabel(field));
            const value = esc(info.name || info.suggested);
            if (info.flagged && !info.accepted) {
                return `<div class="pf-row pf-row--check" data-pf-row="${field}">` +
                    `<span class="pf-mark pf-mark--ask">?</span>` +
                    `<span class="pf-field">${label}</span>` +
                    `<span class="pf-value">${value}</span>` +
                    `<span class="pf-pair">` +
                    `<button type="button" class="pf-yes" data-pf-yes="${field}" aria-label="Accept ${label}">&#10003;</button>` +
                    `<button type="button" class="pf-no" data-pf-no="${field}" aria-label="Clear ${label}">&times;</button>` +
                    `</span></div>`;
            }
            return `<div class="pf-row" data-pf-row="${field}">` +
                `<span class="pf-mark pf-mark--ok">&#10003;</span>` +
                `<span class="pf-field">${label}</span>` +
                `<span class="pf-value">${value}</span>` +
                `<button type="button" class="pf-change" data-pf-change="${field}">change</button>` +
                `</div>`;
        }

        renderRows() {
            if (!this.rowsEl) return;
            let html = '';
            if (this.lotHint) {
                html += '<div class="pf-lot">This photograph looks like <strong>multiple items</strong>. ' +
                    'List them as a lot (coming with lot listings), or one item per photograph.</div>';
            }
            for (const field of this.rows) {
                const info = this.applied[field];
                if (info) html += this.rowHTML(field, info);
            }
            html += (this.lowHints || []).map((h, i) =>
                `<div class="pf-row"><span class="pf-mark pf-mark--maybe">&#9675;</span>` +
                `<span class="pf-field">${esc(this.fieldLabel(h.field))}</span>` +
                `<span class="pf-value">${esc(h.data.name || h.data.source_text)}</span>` +
                `<button type="button" class="pf-act" data-low="${i}">Use it</button></div>`
            ).join('');
            html += (this.extraHints || []).map(h =>
                `<div class="pf-row"><span class="pf-mark pf-mark--maybe">&#9675;</span>` +
                `<span class="pf-field">Add-on</span><span class="pf-value">${esc(h.name)}</span>` +
                `<span class="pf-note">one selectable for now</span></div>`
            ).join('');
            html += (this.missHints || []).map((h, i) =>
                `<div class="pf-row"><span class="pf-mark pf-mark--miss">&times;</span>` +
                `<span class="pf-field">${esc(this.fieldLabel(h.field))}</span>` +
                `<span class="pf-value pf-value--read">&ldquo;${esc(h.source)}&rdquo;</span>` +
                `<button type="button" class="pf-act" data-suggest="${i}">Suggest it</button></div>`
            ).join('');
            this.rowsEl.innerHTML = html;
            this.bindRows();
        }

        bindRows() {
            this.rowsEl.querySelectorAll('[data-pf-yes]').forEach(btn => {
                btn.addEventListener('click', () => this.acceptRow(btn.dataset.pfYes));
            });
            this.rowsEl.querySelectorAll('[data-pf-no]').forEach(btn => {
                btn.addEventListener('click', () => this.clearRow(btn.dataset.pfNo));
            });
            this.rowsEl.querySelectorAll('[data-pf-change]').forEach(btn => {
                btn.addEventListener('click', () => this.focusField(btn.dataset.pfChange));
            });
            this.rowsEl.querySelectorAll('[data-low]').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const h = this.lowHints[Number(btn.dataset.low)];
                    this.applying = true;
                    try { await this.set(h.field, h.data); } finally { this.applying = false; }
                    this.applied[h.field] = { suggested: h.data.value, tier: 'low', name: h.data.name };
                    this.rows.push(h.field);
                    this.lowHints.splice(Number(btn.dataset.low), 1);
                    this.settleFlash(h.field);
                    this.queueCorrection(h.field, { was_accepted: true });
                    this.renderRows();
                    this.renderTally();
                });
            });
            this.rowsEl.querySelectorAll('[data-suggest]').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const h = this.missHints[Number(btn.dataset.suggest)];
                    const body = new URLSearchParams({
                        suggestion_type: 'new_value',
                        target_model: 'license_type',
                        field_name: h.field === 'addon_type' ? 'addon_type' : h.field,
                        proposed_value: h.source,
                        source_or_evidence: 'Extracted by image prefill (job #' + (this.jobId || '?') + ')',
                        next: window.location.pathname,
                    });
                    try {
                        await fetch(this.cfg.suggestionUrl, {
                            method: 'POST', body,
                            headers: { 'X-CSRFToken': csrfToken() },
                        });
                        btn.disabled = true;
                        btn.textContent = 'Sent ✓';
                    } catch (err) {
                        btn.textContent = 'Failed — use "Is a value missing?"';
                    }
                });
            });
        }

        focusField(field) {
            const spec = this.cfg.fields[field] || {};
            const node = (spec.kind === 'radio' || spec.kind === 'checklist')
                ? this.group(field)[0] : el(spec.sel);
            if (!node) return;
            node.scrollIntoView({ behavior: 'smooth', block: 'center' });
            try { node.focus({ preventScroll: true }); } catch (err) { node.focus(); }
        }

        acceptRow(field) {
            const info = this.applied[field];
            if (!info) return;
            info.accepted = true;
            this.unflagField(field);
            this.queueCorrection(field, { was_accepted: true }, () => {
                info.accepted = false;
                this.flagField(field, { name: info.name });
                this.renderRows();
                this.renderTally();
            });
            this.renderRows();
            this.renderTally();
        }

        clearRow(field) {
            const info = this.applied[field];
            if (!info) return;
            const spec = this.cfg.fields[field];
            const restore = () => {
                this.applying = true;
                try {
                    const initial = this.initial[field] || '';
                    if (spec.kind === 'radio') {
                        this.radios(field).forEach(r => { r.checked = r.value === initial; });
                        const on = this.radios(field).find(r => r.checked) || this.radios(field)[0];
                        if (on) on.dispatchEvent(new Event('change', { bubbles: true }));
                    } else if (spec.kind === 'checklist') {
                        const keep = String(initial).split(',');
                        this.group(field).forEach(i => { i.checked = keep.includes(i.value); });
                    } else {
                        const node = el(spec.sel);
                        if (node) { node.value = initial; node.dispatchEvent(new Event('change', { bubbles: true })); }
                    }
                } finally {
                    this.applying = false;
                }
            };
            restore();
            this.cleared[field] = info;
            delete this.applied[field];
            this.rows = this.rows.filter(f => f !== field);
            this.unflagField(field);
            this.queueCorrection(field, { was_cleared: true, cleared_info: info }, async () => {
                // Undo: put the suggestion back exactly as it was.
                this.applying = true;
                try { await this.set(field, { value: info.suggested }); } finally { this.applying = false; }
                delete this.cleared[field];
                this.applied[field] = info;
                this.rows.push(field);
                if (info.flagged) this.flagField(field, { name: info.name });
                this.renderRows();
                this.renderTally();
            }, 'Cleared — ');
            this.renderRows();
            this.renderTally();
        }

        renderTally() {
            const tally = this.panel && this.panel.querySelector('[data-pf-tally]');
            if (!tally) return;
            const filled = Object.values(this.applied)
                .filter(a => !a.flagged || a.accepted).length;
            const toCheck = Object.values(this.applied)
                .filter(a => a.flagged && !a.accepted).length;
            const blanks = (this.cfg.forYou || []).filter(s => this.forYouEmpty(s));
            let html = '<div class="pf-tally-row">' +
                `<span class="pf-tally-filled">${filled} filled</span>`;
            if (toCheck) {
                html += '<span class="pf-tally-sep"></span>' +
                    `<span class="pf-tally-check">${toCheck} to check</span>`;
            }
            html += '<span class="pf-tally-sep"></span>' +
                `<span class="pf-tally-you">${blanks.length} for you</span></div>`;
            if (blanks.length) {
                html += `<span class="pf-tally-blanks">Still blank: ${esc(blanks.map(s => s.name).join(', '))}.</span>`;
            }
            tally.innerHTML = html;
        }

        /* ── corrections: per click, five seconds of undo (4e) ───────── */

        queueCorrection(field, flags, onUndo, undoLabel) {
            const info = flags.cleared_info || this.applied[field] || this.cleared[field] || {};
            const body = {
                field_name: field,
                suggested_value: info.suggested,
                final_value: flags.was_cleared ? (this.initial[field] || '') : this.read(field),
                tier: info.tier || '',
                was_accepted: !!flags.was_accepted,
                was_cleared: !!flags.was_cleared,
            };
            const pending = this.pendingCorrections[field];
            if (pending) { clearTimeout(pending.timer); this.removeUndo(field); }

            const timer = setTimeout(() => this.flushCorrection(field), UNDO_MS);
            this.pendingCorrections[field] = { timer, body, onUndo };
            if (onUndo) this.showUndo(field, undoLabel || '');
        }

        showUndo(field, prefix) {
            const row = this.rowsEl && this.rowsEl.querySelector(`[data-pf-row="${field}"]`);
            const host = row || this.rowsEl;
            if (!host) return;
            const chip = document.createElement('button');
            chip.type = 'button';
            chip.className = 'pf-undo';
            chip.dataset.pfUndo = field;
            chip.textContent = prefix + 'undo';
            chip.addEventListener('click', () => {
                const pending = this.pendingCorrections[field];
                if (!pending) return;
                clearTimeout(pending.timer);
                delete this.pendingCorrections[field];
                chip.remove();
                if (pending.onUndo) pending.onUndo();
            });
            if (row) {
                const pair = row.querySelector('.pf-pair, .pf-change');
                if (pair) pair.replaceWith(chip); else row.appendChild(chip);
            } else {
                host.prepend(chip);
            }
        }

        removeUndo(field) {
            const chip = this.rowsEl && this.rowsEl.querySelector(`[data-pf-undo="${field}"]`);
            if (chip) chip.remove();
        }

        flushCorrection(field, sync) {
            const pending = this.pendingCorrections[field];
            if (!pending || !this.jobId) return;
            clearTimeout(pending.timer);
            delete this.pendingCorrections[field];
            this.removeUndo(field);
            this.sentCorrections[field] = pending.body;
            const url = this.cfg.correctionsUrlTemplate.replace('/0/', '/' + this.jobId + '/');
            const payload = JSON.stringify({ corrections: [pending.body] });
            if (sync && navigator.sendBeacon) {
                navigator.sendBeacon(url, new Blob([payload], { type: 'application/json' }));
                return;
            }
            fetch(url, {
                method: 'POST',
                keepalive: true,
                headers: { 'X-CSRFToken': csrfToken(), 'Content-Type': 'application/json' },
                body: payload,
            }).catch(() => {});
        }

        flushCorrections(sync) {
            for (const field of Object.keys(this.pendingCorrections)) {
                this.flushCorrection(field, sync);
            }
        }

        /* The submit-time diff still runs — it catches the quiet edits that
           never clicked a row button. Rows already logged are skipped
           unless the field moved again afterwards. */
        logCorrections() {
            if (!this.jobId) return;
            const corrections = [];
            for (const [field, info] of Object.entries(this.applied)) {
                const finalValue = this.read(field);
                const sent = this.sentCorrections[field];
                if (sent && String(sent.final_value) === String(finalValue)) continue;
                corrections.push({
                    field_name: field,
                    suggested_value: info.suggested,
                    final_value: finalValue,
                    tier: info.tier,
                    was_accepted: String(info.suggested) === String(finalValue),
                    was_cleared: false,
                });
            }
            for (const [field, info] of Object.entries(this.cleared)) {
                if (this.sentCorrections[field]) continue;
                corrections.push({
                    field_name: field,
                    suggested_value: info.suggested,
                    final_value: this.read(field),
                    tier: info.tier || '',
                    was_accepted: false,
                    was_cleared: true,
                });
            }
            if (!corrections.length) return;
            const url = this.cfg.correctionsUrlTemplate.replace('/0/', '/' + this.jobId + '/');
            fetch(url, {
                method: 'POST',
                keepalive: true,
                headers: { 'X-CSRFToken': csrfToken(), 'Content-Type': 'application/json' },
                body: JSON.stringify({ corrections }),
            }).catch(() => {});
        }
    }

    window.KBPrefill = { init: cfg => new Prefill(cfg) };
})();
