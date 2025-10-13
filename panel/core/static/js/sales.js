document.addEventListener('DOMContentLoaded', () => {

  const productSelect = document.getElementById('sale-product-select');
  const quantityInput = document.getElementById('sale-quantity-input');
  const submitButton  = document.getElementById('sale-submit-button');
  const errorMessage  = document.getElementById('stock-error-message');
  const stockHint     = document.getElementById('stock-available-hint');

  const unitPriceEl   = document.getElementById('sale-unit-price');
  const totalPriceEl  = document.getElementById('sale-total-price');

  const fmtCLP = new Intl.NumberFormat('es-CL', { style: 'currency', currency: 'CLP', maximumFractionDigits: 0 });

  function setSubmitEnabled(ok) {
    if (submitButton) submitButton.disabled = !ok;
  }
  function showError(text) {
    if (!errorMessage) return;
    errorMessage.textContent = text || '';
    errorMessage.style.display = text ? 'block' : 'none';
  }
  function setPrices(price, qty) {
    if (!unitPriceEl || !totalPriceEl) return;
    if (price == null || isNaN(price)) {
      unitPriceEl.textContent = '—';
      totalPriceEl.textContent = '—';
      return;
    }
    const total = price * qty;
    unitPriceEl.textContent  = fmtCLP.format(price);
    totalPriceEl.textContent = fmtCLP.format(total);
  }
  function updateTotals() {
    if (!productSelect) return;
    const opt = productSelect.options[productSelect.selectedIndex];
    if (!opt || !opt.value) {
      setPrices(null, 1);
      return;
    }
    const price = parseFloat(opt.dataset.price || '0');
    const qty   = Math.max(1, parseInt(quantityInput?.value || '1', 10));
    setPrices(price, qty);
  }
  function validateStockAndTotals() {
    if (!productSelect || !quantityInput) return;

    const opt = productSelect.options[productSelect.selectedIndex];
    if (!opt || !opt.value) {
      setSubmitEnabled(false);
      showError('');
      setPrices(null, 1);
      return;
    }

    const available = parseInt(opt.dataset.stock || '0', 10);
    let qty = parseInt(quantityInput.value || '1', 10);
    if (isNaN(qty) || qty < 1) qty = 1;

    if (stockHint) stockHint.textContent = `Disponible: ${isNaN(available) ? 0 : available}`;

    if (available <= 0) {
      showError('Producto sin stock.');
      quantityInput.classList.add('is-invalid');
      setSubmitEnabled(false);
    } else if (qty > available) {
      showError(`Stock insuficiente. Disponible: ${available}`);
      quantityInput.classList.add('is-invalid');
      setSubmitEnabled(false);
    } else {
      showError('');
      quantityInput.classList.remove('is-invalid');
      setSubmitEnabled(true);
    }

    updateTotals();
  }

  productSelect?.addEventListener('change', validateStockAndTotals);
  quantityInput?.addEventListener('input', validateStockAndTotals);
  validateStockAndTotals();

  const searchInput = document.getElementById('inventory-search');
  const table       = document.getElementById('inventory-table');
  if (searchInput && table) {
    const rows = Array.from(table.querySelectorAll('tbody tr'));
    searchInput.addEventListener('input', function () {
      const q = this.value.trim().toLowerCase();
      rows.forEach(tr => {
        const sku  = (tr.querySelector('[data-col="sku"]')?.innerText || '').toLowerCase();
        const name = (tr.querySelector('[data-col="name"]')?.innerText || '').toLowerCase();
        tr.style.display = (sku.includes(q) || name.includes(q)) ? '' : 'none';
      });
    });
  }


  const tickerWrap  = document.querySelector('.ticker-wrap');
  const tickerItems = tickerWrap ? Array.from(tickerWrap.querySelectorAll('.ticker-item')) : [];

  if (tickerWrap && tickerItems.length) {
    const TICKER_LIFETIME_MS = 20000;
    const STAGGER_MS         = 250;
    const FADE_MS            = 350;
    const WRAP_FADE_MS       = 600;

    setTimeout(() => {
      tickerItems.forEach((el, idx) => {
        setTimeout(() => {
          el.classList.add('fade-out');
          setTimeout(() => el.remove(), FADE_MS);
        }, idx * STAGGER_MS);
      });

      const totalFadeTime = (tickerItems.length - 1) * STAGGER_MS + FADE_MS + 50;
      setTimeout(() => {
        tickerWrap.offsetHeight;
        tickerWrap.classList.add('is-gone');
        setTimeout(() => tickerWrap.remove(), WRAP_FADE_MS);
      }, totalFadeTime);
    }, TICKER_LIFETIME_MS);
  }
});
