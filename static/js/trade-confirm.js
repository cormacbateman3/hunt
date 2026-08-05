/* The accept confirmation.
 *
 * Turn 3a: "Accept goes to the confirmation screen your plan already
 * requires, never straight through." Accepting commits property in both
 * directions at once and cannot be taken back, which is the one case on the
 * site where a second look is worth the extra click.
 *
 * Without this file the dialog stays in the page with `hidden` on it and
 * `Review & accept` does nothing — so the fallback is a screen that cannot
 * accept, never one that accepts without asking.
 */
(function () {
    'use strict';

    var box = document.getElementById('tb-accept');
    var open = document.getElementById('tb-accept-open');
    var close = document.getElementById('tb-accept-close');
    if (!box || !open) { return; }

    var returnTo = null;

    function show() {
        returnTo = document.activeElement;
        box.hidden = false;
        var first = box.querySelector('button, [href]');
        if (first) { first.focus(); }
    }

    function hide() {
        box.hidden = true;
        if (returnTo) { returnTo.focus(); }
    }

    open.addEventListener('click', show);
    if (close) { close.addEventListener('click', hide); }
    box.addEventListener('click', function (e) { if (e.target === box) { hide(); } });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && !box.hidden) { hide(); }
    });
}());
