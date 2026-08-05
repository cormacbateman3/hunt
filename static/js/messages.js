/* ==========================================================================
   Messages — the two panes

   Two small jobs. Neither is required for the page to work: without
   JavaScript the list is still a list of links and the thread still reads
   bottom-up on its own scroll.
   ========================================================================== */

(function () {
    'use strict';

    // Open a thread at its newest message, which is what you came for.
    const thread = document.getElementById('message-thread');
    if (thread) thread.scrollTop = thread.scrollHeight;

    // Filter the left pane without a round trip. The server-side chips still
    // work on their own; this is for narrowing a long list while reading.
    const search = document.querySelector('[data-thread-search]');
    if (!search) return;

    const rows = Array.from(document.querySelectorAll('[data-thread-row]'));
    search.addEventListener('input', () => {
        const term = search.value.trim().toLowerCase();
        rows.forEach((row) => {
            row.hidden = Boolean(term) && !row.textContent.toLowerCase().includes(term);
        });
    });
})();
