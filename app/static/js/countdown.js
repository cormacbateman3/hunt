(function () {
  const targets = document.querySelectorAll("[data-countdown]");

  if (targets.length === 0) {
    return;
  }

  const update = () => {
    const now = new Date();

    targets.forEach((node) => {
      const iso = node.getAttribute("data-countdown");
      const end = iso ? new Date(iso) : null;

      if (!end || Number.isNaN(end.getTime())) {
        return;
      }

      const remaining = end - now;
      if (remaining <= 0) {
        node.textContent = "Auction closed";
        return;
      }

      const totalMinutes = Math.floor(remaining / 60000);
      const days = Math.floor(totalMinutes / 1440);
      const hours = Math.floor((totalMinutes % 1440) / 60);
      const minutes = totalMinutes % 60;

      node.textContent = `Ends in ${days}d ${hours}h ${minutes}m`;
    });
  };

  update();
  window.setInterval(update, 60000);
})();
