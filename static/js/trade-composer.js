/* The trade composer — putting licences on the table and taking them off.
 *
 * The shelf is the source of truth. Its checkbox is what submits, and it
 * keeps its row whatever happens; the table shows a CLONE of that row as a
 * cream card. That is how the design draws it — a piece is in both places
 * at once, tinted and ticked on the shelf, laid out on the table — and it
 * means the thing you can see and the thing that gets sent cannot drift
 * apart, which is the failure mode worth designing against on a page where
 * somebody is giving property away.
 *
 * Everything degrades: without this file the server has already rendered
 * both sides, the checkboxes still work, and the same offer is built. The
 * search box and the chips simply do nothing, and nothing is hidden.
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
    var hint = document.getElementById('tb-hint');
    var termsTop = document.getElementById('tb-terms');
    var termsBand = document.getElementById('tb-band-terms');

    /* Which side a piece belongs to, read from the field it posts to — the
     * markup already says it, so nothing is stored twice. */
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
        /* The clone must not submit — one checkbox per piece, on the shelf. */
        var box = card.querySelector('.tb-piece-pick');
        if (box) { box.remove(); }
        card.classList.remove('is-hidden');

        var hit = card.querySelector('.tb-piece-hit');
        var swap = document.createElement('span');
        swap.className = 'tb-piece-hit';
        while (hit.firstChild) { swap.appendChild(hit.firstChild); }
        hit.replaceWith(swap);

        var mark = swap.querySelector('.tb-piece-mark');
        if (mark) {
            var drop = document.createElement('button');
            drop.type = 'button';
            drop.className = 'tb-piece-mark';
            drop.dataset.drop = row.dataset.pk;
            drop.innerHTML = '<span class="kb-sr">Take off the table</span>';
            mark.replaceWith(drop);
        }
        var say = swap.querySelector('.tb-piece-say');
        if (say) { say.remove(); }

        tables[sideOf(row)].appendChild(card);
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
        var amount = form.querySelector('[name="cash_amount"]');
        var value = amount ? parseFloat(amount.value || '0') : 0;
        if (!value) { return ''; }
        var toMe = form.querySelector('[name="cash_direction"]:checked');
        var money = '$' + value.toFixed(2).replace(/\.00$/, '');
        return ', and ' + money + (toMe && toMe.value === 'to_proposer' ? ' to me' : ' from me');
    }

    function money() {
        var amount = form.querySelector('[name="cash_amount"]');
        var value = amount ? parseFloat(amount.value || '0') : 0;
        var side = form.querySelector('[name="cash_direction"]:checked');
        var live = side ? side.value : null;

        form.querySelectorAll('.tb-cash').forEach(function (strip) {
            var on = !!value && strip.dataset.cash === live;
            strip.classList.toggle('is-on', on);
            var figure = strip.querySelector('.tb-cash-figure');
            if (figure) {
                figure.textContent = on ? '$' + value.toFixed(2) : '$0';
            }
        });
    }

    function paint() {
        var n = counts();

        form.querySelectorAll('[data-count]').forEach(function (el) {
            el.textContent = n[el.dataset.count];
        });

        /* Two readings of one deal, matching the server's: the table takes
         * the short one, the band the longer one it is asking you to agree
         * to. "their", never a guessed pronoun. */
        var cash = cashPart();
        var empty = !(n.give || n.get);
        if (termsTop) {
            termsTop.textContent = empty ? 'Nothing on the table yet'
                : n.give + ' for ' + n.get + cash;
        }
        if (termsBand) {
            termsBand.textContent = empty ? 'Nothing on the table yet'
                : 'My ' + n.give + ' for their ' + n.get + cash;
        }

        /* A trade needs something from you. The button says so by being off,
         * and the line underneath says why — a disabled control with no
         * explanation is the same as a broken one. */
        var ready = n.give > 0;
        if (send && send.dataset.always !== 'on') { send.disabled = !ready; }
        if (hint) { hint.classList.toggle('is-hidden', ready); }

        money();

        ['mine', 'theirs'].forEach(function (side) {
            var foot = form.querySelector('[data-foot="' + side + '"]');
            if (!foot) { return; }
            var all = shelves[side].querySelectorAll('.tb-piece');
            var shown = shelves[side].querySelectorAll('.tb-piece:not(.is-hidden)');
            foot.textContent = shown.length + ' of ' + all.length
                + (shown.length === all.length ? ' · scroll' : ' shown');
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
        } else if (e.target.name === 'cash_direction' || e.target.name === 'cash_amount') {
            paint();
        }
    });

    form.addEventListener('input', function (e) {
        if (e.target.name === 'cash_amount') { paint(); }
    });

    /* The × on a card reaches back to the shelf, because that is where the
     * checkbox that actually submits lives. */
    form.addEventListener('click', function (e) {
        var drop = e.target.closest('[data-drop]');
        if (!drop) { return; }
        e.preventDefault();
        var box = form.querySelector('.tb-piece-pick[value="' + drop.dataset.drop + '"]');
        if (box) { box.checked = false; box.dispatchEvent(new Event('change', {bubbles: true})); }
    });

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

    form.querySelectorAll('.tb-find-input').forEach(function (input) {
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
