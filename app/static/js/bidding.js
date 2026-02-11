(function () {
  const amountNode = document.getElementById("bid-amount");
  const controls = document.querySelectorAll("[data-bid-adjust]");

  if (!amountNode || controls.length === 0) {
    return;
  }

  const parseAmount = () => Number(amountNode.textContent.replace(/[^0-9.]/g, "")) || 0;
  const renderAmount = (value) => {
    amountNode.textContent = "$" + Math.max(0, value).toFixed(0);
  };

  controls.forEach((button) => {
    button.addEventListener("click", () => {
      const delta = Number(button.getAttribute("data-bid-adjust")) || 0;
      const next = parseAmount() + delta;
      renderAmount(next);
    });
  });
})();
