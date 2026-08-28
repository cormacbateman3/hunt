// Vanilla JavaScript utilities for Backtag.

function fadeOutMessages() {
    const messages = document.querySelectorAll('[role="alert"]');
    messages.forEach((message) => {
        setTimeout(() => {
            message.style.transition = 'opacity 0.4s ease';
            message.style.opacity = '0';
            setTimeout(() => message.remove(), 400);
        }, 5000);
    });
}

function formatDuration(ms) {
    // "Closing…" while the lazy close lands — never the word EXPIRED.
    if (ms <= 0) {
        return 'Closing…';
    }

    const totalSeconds = Math.floor(ms / 1000);
    const days = Math.floor(totalSeconds / 86400);
    const hours = Math.floor((totalSeconds % 86400) / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    // Lead with the largest unit that exists — "0d 0h 12m" read like a
    // malfunction exactly when people were watching hardest.
    if (days) return `${days}d ${hours}h ${minutes}m`;
    if (hours) return `${hours}h ${minutes}m ${seconds}s`;
    if (minutes) return `${minutes}m ${seconds}s`;
    return `${seconds}s`;
}

function startCountdown(element) {
    if (!element.dataset.auctionEnd) {
        return;
    }

    const tick = () => {
        // The poll keeps dataset.auctionEnd fresh (soft close moves it),
        // and __kbClockOffset corrects for the client's own clock.
        const offset = window.__kbClockOffset || 0;
        const distance = new Date(element.dataset.auctionEnd).getTime()
            - (Date.now() + offset);
        element.textContent = formatDuration(distance);
        element.classList.toggle('is-critical', distance > 0 && distance <= 120000);
    };

    tick();
    setInterval(tick, 1000);
}

function initBidFormValidation() {
    document.querySelectorAll('[data-bid-form]').forEach((form) => {
        const amountInput = form.querySelector('input[name="amount"]');
        const minBidElement = document.querySelector('#min-bid-value');
        const helperElement = document.querySelector('#min-bid-helper');

        if (!amountInput || !minBidElement) {
            return;
        }

        const syncMinimum = () => {
            const minValue = minBidElement.textContent.trim();
            amountInput.min = minValue;
            if (helperElement) {
                helperElement.textContent = minValue;
            }
        };

        syncMinimum();

        form.addEventListener('submit', (event) => {
            syncMinimum();
            const minValue = Number.parseFloat(amountInput.min || '0');
            const submitted = Number.parseFloat(amountInput.value || '0');
            if (submitted < minValue) {
                event.preventDefault();
                alert(`Bid amount must be at least $${minValue.toFixed(2)}.`);
            }
        });
    });
}

// Q&A, bid history and shipping live in tabs so the listing page has a
// bottom. Progressive enhancement: with no JS every panel is simply visible.
function initTabs() {
    document.querySelectorAll('[data-tabs]').forEach((group) => {
        const tabs = Array.from(group.querySelectorAll('[data-tab-target]'));
        if (tabs.length === 0) return;

        const panels = tabs
            .map((tab) => document.getElementById(tab.dataset.tabTarget))
            .filter(Boolean);

        const show = (index) => {
            tabs.forEach((tab, i) => tab.setAttribute('aria-selected', i === index ? 'true' : 'false'));
            panels.forEach((panel, i) => { panel.hidden = i !== index; });
        };

        tabs.forEach((tab, index) => {
            tab.addEventListener('click', () => show(index));
            tab.addEventListener('keydown', (e) => {
                if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
                e.preventDefault();
                const next = (index + (e.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
                tabs[next].focus();
                show(next);
            });
        });

        show(0);
    });
}

// One-tap bidding. A collector deciding in the last two minutes should not
// have to type a figure.
function initQuickBids() {
    const buttons = document.querySelectorAll('[data-quick-bid]');
    if (buttons.length === 0) return;

    buttons.forEach((button) => {
        button.addEventListener('click', () => {
            const form = button.closest('form');
            const input = form ? form.querySelector('input[name="amount"]') : null;
            if (!input) return;
            input.value = button.dataset.quickBid;
            input.focus();
        });
    });
}

function initGallery() {
    const mainImage = document.querySelector('[data-gallery-main]');
    const thumbs = Array.from(document.querySelectorAll('[data-gallery-thumb]'));
    if (!mainImage || thumbs.length === 0) {
        return;
    }

    const sources = thumbs
        .map((thumb) => thumb.dataset.fullSrc)
        .filter((src) => Boolean(src));
    let currentIndex = Math.max(sources.indexOf(mainImage.src), 0);

    const setImage = (index) => {
        currentIndex = (index + sources.length) % sources.length;
        mainImage.src = sources[currentIndex];
        thumbs.forEach((thumb, i) => thumb.classList.toggle('is-on', i === currentIndex));
    };

    thumbs.forEach((thumb, index) => {
        thumb.addEventListener('click', () => setImage(index));
    });

    const prevButton = document.querySelector('[data-gallery-prev]');
    const nextButton = document.querySelector('[data-gallery-next]');
    const zoomButton = document.querySelector('[data-gallery-zoom]');

    if (prevButton) {
        prevButton.addEventListener('click', () => setImage(currentIndex - 1));
    }
    if (nextButton) {
        nextButton.addEventListener('click', () => setImage(currentIndex + 1));
    }
    if (zoomButton) {
        zoomButton.addEventListener('click', () => window.open(mainImage.src, '_blank'));
    }
}

/* ── The live auction panel ─────────────────────────────────────────────
   One poll loop, pacing itself by the clock: 10s at a distance, 5s inside
   ten minutes, 2s inside the closing window — and 30s when the tab is
   hidden. The last five minutes are the whole point: the room feed shows
   every bid as it lands, an extension announces itself, and when the
   lot closes the page swaps to the truth instead of a frozen countdown. */

function initAuctionLive() {
    const host = document.querySelector('[data-poll-url]');
    if (!host) return;
    const endpoint = host.dataset.pollUrl;
    if (!endpoint) return;

    const bidTarget = document.querySelector(host.dataset.bidTarget || '');
    const countTarget = document.querySelector(host.dataset.bidCountTarget || '');
    const minTarget = document.querySelector(host.dataset.minBidTarget || '');
    const endTarget = document.querySelector(host.dataset.auctionEndTarget || '');
    const room = document.querySelector('[data-room]');
    const roomFeed = document.querySelector('[data-room-feed]');
    const roomNote = document.querySelector('[data-room-note]');
    const standing = document.querySelector('[data-your-standing]');
    const reduced = window.matchMedia
        && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    let lastEnd = null;
    let lastPrice = null;
    let lastLeading = null;
    let wasActive = null;
    let closing = false;

    const secondsLeft = () => {
        if (!lastEnd) return Infinity;
        const offset = window.__kbClockOffset || 0;
        return (new Date(lastEnd).getTime() - (Date.now() + offset)) / 1000;
    };

    const cadence = () => {
        if (document.hidden) return 30000;
        const left = secondsLeft();
        if (left <= 150) return 2000;
        if (left <= 600) return 5000;
        return 10000;
    };

    const ago = (iso) => {
        const offset = window.__kbClockOffset || 0;
        const s = Math.max(0, Math.round((Date.now() + offset - new Date(iso).getTime()) / 1000));
        if (s < 60) return s + 's ago';
        if (s < 3600) return Math.floor(s / 60) + 'm ago';
        return Math.floor(s / 3600) + 'h ago';
    };

    const flash = (node) => {
        if (!node || reduced) return;
        node.classList.remove('lst-flash');
        void node.offsetWidth;   // restart the animation
        node.classList.add('lst-flash');
    };

    const renderFeed = (payload) => {
        if (!room || !roomFeed) return;
        const open = payload.is_active;
        const show = open && secondsLeft() <= 300 && payload.feed && payload.feed.length;
        room.hidden = !show;
        if (!show) return;
        const topKey = payload.feed[0] && payload.feed[0].at + payload.feed[0].amount;
        const changed = topKey && topKey !== room.dataset.topKey;
        room.dataset.topKey = topKey || '';
        roomFeed.innerHTML = payload.feed.slice(0, 5).map((bid, i) =>
            '<li class="lst-room-row' + (i === 0 && changed && !reduced ? ' is-new' : '') + '">' +
            '<strong>$' + Number(bid.amount).toFixed(2) + '</strong>' +
            '<span>' + bid.bidder + (bid.auto ? ' · auto' : '') + '</span>' +
            '<time>' + ago(bid.at) + '</time></li>'
        ).join('');
        if (roomNote) {
            roomNote.textContent = payload.extensions > 0
                ? 'extended ×' + payload.extensions : '';
        }
    };

    const render = (payload) => {
        // Correct the countdown for client clock skew.
        if (payload.server_time) {
            window.__kbClockOffset = new Date(payload.server_time).getTime() - Date.now();
        }

        if (bidTarget && payload.current_bid) {
            if (lastPrice !== null && payload.current_bid !== lastPrice) {
                flash(bidTarget.closest('.lst-big') || bidTarget);
            }
            bidTarget.textContent = payload.current_bid;
            lastPrice = payload.current_bid;
        }
        if (countTarget && typeof payload.bid_count !== 'undefined') {
            countTarget.textContent = payload.bid_count;
        }
        if (minTarget && payload.minimum_bid) {
            minTarget.textContent = payload.minimum_bid;
        }

        if (payload.auction_end) {
            if (endTarget) endTarget.dataset.auctionEnd = payload.auction_end;
            if (lastEnd && payload.is_active
                    && new Date(payload.auction_end) > new Date(lastEnd)) {
                // Soft close: say it where everyone is looking.
                if (roomNote) {
                    roomNote.textContent = 'Extended — two more minutes for everyone.';
                }
                flash(endTarget);
            }
            lastEnd = payload.auction_end;
        }

        if (standing && typeof payload.is_leading !== 'undefined') {
            if (lastLeading === true && payload.is_leading === false) {
                standing.classList.add('is-outbid');
                const strong = standing.querySelector('strong');
                standing.innerHTML = 'Your maximum: <strong>'
                    + (strong ? strong.textContent : '')
                    + '</strong> · you’ve been outbid — raise it to answer.';
            }
            lastLeading = payload.is_leading;
        }

        renderFeed(payload);

        // The lot closed while we watched: the server has already run the
        // close (the poll triggers it), so a reload renders the outcome —
        // the won-panel, the sold line, the works.
        if (wasActive === true && payload.is_active === false && !closing) {
            closing = true;
            setTimeout(() => window.location.reload(), 800);
        }
        wasActive = payload.is_active;
    };

    let timer = null;
    const tick = async () => {
        try {
            const response = await fetch(endpoint, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            if (response.ok) render(await response.json());
        } catch (error) {
            // Keep polling even when intermittent requests fail.
        }
        if (!closing) timer = setTimeout(tick, cadence());
    };
    tick();
    document.addEventListener('visibilitychange', () => {
        // Coming back to the tab deserves a fresh look right away —
        // one loop only, so the pending timer dies first.
        if (!document.hidden && !closing) {
            clearTimeout(timer);
            tick();
        }
    });
}

function initNav() {
    // Mobile toggle for the three destinations
    const toggle = document.getElementById('kb-nav-toggle');
    const topbar = document.getElementById('kb-topbar');
    if (toggle && topbar) {
        toggle.addEventListener('click', () => {
            const open = topbar.classList.toggle('is-open');
            toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
        });
    }

    // Account menu — profile, settings, sign out and nothing else
    const account = document.getElementById('kb-account');
    const accountBtn = account ? account.querySelector('.kb-avatar') : null;
    if (account && accountBtn) {
        accountBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const open = account.classList.toggle('is-open');
            accountBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && account.classList.contains('is-open')) {
                account.classList.remove('is-open');
                accountBtn.setAttribute('aria-expanded', 'false');
                accountBtn.focus();
            }
        });
    }

    document.addEventListener('click', () => {
        document.querySelectorAll('.kb-account.is-open').forEach((m) => {
            m.classList.remove('is-open');
            const btn = m.querySelector('.kb-avatar');
            if (btn) btn.setAttribute('aria-expanded', 'false');
        });
    });
}

function initDashTabs() {
    const tabBtns = document.querySelectorAll('.dash-tab-btn');
    if (tabBtns.length === 0) return;

    const activate = (btn) => {
        const target = btn.dataset.tab;
        document.querySelectorAll('.dash-tab-btn').forEach((b) => b.classList.remove('active'));
        document.querySelectorAll('.dash-tab-panel').forEach((p) => p.classList.remove('active'));
        btn.classList.add('active');
        const panel = document.getElementById(target);
        if (panel) panel.classList.add('active');
        try { sessionStorage.setItem('dash-tab', target); } catch (_) {}
    };

    tabBtns.forEach((btn) => {
        btn.addEventListener('click', () => activate(btn));
    });

    // Restore last-active tab
    let initial;
    try { initial = sessionStorage.getItem('dash-tab'); } catch (_) {}
    const firstTarget = initial && document.getElementById(initial)
        ? document.querySelector(`.dash-tab-btn[data-tab="${initial}"]`)
        : tabBtns[0];
    if (firstTarget) activate(firstTarget);
}

function initHowBidding() {
    const btn = document.querySelector('[data-how-toggle]');
    const panel = document.getElementById('lst-how');
    if (!btn || !panel) return;
    btn.addEventListener('click', () => {
        panel.hidden = !panel.hidden;
        btn.setAttribute('aria-expanded', panel.hidden ? 'false' : 'true');
    });
}

document.addEventListener('DOMContentLoaded', () => {
    fadeOutMessages();
    initNav();
    initDashTabs();
    initTabs();
    initQuickBids();
    initHowBidding();
    document.querySelectorAll('[data-auction-end]').forEach(startCountdown);
    initBidFormValidation();
    initGallery();

    initAuctionLive();
});

/* ── The header, made modern (implementation plan §2) ───────────────── */
(function () {
    'use strict';

    /* Sticky condensed masthead: past the nameplate the nav row and the
       stat line collapse; search, Mail/Alerts, the gold CTA and the
       avatar stay in reach. */
    const masthead = document.getElementById('kb-masthead');
    if (masthead) {
        const onScroll = () => {
            masthead.classList.toggle('is-condensed', window.scrollY > 96);
        };
        window.addEventListener('scroll', onScroll, { passive: true });
        onScroll();
    }

    /* "/" focuses search from anywhere; ctrl/cmd-K for those feeling
       modern. Never while already typing somewhere. */
    const searchInput = () =>
        document.getElementById('kb-q-home') || document.getElementById('kb-q');
    document.addEventListener('keydown', (event) => {
        const el = document.activeElement;
        const typing = el && (/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName) || el.isContentEditable);
        const cmdK = (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k';
        const slash = event.key === '/' && !typing && !event.ctrlKey && !event.metaKey && !event.altKey;
        if (slash || cmdK) {
            const input = searchInput();
            if (!input) return;
            event.preventDefault();
            input.focus();
            input.select();
        }
    });

    /* Typeahead: results grouped Listings / Collectors / Counties, each
       row a real link. Arrows walk it, Enter goes, Esc closes. */
    const esc = (s) => String(s).replace(/[&<>"]/g,
        (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

    document.querySelectorAll('#kb-q, #kb-q-home').forEach((input) => {
        const wrap = input.closest('form');
        if (!wrap) return;
        wrap.classList.add('kb-search-anchored');
        const box = document.createElement('div');
        box.className = 'kb-suggest';
        box.hidden = true;
        wrap.appendChild(box);
        let timer = null;
        let items = [];
        let active = -1;

        const close = () => { box.hidden = true; box.innerHTML = ''; items = []; active = -1; };
        const render = (data) => {
            const groups = [['Listings', data.listings],
                            ['Collectors', data.collectors],
                            ['Counties', data.counties]];
            let html = '';
            items = [];
            groups.forEach(([label, rows]) => {
                if (!rows || !rows.length) return;
                html += '<div class="kb-suggest-group">' + label + '</div>';
                rows.forEach((row) => {
                    items.push(row);
                    html += '<a class="kb-suggest-row" href="' + esc(row.url) + '">'
                        + '<span>' + esc(row.title) + '</span>'
                        + (row.meta ? '<small>' + esc(row.meta) + '</small>' : '')
                        + '</a>';
                });
            });
            if (!html) { close(); return; }
            box.innerHTML = html;
            box.hidden = false;
            active = -1;
        };

        input.addEventListener('input', () => {
            clearTimeout(timer);
            const q = input.value.trim();
            if (q.length < 2) { close(); return; }
            timer = setTimeout(async () => {
                try {
                    const resp = await fetch('/api/search/?q=' + encodeURIComponent(q));
                    if (resp.ok) render(await resp.json());
                } catch (err) { close(); }
            }, 180);
        });
        input.addEventListener('keydown', (event) => {
            const rows = box.querySelectorAll('.kb-suggest-row');
            if (box.hidden || !rows.length) return;
            if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
                event.preventDefault();
                active += event.key === 'ArrowDown' ? 1 : -1;
                active = (active + rows.length) % rows.length;
                rows.forEach((row, i) => row.classList.toggle('is-active', i === active));
            } else if (event.key === 'Enter' && active >= 0) {
                event.preventDefault();
                window.location.href = items[active].url;
            } else if (event.key === 'Escape') {
                close();
            }
        });
        document.addEventListener('click', (event) => {
            if (!wrap.contains(event.target)) close();
        });
    });
})();
