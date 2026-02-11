(function () {
  const eraFilter = document.getElementById("era-filter");
  const cards = document.querySelectorAll("[data-collector-grid] [data-era]");

  if (!eraFilter || cards.length === 0) {
    return;
  }

  eraFilter.addEventListener("change", () => {
    const selectedEra = eraFilter.value;

    cards.forEach((card) => {
      const match = selectedEra === "all" || card.getAttribute("data-era") === selectedEra;
      card.hidden = !match;
    });
  });
})();
