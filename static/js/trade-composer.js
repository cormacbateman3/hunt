/* The trade composer — moving licences on and off the table.
 *
 * A piece is MOVED between its shelf and the table rather than copied. The
 * checkbox that actually submits travels with it, so what you can see and
 * what gets sent cannot drift apart — which is the failure mode worth
 * designing against on a page where somebody is giving property away.
 *
 * Everything degrades: without this file the whole shelf is rendered, the
 * checkboxes still work, and the server still builds the same offer. The
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

    /* Which side of the table a piece belongs to, read from the field it
     * posts to — the markup already says it, so nothing is stored twice. */
    function sideOf(piece) {
        var box = piece.querySelector('.tb-piece-pick');
        return box && box.name === 'requested_items' ? 'theirs' : 'mine';
    }

    function move(piece, onTable) {
        var side = sideOf(piece);
        (onTable ? tables[side] : shelves[side]).appendChild(piece);
        var say = piece.querySelector('.tb-piece-say');
        if (say) { say.textContent = onTable ? 'Take off the table' : 'Put on the table'; }
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

    function paint() {
        var n = counts();

        form.querySelectorAll('[data-count]').forEach(function (el) {
            el.textContent = n[el.dataset.count];
        });
        form.querySelectorAll('[data-empty]').forEach(function (el) {
            var side = el.dataset.empty;
            var filled = tables[side].querySelectorAll('.tb-piece').length > 0;
            el.classList.toggle('is-hidden', filled);
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
        if (send) { send.disabled = !ready; }
        if (hint) { hint.classList.toggle('is-hidden', ready); }

        form.querySelectorAll('.tb-cash').forEach(function (strip) {
            var radio = strip.querySelector('[name="cash_direction"]');
            var amount = form.querySelector('[name="cash_amount"]');
            var live = amount && parseFloat(amount.value || '0') > 0;
            strip.classList.toggle('is-on', !!(live && radio && radio.checked));
        });

        ['mine', 'theirs'].forEach(function (side) {
            var foot = form.querySelector('[data-foot="' + side + '"]');
            if (!foot) { return; }
            var all = shelves[side].querySelectorAll('.tb-piece');
            var shown = shelves[side].querySelectorAll('.tb-piece:not(.is-hidden)');
            foot.textContent = shown.length + ' of ' + all.length
                + (shown.length === all.length ? '' : ' shown');
        });
    }

    form.addEventListener('change', function (e) {
        if (e.target.classList.contains('tb-piece-pick')) {
            move(e.target.closest('.tb-piece'), e.target.checked);
            paint();
        } else if (e.target.name === 'cash_direction' || e.target.name === 'cash_amount') {
            paint();
        }
    });

    form.addEventListener('input', function (e) {
        if (e.target.name === 'cash_amount') { paint(); }
    });

    /* ── Finding, on the shelves ───────────────────────────────────── */
    var state = { mine: { q: '', filter: '' }, theirs: { q: '', filter: '' } };

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

    function noteFor(filter) {
        return { wants: 'wanted', dupes: 'duplicate', gaps: 'gap' }[filter] || filter;
    }

    function isPre1950(hay) {
        var year = hay.match(/\b(1[89]\d{2})\b/);
        return !!year && parseInt(year[1], 10) < 1950;
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
