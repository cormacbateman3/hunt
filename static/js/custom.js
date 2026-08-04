// Vanilla JavaScript utilities for KeystoneBid.

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
    if (ms <= 0) {
        return 'EXPIRED';
    }

    const totalSeconds = Math.floor(ms / 1000);
    const days = Math.floor(totalSeconds / 86400);
    const hours = Math.floor((totalSeconds % 86400) / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    return `${days}d ${hours}h ${minutes}m ${seconds}s`;
}

function startCountdown(element) {
    const endDate = element.dataset.auctionEnd;
    if (!endDate) {
        return;
    }

    const tick = () => {
        const distance = new Date(endDate).getTime() - Date.now();
        element.textContent = formatDuration(distance);
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

async function pollJson(endpoint, callback, intervalMs = 10000) {
    const run = async () => {
        try {
            const response = await fetch(endpoint, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            if (!response.ok) {
                return;
            }
            const payload = await response.json();
            callback(payload);
        } catch (error) {
            // Keep polling even when intermittent requests fail.
            console.error('Polling failed:', error);
        }
    };

    await run();
    return setInterval(run, intervalMs);
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

document.addEventListener('DOMContentLoaded', () => {
    fadeOutMessages();
    initNav();
    initDashTabs();
    document.querySelectorAll('[data-auction-end]').forEach(startCountdown);
    initBidFormValidation();
    initGallery();

    document.querySelectorAll('[data-poll-url]').forEach((element) => {
        const endpoint = element.dataset.pollUrl;
        const bidTargetSelector = element.dataset.bidTarget;
        const countTargetSelector = element.dataset.bidCountTarget;
        const minBidTargetSelector = element.dataset.minBidTarget;
        const auctionEndTargetSelector = element.dataset.auctionEndTarget;
        if (!endpoint) {
            return;
        }

        pollJson(endpoint, (payload) => {
            if (bidTargetSelector) {
                const bidTarget = document.querySelector(bidTargetSelector);
                if (bidTarget && payload.current_bid) {
                    bidTarget.textContent = payload.current_bid;
                }
            }

            if (countTargetSelector) {
                const countTarget = document.querySelector(countTargetSelector);
                if (countTarget && typeof payload.bid_count !== 'undefined') {
                    countTarget.textContent = payload.bid_count;
                }
            }

            if (minBidTargetSelector) {
                const minBidTarget = document.querySelector(minBidTargetSelector);
                if (minBidTarget && payload.minimum_bid) {
                    minBidTarget.textContent = payload.minimum_bid;
                }
            }

            if (auctionEndTargetSelector && payload.auction_end) {
                const countdownTarget = document.querySelector(auctionEndTargetSelector);
                if (countdownTarget) {
                    countdownTarget.dataset.auctionEnd = payload.auction_end;
                }
            }
        });
    });
});
