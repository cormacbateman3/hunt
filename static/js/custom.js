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

document.addEventListener('DOMContentLoaded', () => {
    fadeOutMessages();
    document.querySelectorAll('[data-auction-end]').forEach(startCountdown);

    document.querySelectorAll('[data-poll-url]').forEach((element) => {
        const endpoint = element.dataset.pollUrl;
        const bidTargetSelector = element.dataset.bidTarget;
        const countTargetSelector = element.dataset.bidCountTarget;
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
        });
    });
});
