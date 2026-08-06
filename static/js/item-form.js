/* KeystoneBid item form — the evidence rail and the work column.
 *
 * Three jobs, all drawn on turns 5b/6b:
 *   1. Named photograph slots. Front and back are fixed slots, so reordering
 *      can't relabel them; the three detail slots drag among themselves.
 *      Files land in the same hidden inputs the server always read —
 *      everything degrades to plain file inputs without JavaScript.
 *   2. The live "How buyers will see it" card, with the completeness line
 *      that says what to add next instead of just scoring.
 *   3. The title that writes itself from year, county, residency and
 *      attachments — the order collectors search in — until the seller
 *      touches it, after which it is theirs.
 *
 * Wire-up:
 *   KBItemForm.init({
 *     form: 'form[enctype]',
 *     slots: {
 *       front:   { input: '#id_featured_image', role: null },
 *       back:    { input: '#id_images-0-image', role: '#id_images-0-image_role', sort: '#id_images-0-sort_order', del: '#id_images-0-DELETE' },
 *       details: [ {input, role, sort, del}, ... ],
 *     },
 *     kind: 'listing' | 'collection',
 *     preview: true,
 *   })
 */
(function () {
    'use strict';

    function el(sel) {
        if (!sel) return null;
        try { return document.querySelector(sel); } catch (err) { return null; }
    }

    function kbConfirm(message) {
        return new Promise((resolve) => {
            const overlay = document.createElement('div');
            overlay.className = 'kb-modal-overlay';
            overlay.innerHTML = '<div class="kb-modal"><p>' + message + '</p>'
                + '<div class="kb-modal-actions">'
                + '<button type="button" class="kb-btn kb-btn--secondary" data-cancel>Keep it</button>'
                + '<button type="button" class="kb-btn kb-btn--primary" data-ok>Remove</button>'
                + '</div></div>';
            document.body.appendChild(overlay);
            overlay.querySelector('[data-ok]').addEventListener('click', () => { overlay.remove(); resolve(true); });
            overlay.querySelector('[data-cancel]').addEventListener('click', () => { overlay.remove(); resolve(false); });
            overlay.addEventListener('click', (e) => { if (e.target === overlay) { overlay.remove(); resolve(false); } });
        });
    }

    /* ── Photograph slots ───────────────────────────────────────────── */

    class Slots {
        constructor(cfg, onChange) {
            this.cfg = cfg;
            this.onChange = onChange;
            this.form = el(cfg.form);
            this.panel = el('[data-photo-panel]');
            if (!this.panel || !this.form) return;

            // No JavaScript, no slot theatre: the plain file inputs are the
            // form. With it, the slots take over and the inputs hide.
            const ui = this.panel.querySelector('[data-slots-ui]');
            if (ui) ui.hidden = false;
            const native = this.panel.querySelector('.if-native');
            if (native) native.classList.add('is-managed');

            // staged File objects for the named slots; details is ordered.
            this.front = null;
            this.back = null;
            this.details = [];
            this.dragFrom = null;

            this.picker = document.createElement('input');
            this.picker.type = 'file';
            this.picker.accept = 'image/*';
            this.picker.multiple = true;

            this.panel.addEventListener('click', (e) => this.click(e));
            this.panel.addEventListener('dragover', (e) => { e.preventDefault(); this.panel.classList.add('is-over'); });
            this.panel.addEventListener('dragleave', () => this.panel.classList.remove('is-over'));
            this.panel.addEventListener('drop', (e) => {
                e.preventDefault();
                this.panel.classList.remove('is-over');
                const files = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/'));
                if (files.length) this.take(files);
            });
            this.render();
        }

        click(e) {
            const x = e.target.closest('[data-slot-x]');
            if (x) {
                e.preventDefault();
                this.remove(x.dataset.slotX);
                return;
            }
            const slot = e.target.closest('[data-slot]');
            if (!slot) return;
            e.preventDefault();
            this.pickInto = slot.dataset.slot;
            this.picker.multiple = this.pickInto === 'any';
            this.picker.onchange = () => {
                const files = Array.from(this.picker.files);
                this.picker.value = '';
                if (!files.length) return;
                if (this.pickInto === 'front') this.front = files[0];
                else if (this.pickInto === 'back') this.back = files[0];
                else if (this.pickInto.startsWith('detail')) {
                    const i = Number(this.pickInto.slice(6));
                    this.details[i] = files[0];
                    this.details = this.details.filter(Boolean);
                } else this.take(files);
                this.sync();
            };
            this.picker.click();
        }

        /* Fill in reading order: front, back, then details. */
        take(files) {
            for (const file of files) {
                const key = file.name + ':' + file.size;
                const have = [this.front, this.back, ...this.details].filter(Boolean)
                    .some(f => f.name + ':' + f.size === key);
                if (have) continue;
                if (!this.front && !this.has('front')) this.front = file;
                else if (!this.back && !this.has('back')) this.back = file;
                else if (this.details.length < this.cfg.slots.details.length) this.details.push(file);
            }
            this.sync();
        }

        /* An edit form's slot can already hold a saved photograph. */
        has(name) {
            if (!this.panel) return false;
            const node = this.panel.querySelector(`[data-slot="${name}"]`);
            return node && node.dataset.existing === 'yes' && !node.dataset.deleted;
        }

        async remove(name) {
            const node = this.panel.querySelector(`[data-slot="${name}"]`);
            if (node && node.dataset.existing === 'yes' && !node.dataset.deleted) {
                if (!await kbConfirm('Remove this photograph from the record?')) return;
                const spec = this.spec(name);
                const del = spec && el(spec.del);
                if (del) del.checked = true;
                node.dataset.deleted = 'yes';
                this.sync();
                return;
            }
            if (name === 'front') this.front = null;
            else if (name === 'back') this.back = null;
            else if (name.startsWith('detail')) {
                this.details.splice(Number(name.slice(6)), 1);
            }
            this.sync();
        }

        spec(name) {
            if (name === 'front') return this.cfg.slots.front;
            if (name === 'back') return this.cfg.slots.back;
            if (name.startsWith('detail')) return this.cfg.slots.details[Number(name.slice(6))];
            return null;
        }

        sync() {
            // Named slots write straight to their inputs; details compact
            // upward so the formset never has a hole in the middle.
            const write = (spec, file) => {
                const input = spec && el(spec.input);
                if (!input) return;
                const dt = new DataTransfer();
                if (file) dt.items.add(file);
                input.files = dt.files;
            };
            write(this.cfg.slots.front, this.front);
            write(this.cfg.slots.back, this.back);
            this.cfg.slots.details.forEach((spec, i) => {
                write(spec, this.details[i] || null);
                const role = el(spec.role);
                if (role) role.value = 'detail';
                const sort = el(spec.sort);
                if (sort) sort.value = String((this.cfg.kind === 'collection' ? 2 : 1) + i);
            });
            const backSpec = this.cfg.slots.back;
            const backRole = backSpec && el(backSpec.role);
            if (backRole) backRole.value = 'back';
            const backSort = backSpec && el(backSpec.sort);
            if (backSort) backSort.value = this.cfg.kind === 'collection' ? '1' : '0';
            const frontRole = this.cfg.slots.front && el(this.cfg.slots.front.role);
            if (frontRole) frontRole.value = 'front';
            const frontSort = this.cfg.slots.front && el(this.cfg.slots.front.sort);
            if (frontSort) frontSort.value = '0';

            // Programmatic .files assignment fires no event — the prefill
            // machinery watches the front input.
            const frontInput = el(this.cfg.slots.front.input);
            if (frontInput) frontInput.dispatchEvent(new Event('change', { bubbles: true }));

            this.render();
            if (this.onChange) this.onChange(this);
        }

        thumb(name) {
            const map = {
                front: this.front, back: this.back,
            };
            const file = name.startsWith('detail') ? this.details[Number(name.slice(6))] : map[name];
            return file ? URL.createObjectURL(file) : null;
        }

        render() {
            let count = 0;
            this.panel.querySelectorAll('[data-slot]').forEach((node) => {
                const name = node.dataset.slot;
                if (name === 'any') return;
                const url = this.thumb(name);
                const existing = node.dataset.existing === 'yes' && !node.dataset.deleted;
                const img = node.querySelector('img');
                if (url) {
                    if (img) img.src = url;
                    else {
                        const pic = document.createElement('img');
                        pic.alt = '';
                        pic.src = url;
                        node.prepend(pic);
                    }
                    node.classList.add('is-filled');
                } else if (existing) {
                    node.classList.add('is-filled');
                } else {
                    if (img && !existing) img.remove();
                    node.classList.remove('is-filled');
                }
                if (url || existing) count += 1;
                if (node.dataset.deleted && img) img.remove();
            });
            const counter = this.panel.querySelector('[data-photo-count]');
            if (counter) counter.textContent = count + ' of ' + (2 + this.cfg.slots.details.length);

            // Details drag among themselves; the named slots hold still.
            this.panel.querySelectorAll('[data-slot^="detail"]').forEach((node) => {
                const i = Number(node.dataset.slot.slice(6));
                node.draggable = Boolean(this.details[i]);
                node.ondragstart = () => { this.dragFrom = i; node.classList.add('is-dragging'); };
                node.ondragend = () => { this.dragFrom = null; node.classList.remove('is-dragging'); };
                node.ondragover = (e) => { e.preventDefault(); node.classList.add('is-target'); };
                node.ondragleave = () => node.classList.remove('is-target');
                node.ondrop = (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    node.classList.remove('is-target');
                    if (this.dragFrom === null || this.dragFrom === i) return;
                    const [moved] = this.details.splice(this.dragFrom, 1);
                    this.details.splice(Math.min(i, this.details.length), 0, moved);
                    this.sync();
                };
            });
        }
    }

    /* ── The card preview and the completeness line ─────────────────── */

    function fieldText(sel) {
        const node = el(sel);
        if (!node) return '';
        if (node.tagName === 'SELECT') {
            const opt = node.options[node.selectedIndex];
            return (node.value && opt) ? opt.text.trim() : '';
        }
        return (node.value || '').trim();
    }

    function checkedText(name) {
        const hits = Array.from(document.querySelectorAll(`input[name="${name}"]:checked`));
        return hits.map((input) => {
            const label = input.closest('label');
            return label ? label.textContent.trim() : input.value;
        });
    }

    class Preview {
        constructor(cfg, slots) {
            this.cfg = cfg;
            this.slots = slots;
            this.card = el('[data-preview]');
            if (!this.card) return;
            const form = el(cfg.form);
            ['input', 'change'].forEach(evt =>
                form.addEventListener(evt, () => this.paint(), true));
            this.paint();
        }

        pieces() {
            return {
                year: fieldText('#id_license_year'),
                county: fieldText(this.cfg.kind === 'collection' ? '#id_county' : '#id_county_ref'),
                residency: fieldText('#id_residency'),
                condition: checkedText('condition_grade')[0] || fieldText('#id_condition_grade'),
                addons: checkedText('addon_type'),
                title: fieldText('#id_title'),
                era: fieldText('#id_era_label'),
            };
        }

        paint() {
            const p = this.pieces();
            const put = (sel, text) => {
                const node = this.card.querySelector(sel);
                if (node) node.textContent = text;
            };
            put('[data-pv-title]', p.title || 'Untitled, so far');
            const facts = [p.county, p.year || p.era, p.residency].filter(Boolean).join(' · ');
            put('[data-pv-facts]', facts || 'County, year and residency go here');
            put('[data-pv-cond]', p.condition ? p.condition : 'Condition not set');

            const media = this.card.querySelector('[data-pv-media]');
            if (media && this.slots) {
                const url = this.slots.thumb('front');
                let img = media.querySelector('img');
                if (url) {
                    if (!img) {
                        img = document.createElement('img');
                        img.alt = '';
                        media.prepend(img);
                    }
                    img.src = url;
                }
            }
            this.meter(p);
        }

        /* Mirrors Listing.listing_completeness_score, and then says what
           to add next — the number alone was a score with no advice. */
        meter(p) {
            const wrap = el('[data-complete]');
            if (!wrap) return;
            const kindInput = document.querySelector('input[name="item_kind"]:checked');
            const kind = kindInput ? kindInput.value : 'license';
            const has = {
                county: Boolean(fieldText(this.cfg.kind === 'collection' ? '#id_county' : '#id_county_ref')),
                material: Boolean(fieldText('#id_material')),
                description: Boolean(fieldText('#id_description')),
                shape: Boolean(fieldText('#id_shape')),
                colors: checkedText('colors').length > 0,
                addons: p.addons.length > 0,
                residency: Boolean(p.residency),
                scope: Boolean(fieldText('#id_activity_scope')),
                duration: Boolean(fieldText('#id_duration')),
                holder: Boolean(fieldText('#id_holder_eligibility')),
            };
            let checks;
            if (kind === 'addon') {
                checks = [has.county, has.material, has.description, has.shape, has.colors, has.addons];
            } else {
                checks = [has.county, has.material, has.description, has.shape, has.colors,
                          has.scope, has.residency, has.duration, has.holder, has.addons];
            }
            const score = Math.round((checks.filter(Boolean).length / checks.length) * 100);
            const fill = wrap.querySelector('[data-complete-fill]');
            const num = wrap.querySelector('[data-complete-score]');
            if (fill) fill.style.width = score + '%';
            if (num) num.textContent = score + '%';

            const wants = [];
            if (this.slots && this.slots.panel
                && !this.slots.thumb('back') && !this.slots.has('back')) wants.push('a back photograph');
            if (!has.material) wants.push('the material');
            if (!p.condition) wants.push('a condition grade');
            if (!has.shape) wants.push('the shape');
            if (!has.colors) wants.push('the colours');
            if (!has.description) wants.push('a line of description');
            const next = wrap.querySelector('[data-complete-next]');
            if (next) {
                if (score >= 100 && !wants.length) {
                    next.textContent = 'Nothing missing. This is the entry collectors stop on.';
                } else if (wants.length) {
                    next.textContent = wants.slice(0, 2).join(' and ').replace(/^./, c => c.toUpperCase())
                        + ' would finish it. Fuller entries sell for more, which is the only reason we mention it.';
                } else {
                    next.textContent = 'Nearly there.';
                }
            }
        }
    }

    /* ── The title that writes itself ───────────────────────────────── */

    class Title {
        constructor(cfg) {
            this.cfg = cfg;
            this.input = el('#id_title');
            if (!this.input) return;
            this.form = el(cfg.form);
            this.dirty = Boolean(this.input.value.trim()) && !cfg.freshTitle;
            this.input.addEventListener('input', () => { this.dirty = true; });

            // Fresh record: the written-for-you panel fronts for the input
            // (turn 5b). Anybody without JavaScript just gets the input.
            const panel = el('[data-title-panel]');
            const field = el('[data-title-field]');
            if (panel && field && !this.dirty) {
                panel.hidden = false;
                field.hidden = true;
            }

            const own = el('[data-title-own]');
            if (own) {
                own.addEventListener('click', () => {
                    const panel = el('[data-title-panel]');
                    const field = el('[data-title-field]');
                    if (panel) panel.hidden = true;
                    if (field) field.hidden = false;
                    this.dirty = true;
                    this.input.focus();
                });
            }
            this.form.addEventListener('change', () => this.write(), true);
            this.form.addEventListener('input', (e) => {
                if (e.target !== this.input) this.write();
            }, true);
            this.write();
        }

        compose() {
            const year = fieldText('#id_license_year') || fieldText('#id_era_label');
            const county = fieldText(this.cfg.kind === 'collection' ? '#id_county' : '#id_county_ref');
            const residency = fieldText('#id_residency');
            const addons = checkedText('addon_type').filter(n => n.toLowerCase() !== 'other');
            if (!year && !county) return '';
            let name = [year, county && county !== 'Statewide' ? county + ' County' : county, residency]
                .filter(Boolean).join(' ');
            if (addons.length) {
                name += ', ' + addons.map(a => a.toLowerCase()).join(' and ') + ' attached';
            }
            return name;
        }

        write() {
            if (this.dirty) return;
            const made = this.compose();
            if (!made) return;
            this.input.value = made;
            const shown = el('[data-title-made]');
            if (shown) shown.textContent = made;
            this.input.dispatchEvent(new Event('kb-titled'));
        }
    }

    /* ── The description counter ────────────────────────────────────── */

    function counter() {
        const node = el('#id_description');
        const out = el('[data-desc-count]');
        if (!node || !out) return;
        const max = node.getAttribute('maxlength') || 2000;
        const say = () => { out.textContent = node.value.length + ' / ' + max; };
        node.addEventListener('input', say);
        say();
    }

    window.KBItemForm = {
        init(cfg) {
            const slots = new Slots(cfg, (s) => {
                if (window.__kbPreview) window.__kbPreview.paint();
            });
            window.__kbPreview = new Preview(cfg, slots);
            new Title(cfg);
            counter();
            return slots;
        },
    };
})();
