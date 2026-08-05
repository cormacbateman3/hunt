/* The trade composer — putting licences on the table and taking them off.
 *
 * The shelf is the source of truth. Its checkbox is what submits, and it
 * keeps its row whatever happens; the give/receive column shows a CLONE of
 * that row as a card. A piece is in both places at once — ticked on the
 * shelf, laid out in the column — which means the thing you can see and the
 * thing that gets sent cannot drift apart. That is the failure worth
 * designing against on a page where somebody gives property away.
 *
 * Everything degrades: without this file the server has already rendered
 * both sides, the checkboxes still work, and the same offer is built. The
 * search, the chips and the closer look simply do nothing.
 */
(function () {
    'use strict';

    var form = document.getElementById('tb-composer');
    if (!form) { return; }

    var shelves = {
        mine: form.querySelector('[data-shelf="mine"]'),
        theirs: form.querySelector('[data-shelf="theirs"]')
    };
    var tables = {
        mine: form.querySelector('[data-table="mine"]'),
        theirs: form.querySelector('[data-table="theirs"]')
    };
    var send = document.getElementById('tb-send');
    var termsBand = document.getElementById('tb-band-terms');

    function sideOf(row) {
        var box = row.querySelector('.tb-piece-pick');
        return box && box.name === 'requested_items' ? 'theirs' : 'mine';
    }

    function cardFor(row) {
        return tables[sideOf(row)].querySelector('.tb-piece[data-pk="' + row.dataset.pk + '"]');
    }

    function lay(row) {
        if (cardFor(row)) { return; }
        var card = row.cloneNode(true);
        var box = card.querySelector('.tb-piece-pick');
        if (box) { box.remove(); }
        card.classList.remove('is-hidden');

        /* A label inside a label would steal the click; the card is inert. */
        var hit = card.querySelector('.tb-piece-hit');
        var inert = document.createElement('span');
        inert.className = 'tb-piece-hit';
        while (hit.firstChild) { inert.appendChild(hit.firstChild); }
        hit.replaceWith(inert);

        /* The card carries county·year, not the shelf's reason line. */
        var note = inert.querySelector('.tb-piece-note');
        if (note) {
            note.className = 'tb-piece-note tb-piece-note--plain';
            note.textContent = (row.dataset.meta || '').replace(/&middot;/g, '·');
        }

        var mark = inert.querySelector('.tb-piece-mark');
        var drop = document.createElement('button');
        drop.type = 'button';
        drop.className = 'tb-piece-mark tb-piece-mark--drop';
        drop.dataset.drop = row.dataset.pk;
        drop.innerHTML = '<span class="kb-sr">Take off the table</span>';
        if (mark) { mark.replaceWith(drop); } else { inert.appendChild(drop); }

        var say = inert.querySelector('.tb-piece-say');
        if (say) { say.remove(); }

        /* The dashed hint lives inside the list, so cards go in front of it. */
        var table = tables[sideOf(row)];
        table.insertBefore(card, table.querySelector('.tb-drop'));
    }

    function clear(row) {
        var card = cardFor(row);
        if (card) { card.remove(); }
    }

    function counts() {
        return {
            give: tables.mine.querySelectorAll('.tb-piece').length,
            get: tables.theirs.querySelectorAll('.tb-piece').length
        };
    }

    function cashPart() {
        var mine = parseFloat((form.querySelector('[name="cash_i_add"]') || {}).value || '0');
        var theirs = parseFloat((form.querySelector('[name="cash_to_me"]') || {}).value || '0');
        if (mine > 0) { return ', and $' + mine.toFixed(2).replace(/\.00$/, '') + ' from me'; }
        if (theirs > 0) { return ', and $' + theirs.toFixed(2).replace(/\.00$/, '') + ' to me'; }
        return '';
    }

    function paint() {
        var n = counts();

        form.querySelectorAll('[data-count]').forEach(function (el) {
            var count = n[el.dataset.count];
            el.textContent = count + ' item' + (count === 1 ? '' : 's');
        });

        if (termsBand) {
            termsBand.textContent = (n.give || n.get)
                ? 'My ' + n.give + ' for their ' + n.get + cashPart()
                : 'Nothing on the table yet';
        }

        /* A trade needs something from you. The button says so by being off. */
        if (send && send.classList.contains('tb-decide--go')) {
            send.disabled = !(n.give > 0);
        }

        ['mine', 'theirs'].forEach(function (side) {
            var foot = form.querySelector('[data-foot="' + side + '"]');
            if (!foot) { return; }
            var all = shelves[side].querySelectorAll('.tb-piece').length;
            var shown = shelves[side].querySelectorAll('.tb-piece:not(.is-hidden)').length;
            foot.textContent = 'Showing ' + shown + ' of ' + all
                + (shown === all ? ' · scroll for more' : ' · filtered');
        });
    }

    form.addEventListener('change', function (e) {
        if (e.target.classList.contains('tb-piece-pick')) {
            var row = e.target.closest('.tb-piece');
            row.classList.toggle('is-on-table', e.target.checked);
            if (e.target.checked) { lay(row); } else { clear(row); }
            var say = row.querySelector('.tb-piece-say');
            if (say) { say.textContent = e.target.checked ? 'Take off the table' : 'Put on the table'; }
            paint();
        }
    });

    /* Cash runs one way. Typing in one box empties the other rather than
     * waiting for the server to say no. */
    form.addEventListener('input', function (e) {
        if (e.target.name === 'cash_i_add' || e.target.name === 'cash_to_me') {
            var other = form.querySelector(
                '[name="' + (e.target.name === 'cash_i_add' ? 'cash_to_me' : 'cash_i_add') + '"]');
            if (other && parseFloat(e.target.value || '0') > 0) { other.value = ''; }
            paint();
        }
    });

    form.addEventListener('click', function (e) {
        var drop = e.target.closest('[data-drop]');
        if (!drop) { return; }
        e.preventDefault();
        var box = form.querySelector('.tb-piece-pick[value="' + drop.dataset.drop + '"]');
        if (box) { box.checked = false; box.dispatchEvent(new Event('change', { bubbles: true })); }
    });

    /* ── Dragging ──────────────────────────────────────────────────── */
    function setPick(pk, on) {
        var box = form.querySelector('.tb-piece-pick[value="' + pk + '"]');
        if (!box || box.disabled || box.checked === on) { return; }
        box.checked = on;
        box.dispatchEvent(new Event('change', { bubbles: true }));
    }

    form.addEventListener('dragstart', function (e) {
        var piece = e.target.closest('.tb-piece');
        if (!piece || piece.classList.contains('is-held')) { return; }
        hideLook();
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', piece.dataset.pk);
        piece.classList.add('is-lifting');
        form.dataset.dragging = piece.dataset.side;
    });

    form.addEventListener('dragend', function (e) {
        var piece = e.target.closest('.tb-piece');
        if (piece) { piece.classList.remove('is-lifting'); }
        delete form.dataset.dragging;
        form.querySelectorAll('.is-drop-target').forEach(function (zone) {
            zone.classList.remove('is-drop-target');
        });
    });

    function zoneFor(target) {
        var laid = target.closest('.tb-laid');
        if (laid) { return { el: laid, side: laid.dataset.table, on: true }; }
        var shelf = target.closest('.tb-shelf');
        if (shelf) { return { el: shelf, side: shelf.dataset.shelf, on: false }; }
        return null;
    }

    form.addEventListener('dragover', function (e) {
        var zone = zoneFor(e.target);
        if (!zone || zone.side !== form.dataset.dragging) { return; }
        e.preventDefault();
        e.dataTransfer.dropEffect = 'move';
        zone.el.classList.add('is-drop-target');
    });

    form.addEventListener('dragleave', function (e) {
        var zone = zoneFor(e.target);
        if (zone && !zone.el.contains(e.relatedTarget)) {
            zone.el.classList.remove('is-drop-target');
        }
    });

    form.addEventListener('drop', function (e) {
        var zone = zoneFor(e.target);
        if (!zone || zone.side !== form.dataset.dragging) { return; }
        e.preventDefault();
        zone.el.classList.remove('is-drop-target');
        setPick(e.dataTransfer.getData('text/plain'), zone.on);
    });

    /* ── A closer look ─────────────────────────────────────────────────
     * A 36×28 thumbnail tells you a licence from a tag and nothing else.
     * Hovering opens the piece properly, beside the cursor and clear of
     * the shelf's own scroll box — which is why it lives on <body>. */
    var look = document.createElement('div');
    look.className = 'tb-look';
    look.hidden = true;
    look.innerHTML = '<img class="tb-look-media" alt="">'
        + '<div class="tb-look-body"><span class="tb-look-title"></span>'
        + '<span class="tb-look-meta"></span><span class="tb-look-note"></span></div>';
    document.body.appendChild(look);

    var media = look.querySelector('.tb-look-media');
    var opening = null;

    function hideLook() {
        clearTimeout(opening);
        look.hidden = true;
    }

    function showLook(piece) {
        var image = piece.dataset.image;
        if (image) { media.src = image; media.hidden = false; } else { media.hidden = true; }
        look.querySelector('.tb-look-title').textContent = piece.dataset.title || '';
        look.querySelector('.tb-look-meta').textContent =
            (piece.dataset.meta || '').replace(/&middot;/g, '·');
        look.querySelector('.tb-look-note').textContent = piece.dataset.noteText || '';

        var box = piece.getBoundingClientRect();
        look.hidden = false;
        var size = look.getBoundingClientRect();
        /* Left of the row when there is no room to its right, and nudged up
         * when it would run off the bottom. */
        var left = box.right + 12;
        if (left + size.width > window.innerWidth - 8) { left = box.left - size.width - 12; }
        var top = Math.min(box.top, window.innerHeight - size.height - 8);
        look.style.left = Math.max(8, left) + 'px';
        look.style.top = Math.max(8, top) + 'px';
    }

    form.addEventListener('mouseover', function (e) {
        var piece = e.target.closest('.tb-piece');
        if (!piece || form.dataset.dragging) { return hideLook(); }
        clearTimeout(opening);
        opening = setTimeout(function () { showLook(piece); }, 260);
    });

    form.addEventListener('mouseout', function (e) {
        if (!e.relatedTarget || !e.relatedTarget.closest('.tb-piece')) { hideLook(); }
    });

    form.addEventListener('scroll', hideLook, true);
    window.addEventListener('scroll', hideLook, { passive: true });

    /* ── Finding, on the shelves ───────────────────────────────────── */
    var state = { mine: { q: '', filter: '' }, theirs: { q: '', filter: '' } };

    function noteFor(filter) {
        return { wants: 'wanted', dupes: 'duplicate', gaps: 'gap' }[filter] || filter;
    }

    function isPre1950(hay) {
        var year = hay.match(/\b(1[89]\d{2})\b/);
        return !!year && parseInt(year[1], 10) < 1950;
    }

    function sift(side) {
        var q = state[side].q.toLowerCase();
        var f = state[side].filter;
        shelves[side].querySelectorAll('.tb-piece').forEach(function (piece) {
            var hay = piece.dataset.find || '';
            var kind = piece.dataset.note || '';
            var ok = (!q || hay.indexOf(q) !== -1)
                && (!f || (f === 'pre1950' ? isPre1950(hay) : kind === noteFor(f)));
            piece.classList.toggle('is-hidden', !ok);
        });
        paint();
    }

    form.querySelectorAll('.tb-find').forEach(function (input) {
        input.addEventListener('input', function () {
            state[input.dataset.findFor].q = input.value.trim();
            sift(input.dataset.findFor);
        });
    });

    form.querySelectorAll('.tb-chip').forEach(function (chip) {
        chip.addEventListener('click', function () {
            var side = chip.dataset.for;
            var on = state[side].filter === chip.dataset.filter;
            state[side].filter = on ? '' : chip.dataset.filter;
            form.querySelectorAll('.tb-chip[data-for="' + side + '"]').forEach(function (other) {
                other.classList.toggle('is-on', other === chip && !on);
            });
            sift(side);
        });
    });

    paint();
}());
