/* KeystoneBid image prefill — tier-based form filling from a license photo.
 *
 * Wire-up (per form):
 *   KBPrefill.init({
 *     createUrl, correctionsUrlTemplate, suggestionUrl, source: 'collection'|'listing',
 *     fileInput: '#id_images-0-image',
 *     jobIdInput: '#prefill-job-id',
 *     panel: '#prefill-panel',
 *     form: 'form',
 *     fields: { state: {sel:'#id_state', kind:'select'}, ... }
 *   });
 *
 * Tier rules (spec §7): high = filled; medium = filled + ✨ badge + one-click clear;
 * low = click-to-apply chip; unmatched = "couldn't match" panel with Suggest.
 * Never overwrites a field the user has edited (dirty tracking).
 */
(function () {
    'use strict';

    const DEFERRED = ['geographic_unit', 'residency', 'holder_eligibility',
                      'activity_scope', 'duration', 'material', 'addon_type'];
    const FIELD_LABELS = {
        item_kind: 'Item kind', state: 'State', license_year: 'Year', era_guess: 'Era',
        geographic_unit: 'County / unit', residency: 'Residency', holder_eligibility: 'Eligibility',
        activity_scope: 'Activity', duration: 'Duration', material: 'Material',
        addon_type: 'Add-on', shape: 'Shape', colors: 'Colors', serial_number: 'Serial',
    };

    function cookie(name) {
        const m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
        return m ? decodeURIComponent(m.pop()) : '';
    }

    function el(sel) { return sel ? document.querySelector(sel) : null; }

    class Prefill {
        constructor(cfg) {
            this.cfg = cfg;
            this.jobId = null;
            this.payload = null;
            this.applied = {};   // field -> {suggested, tier}
            this.cleared = {};
            this.dirty = {};
            this.initial = {};
            this.applying = false;

            this.panel = el(cfg.panel);
            this.fileInput = el(cfg.fileInput);
            this.form = el(cfg.form) || (this.fileInput && this.fileInput.form);
            if (!this.fileInput || !this.form) return;

            for (const [field, spec] of Object.entries(cfg.fields)) {
                const node = this.node(field);
                if (!node) continue;
                this.initial[field] = this.read(field);
                // On edit forms, saved values are protected (cfg.protectInitial);
                // on create forms only user edits after load count as dirty.
                if (cfg.protectInitial && this.initial[field]) this.dirty[field] = true;
                const mark = () => { if (!this.applying) this.dirty[field] = true; };
                ((spec.kind === 'radio' || spec.kind === 'checklist') ? this.group(field) : [node]).forEach(n => {
                    n.addEventListener('input', mark);
                    n.addEventListener('change', mark);
                });
            }

            this.fileInput.addEventListener('change', () => {
                const file = this.fileInput.files && this.fileInput.files[0];
                if (!file) return;
                const key = file.name + ':' + file.size;    // drop zones re-assign on reorder
                if (key === this.lastFileKey) return;
                this.lastFileKey = key;
                this.start(file);
            });
            this.form.addEventListener('submit', () => this.logCorrections());
        }

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

        status(html) {
            if (!this.panel) return;
            let box = this.panel.querySelector('.prefill-status');
            if (!box) {
                box = document.createElement('div');
                box.className = 'prefill-status';
                this.panel.prepend(box);
            }
            box.innerHTML = html;
        }

        async start(file) {
            this.status('<span class="prefill-shimmer">&#10024; Reading your image&hellip;</span>');
            const body = new FormData();
            body.append('image', file);
            body.append('source_form', this.cfg.source);
            let state;
            try {
                const resp = await fetch(this.cfg.createUrl, {
                    method: 'POST', body,
                    headers: { 'X-CSRFToken': cookie('csrftoken') },
                });
                state = await resp.json();
                if (!resp.ok) throw new Error(state.error || 'Prefill failed');
            } catch (err) {
                this.status('Prefill unavailable: ' + err.message);
                return;
            }
            for (let i = 0; i < 40 && (state.status === 'pending' || state.status === 'resolving'); i++) {
                await new Promise(r => setTimeout(r, 750));
                const resp = await fetch(this.cfg.createUrl + state.job_id + '/');
                state = await resp.json();
            }
            if (state.status !== 'complete') {
                this.status('Prefill did not finish: ' + (state.error || state.status));
                return;
            }
            this.jobId = state.job_id;
            const jobInput = el(this.cfg.jobIdInput);
            if (jobInput) jobInput.value = state.job_id;
            this.payload = state.payload;
            await this.apply(state.payload);
        }

        async apply(payload) {
            this.applying = true;
            const hints = [];
            try {
                if (payload.lot_detected) {
                    hints.push({ kind: 'lot' });
                }
                const fields = payload.fields || {};
                const order = Object.keys(this.cfg.fields)
                    .sort((a, b) => (a === 'state' ? -1 : b === 'state' ? 1 : 0));
                for (const field of order) {
                    if (field === 'addon_type') continue;
                    const data = fields[field];
                    if (!data) continue;
                    await this.applyField(field, data, hints);
                }
                await this.applyAddons(fields.addon_type, hints);
                for (const miss of payload.unmatched || []) {
                    if (!hints.some(h => h.source === miss.source_text)) {
                        hints.push({ kind: 'unmatched', field: miss.field, source: miss.source_text });
                    }
                }
            } finally {
                this.applying = false;
            }
            this.renderPanel(hints, payload);
        }

        async applyField(field, data, hints) {
            const spec = this.cfg.fields[field];
            if (!spec || data.value === null || data.value === undefined) {
                if (data && data.source_text && data.tier === 'unmatched') {
                    hints.push({ kind: 'unmatched', field, source: String(data.source_text) });
                }
                return;
            }
            if (data.tier === 'low') {
                hints.push({ kind: 'low', field, data });
                return;
            }
            if (data.tier !== 'high' && data.tier !== 'medium') return;
            if (this.dirty[field]) return;
            const ok = await this.set(field, data);
            if (!ok) {
                hints.push({ kind: 'unmatched', field, source: String(data.source_text || data.name || '') });
                return;
            }
            this.applied[field] = { suggested: data.value, tier: data.tier, name: data.name };
            if (data.tier === 'medium' || data.inferred || data.second_pass) this.badge(field, data);
        }

        async applyAddons(addonField, hints) {
            const items = (addonField && addonField.items) || [];
            if (!items.length) return;
            const matched = items.filter(i => i.value !== null && (i.tier === 'high' || i.tier === 'medium'));
            const spec = this.cfg.fields.addon_type || {};
            if (matched.length && !this.dirty.addon_type) {
                if (spec.kind === 'checklist') {
                    const ok = await this.set('addon_type', { value: matched.map(i => i.value) });
                    if (ok) {
                        this.applied.addon_type = {
                            suggested: matched.map(i => i.value),
                            tier: matched.some(i => i.tier === 'medium') ? 'medium' : 'high',
                            name: matched.map(i => i.name).join(', '),
                        };
                        if (matched.some(i => i.tier === 'medium' || i.second_pass)) {
                            this.badge('addon_type', { source_text: matched.map(i => i.source_text).join(', '), name: '' });
                        }
                    }
                } else {
                    const best = matched[0];
                    const ok = await this.set('addon_type', best);
                    if (ok) {
                        this.applied.addon_type = { suggested: best.value, tier: best.tier, name: best.name };
                        if (best.tier === 'medium' || best.second_pass) this.badge('addon_type', best);
                    }
                    for (const item of matched.slice(1)) {
                        hints.push({ kind: 'addon-extra', name: item.name, tier: item.tier });
                    }
                }
            }
            for (const item of items.filter(i => i.value === null && i.source_text)) {
                hints.push({ kind: 'unmatched', field: 'addon_type', source: String(item.source_text) });
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

        badge(field, data) {
            const spec = this.cfg.fields[field];
            const anchor = (spec.kind === 'radio' || spec.kind === 'checklist')
                ? (this.group(field).slice(-1)[0] || {}).parentElement
                : el(spec.sel);
            if (!anchor || anchor.parentElement.querySelector(`[data-prefill-badge="${field}"]`)) return;
            const badge = document.createElement('span');
            badge.className = 'prefill-badge';
            badge.dataset.prefillBadge = field;
            badge.title = 'AI read this as: ' + (data.source_text || data.name || '');
            badge.innerHTML = '&#10024; AI <button type="button" aria-label="Clear suggestion">&times;</button>';
            badge.querySelector('button').addEventListener('click', () => {
                this.applying = true;
                try {
                    const initial = this.initial[field] || '';
                    if (spec.kind === 'radio') {
                        this.radios(field).forEach(r => { r.checked = r.value === initial; });
                    } else {
                        const node = el(spec.sel);
                        if (node) { node.value = initial; node.dispatchEvent(new Event('change', { bubbles: true })); }
                    }
                } finally {
                    this.applying = false;
                }
                this.cleared[field] = true;
                delete this.applied[field];
                badge.remove();
            });
            anchor.insertAdjacentElement('afterend', badge);
        }

        renderPanel(hints, payload) {
            const applied = Object.keys(this.applied).length;
            let html = `<div class="prefill-status">&#10024; Prefilled ${applied} field${applied === 1 ? '' : 's'} from your image — please verify. AI suggestions can be wrong, and listings are your responsibility.</div>`;
            const lot = hints.find(h => h.kind === 'lot');
            if (lot) {
                html += '<div class="prefill-lot">This photo looks like <strong>multiple items</strong>. List them as a lot (coming with lot listings) or upload one item per photo.</div>';
            }
            const lows = hints.filter(h => h.kind === 'low');
            if (lows.length) {
                html += '<div class="prefill-hints"><strong>Low confidence</strong> — click to apply: ' +
                    lows.map((h, i) => `<button type="button" class="prefill-chip" data-low="${i}">${FIELD_LABELS[h.field] || h.field}: ${h.data.name || h.data.source_text}</button>`).join(' ') +
                    '</div>';
            }
            const extras = hints.filter(h => h.kind === 'addon-extra');
            if (extras.length) {
                html += '<div class="prefill-hints">Also read on the item (one add-on selectable for now): ' +
                    extras.map(h => `<span class="prefill-chip prefill-chip-static">${h.name}</span>`).join(' ') + '</div>';
            }
            const misses = hints.filter(h => h.kind === 'unmatched');
            if (misses.length) {
                html += '<div class="prefill-hints"><strong>We read these but couldn\'t match them:</strong><ul>' +
                    misses.map((h, i) => `<li>"${h.source}" (${FIELD_LABELS[h.field] || h.field}) <button type="button" class="prefill-chip" data-suggest="${i}">Suggest this value</button></li>`).join('') +
                    '</ul></div>';
            }
            this.panel.innerHTML = html;

            this.panel.querySelectorAll('[data-low]').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const h = lows[Number(btn.dataset.low)];
                    this.applying = true;
                    try { await this.set(h.field, h.data); } finally { this.applying = false; }
                    this.applied[h.field] = { suggested: h.data.value, tier: 'low', name: h.data.name };
                    btn.disabled = true;
                    btn.textContent += ' ✓';
                });
            });
            this.panel.querySelectorAll('[data-suggest]').forEach(btn => {
                btn.addEventListener('click', async () => {
                    const h = misses[Number(btn.dataset.suggest)];
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
                            headers: { 'X-CSRFToken': cookie('csrftoken') },
                        });
                        btn.disabled = true;
                        btn.textContent = 'Suggested ✓';
                    } catch (err) {
                        btn.textContent = 'Failed — try the "Is a value missing?" form';
                    }
                });
            });
        }

        logCorrections() {
            if (!this.jobId) return;
            const corrections = [];
            for (const [field, info] of Object.entries(this.applied)) {
                const finalValue = this.read(field);
                corrections.push({
                    field_name: field,
                    suggested_value: info.suggested,
                    final_value: finalValue,
                    tier: info.tier,
                    was_accepted: String(info.suggested) === String(finalValue),
                    was_cleared: false,
                });
            }
            for (const field of Object.keys(this.cleared)) {
                corrections.push({
                    field_name: field,
                    suggested_value: (this.payload.fields[field] || {}).value,
                    final_value: this.read(field),
                    tier: (this.payload.fields[field] || {}).tier || '',
                    was_accepted: false,
                    was_cleared: true,
                });
            }
            if (!corrections.length) return;
            const url = this.cfg.correctionsUrlTemplate.replace('/0/', '/' + this.jobId + '/');
            fetch(url, {
                method: 'POST',
                keepalive: true,
                headers: { 'X-CSRFToken': cookie('csrftoken'), 'Content-Type': 'application/json' },
                body: JSON.stringify({ corrections }),
            }).catch(() => {});
        }
    }

    window.KBPrefill = { init: cfg => new Prefill(cfg) };
})();
