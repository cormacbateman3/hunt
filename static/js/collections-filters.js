/* ==========================================================================
   Everything owned — the filter bar
   Spec: design turn 13b (behaviour) and 18a (the two defects it inherited).

   Three things this file has to get right:

   1. Apply is gone. The grid updates as you go, which is what the
      multi-select panels always implied.
   2. Fetch first, clear second. The old handler emptied the county and all
      six license-type selects and *then* fetched replacements inside a bare
      Promise.all with no catch — so a dropped connection left a filter bar
      full of "Any" in a state that definitely has counties, with nothing on
      the page to suggest a retry would help.
   3. The panel is a child of its trigger. It used to be appended to
      document.body and positioned once, so any scroll or resize left a live
      checkbox list floating over unrelated rows — and six of them sit in a
      strip that scrolls sideways on any narrow window, so that was the
      normal case rather than a corner.
   ========================================================================== */

(function () {
    'use strict';

    const form = document.querySelector('[data-live-filters]');
    if (!form) return;

    const errorLine = document.getElementById('ow-filter-error');
    const stateSelect = document.getElementById('state_id');
    const countySelect = document.getElementById('county_id');
    const countyLabel = document.getElementById('county-label');
    const LT_CATS = ['residency', 'holder_eligibility', 'activity_scope',
                     'duration', 'addon_type', 'material'];

    let lastGoodState = stateSelect ? stateSelect.value : '';
    let submitting = false;

    function submit() {
        if (submitting) return;
        submitting = true;
        // Page 4 of the old result set is meaningless against the new one.
        const page = form.querySelector('input[name="page"]');
        if (page) page.remove();
        form.submit();
    }

    function say(message) {
        if (!errorLine) return;
        errorLine.textContent = message || '';
        errorLine.hidden = !message;
    }

    /* ── Live filtering ──────────────────────────────────────────────────
       `change` rather than `input` on the text boxes: it fires on blur and
       on Enter, so a collector can finish typing a county name without the
       page reloading under them mid-word. */
    form.addEventListener('change', (event) => {
        const el = event.target;
        if (!el.name || el.multiple) return;      // panels submit on close
        if (el === stateSelect) return;           // handled below, after the fetch
        submit();
    });

    form.addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && event.target.tagName === 'INPUT') {
            event.preventDefault();
            submit();
        }
    });

    /* ── State change: fetch first, clear second ─────────────────────── */
    function fillSelect(select, options, placeholder) {
        select.innerHTML = '';
        if (placeholder !== null) {
            const any = document.createElement('option');
            any.value = '';
            any.textContent = placeholder;
            select.appendChild(any);
        }
        options.forEach((row) => {
            const opt = document.createElement('option');
            opt.value = row.id;
            opt.textContent = row.name;
            select.appendChild(opt);
        });
    }

    if (stateSelect) {
        stateSelect.addEventListener('change', async () => {
            const stateId = stateSelect.value;
            say('');

            if (!stateId) {
                lastGoodState = '';
                submit();
                return;
            }

            const stateName = stateSelect.options[stateSelect.selectedIndex].text;
            stateSelect.disabled = true;

            let geoData, ltData;
            try {
                [geoData, ltData] = await Promise.all([
                    fetch(`/api/geo-units/?state=${encodeURIComponent(stateId)}`)
                        .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }),
                    fetch(`/api/license-types/?state=${encodeURIComponent(stateId)}`)
                        .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); }),
                ]);
            } catch (err) {
                // Nothing has been cleared yet, so the bar the collector was
                // using is still intact. Put the old state back and say why.
                stateSelect.value = lastGoodState;
                stateSelect.disabled = false;
                say(`Couldn’t load ${stateName}. Check your connection and try again.`);
                return;
            }

            // Both responses are in hand — only now is it safe to replace.
            if (countySelect) {
                fillSelect(countySelect, geoData.results || [], 'Any');
                if (countyLabel) countyLabel.textContent = geoData.issuance_unit_label || 'County';
            }
            LT_CATS.forEach((cat) => {
                const select = document.getElementById(`${cat}_id`);
                if (!select) return;
                fillSelect(select, (ltData.results && ltData.results[cat]) || [], null);
                if (select._msRebuild) select._msRebuild();
            });

            lastGoodState = stateId;
            stateSelect.disabled = false;
            submit();
        });
    }

    /* ── Multi-select ────────────────────────────────────────────────────
       The panel is an absolutely positioned child of the filter item, so it
       moves with its trigger for free — no repositioning to forget. */
    let openPanel = null;

    function closePanel(andSubmit) {
        if (!openPanel) return;
        const changed = openPanel._changed;
        openPanel.remove();
        openPanel = null;
        if (changed && andSubmit !== false) submit();
    }

    document.addEventListener('click', () => closePanel(true));
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closePanel(true); });

    function buildMultiSelect(select) {
        const wrapper = select.parentElement;
        const name = select.dataset.msLabel || 'Any';
        select.style.display = 'none';

        const trigger = document.createElement('button');
        trigger.type = 'button';
        trigger.className = 'ms-trigger';
        select._msTrigger = trigger;
        wrapper.appendChild(trigger);

        function updateLabel() {
            const chosen = Array.from(select.selectedOptions).filter((o) => o.value);
            trigger.textContent = name;
            if (chosen.length) {
                const badge = document.createElement('span');
                badge.className = 'ms-trigger-count';
                badge.textContent = chosen.length;
                trigger.appendChild(document.createTextNode(' '));
                trigger.appendChild(badge);
            }
            trigger.dataset.active = chosen.length > 0 ? 'true' : 'false';
        }
        updateLabel();

        function buildPanel() {
            const panel = document.createElement('div');
            panel.className = 'ms-panel';
            panel._changed = false;

            Array.from(select.options).forEach((opt) => {
                if (!opt.value) return;
                const label = document.createElement('label');
                label.className = 'ms-option';
                const box = document.createElement('input');
                box.type = 'checkbox';
                box.value = opt.value;
                box.checked = opt.selected;
                box.addEventListener('change', () => {
                    opt.selected = box.checked;
                    panel._changed = true;
                    updateLabel();
                });
                label.appendChild(box);
                label.appendChild(document.createTextNode(' ' + opt.text));
                panel.appendChild(label);
            });

            if (!panel.children.length) {
                const none = document.createElement('p');
                none.className = 'ms-none';
                none.textContent = 'Nothing recorded for this state yet.';
                panel.appendChild(none);
            }

            panel.addEventListener('click', (e) => e.stopPropagation());
            return panel;
        }

        // Called after the options are swapped for a new state.
        select._msRebuild = () => {
            if (openPanel && openPanel._owner === select) closePanel(false);
            updateLabel();
        };

        trigger.addEventListener('click', (e) => {
            e.stopPropagation();
            if (openPanel && openPanel._owner === select) { closePanel(true); return; }
            closePanel(true);
            const panel = buildPanel();
            panel._owner = select;
            wrapper.appendChild(panel);
            openPanel = panel;
        });
    }

    document.querySelectorAll('select[data-ms]').forEach(buildMultiSelect);
})();
