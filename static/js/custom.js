// Custom JavaScript for KeystoneBid

// Initialize tooltips, modals, or other interactive elements here

// Example: Auto-hide messages after 5 seconds
document.addEventListener('DOMContentLoaded', function() {
    const messages = document.querySelectorAll('[role="alert"]');
    messages.forEach(function(message) {
        setTimeout(function() {
            message.style.transition = 'opacity 0.5s';
            message.style.opacity = '0';
            setTimeout(function() {
                message.remove();
            }, 500);
        }, 5000);
    });
});

// Countdown timer for auctions (will be enhanced later)
function updateCountdown(endDate, elementId) {
    const now = new Date().getTime();
    const distance = new Date(endDate).getTime() - now;

    if (distance < 0) {
        document.getElementById(elementId).innerHTML = "EXPIRED";
        return;
    }

    const days = Math.floor(distance / (1000 * 60 * 60 * 24));
    const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
    const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
    const seconds = Math.floor((distance % (1000 * 60)) / 1000);

    document.getElementById(elementId).innerHTML = `${days}d ${hours}h ${minutes}m ${seconds}s`;
}
