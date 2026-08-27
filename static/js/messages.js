/* ==========================================================================
   Messages — the two panes

   Progressive on purpose: without JavaScript the list is still links, the
   thread still reads on its own scroll, the report form still posts, and
   the picker inputs still accept a typed username.
   ========================================================================== */

(function () {
    'use strict';

    // Open a thread at its newest message, which is what you came for.
    const thread = document.getElementById('message-thread');
    if (thread) thread.scrollTop = thread.scrollHeight;

    // Filter the left pane without a round trip. The server-side chips still
    // work on their own; this is for narrowing a long list while reading.
    const search = document.querySelector('[data-thread-search]');
    if (search) {
        const rows = Array.from(document.querySelectorAll('[data-thread-row]'));
        search.addEventListener('input', () => {
            const term = search.value.trim().toLowerCase();
            rows.forEach((row) => {
                row.hidden = Boolean(term) && !row.textContent.toLowerCase().includes(term);
            });
        });
    }

    /* ── The header menus: open, ×, click-away, Esc ─────────────────── */
    const menus = Array.from(document.querySelectorAll('[data-menu]'));
    const closeAll = () => menus.forEach((menu) => {
        const panel = menu.querySelector('.ms-menu-panel');
        const toggle = menu.querySelector('[data-menu-toggle]');
        if (panel) panel.hidden = true;
        if (toggle) toggle.setAttribute('aria-expanded', 'false');
    });
    menus.forEach((menu) => {
        const toggle = menu.querySelector('[data-menu-toggle]');
        const panel = menu.querySelector('.ms-menu-panel');
        if (!toggle || !panel) return;
        toggle.addEventListener('click', (event) => {
            event.stopPropagation();
            const opening = panel.hidden;
            closeAll();
            panel.hidden = !opening;
            toggle.setAttribute('aria-expanded', opening ? 'true' : 'false');
        });
        panel.addEventListener('click', (event) => event.stopPropagation());
        const x = menu.querySelector('[data-menu-close]');
        if (x) x.addEventListener('click', closeAll);
    });
    if (menus.length) {
        document.addEventListener('click', closeAll);
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') closeAll();
        });
    }

    /* ── Pointing at messages: reveal checkboxes, count the picks ───── */
    const pickToggle = document.querySelector('[data-pick-toggle]');
    if (pickToggle && thread) {
        const sayCount = () => {
            const n = thread.querySelectorAll('[data-pick-box]:checked').length;
            pickToggle.textContent = n
                ? `${n} message${n === 1 ? '' : 's'} picked — pick more or Report`
                : 'Picking messages — tick the ones you mean';
        };
        pickToggle.addEventListener('click', () => {
            const on = thread.classList.toggle('is-picking');
            if (on) sayCount();
            else pickToggle.textContent = 'Point at specific messages';
        });
        thread.addEventListener('change', (event) => {
            if (event.target.matches('[data-pick-box]')
                    && thread.classList.contains('is-picking')) {
                sayCount();
            }
        });
    }

    /* ── The member picker: names you can verify ────────────────────── */
    function wirePicker(input, onPick) {
        const url = input.dataset.pickerUrl;
        const list = input.closest('form, [data-picker-scope]')
            .querySelector('[data-picker-list]');
        if (!url || !list) return;
        let timer = null;

        const hide = () => { list.hidden = true; list.innerHTML = ''; };
        const show = (results) => {
            if (!results.length) { hide(); return; }
            list.innerHTML = results.map((person) =>
                `<button type="button" class="ms-picker-item" data-username="${person.username}">` +
                `${person.username}<small>${person.display === person.username ? '' : person.display}</small></button>`
            ).join('');
            list.hidden = false;
        };

        input.addEventListener('input', () => {
            clearTimeout(timer);
            const term = input.value.trim();
            if (term.length < 2) { hide(); return; }
            timer = setTimeout(async () => {
                try {
                    const response = await fetch(`${url}?q=${encodeURIComponent(term)}`,
                        { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
                    if (response.ok) show((await response.json()).results);
                } catch (error) { hide(); }
            }, 200);
        });
        list.addEventListener('click', (event) => {
            const item = event.target.closest('[data-username]');
            if (!item) return;
            onPick(item.dataset.username);
            hide();
        });
        input.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') hide();
        });
    }

    // Single pick: the add-to-room box — picking fills the input.
    document.querySelectorAll('[data-picker-single] [data-picker-input]').forEach((input) => {
        wirePicker(input, (username) => { input.value = username; input.focus(); });
    });

    // Multi pick: opening a room — picks become pills, pills become the
    // hidden field the server already reads.
    const multi = document.querySelector('[data-picker-multi]');
    if (multi) {
        const input = multi.querySelector('[data-picker-input]');
        const pills = multi.querySelector('[data-picker-pills]');
        const hiddenField = multi.querySelector('[data-picker-value]');
        const picked = [];

        const syncField = () => { hiddenField.value = picked.join(' '); };
        const draw = () => {
            pills.innerHTML = picked.map((name) =>
                `<span class="ms-pill">${name}` +
                `<button type="button" data-unpick="${name}" aria-label="Remove ${name}">&times;</button></span>`
            ).join('');
            syncField();
        };
        pills.addEventListener('click', (event) => {
            const button = event.target.closest('[data-unpick]');
            if (!button) return;
            picked.splice(picked.indexOf(button.dataset.unpick), 1);
            draw();
        });
        wirePicker(input, (username) => {
            if (!picked.includes(username)) picked.push(username);
            input.value = '';
            draw();
            input.focus();
        });
    }
})();
