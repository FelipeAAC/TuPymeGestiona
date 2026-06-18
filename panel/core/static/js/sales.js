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

  // Cart support
  const addToCartButton = document.getElementById('add-to-cart-button');
  const cartListEl = document.getElementById('cart-list');
  const cartInput = document.getElementById('cart-items-input');
  let cart = [];

  function renderCart() {
    if (!cartListEl) return;
    cartListEl.innerHTML = '';
    cart.forEach((it, idx) => {
      const li = document.createElement('li');
      li.className = 'list-group-item d-flex justify-content-between align-items-center';
      li.innerHTML = `
        <div class="d-flex align-items-center gap-2">
          <div><button class="btn btn-sm btn-outline-secondary cart-decr" data-idx="${idx}">-</button></div>
          <div><input class="form-control form-control-sm cart-qty" data-idx="${idx}" style="width:64px;" value="${it.qty}" /></div>
          <div class="flex-grow-1">${it.name}</div>
        </div>
        <div>
          <button class="btn btn-sm btn-link text-danger remove-cart" data-idx="${idx}">Eliminar</button>
        </div>
      `;
      cartListEl.appendChild(li);
    });
    if (cart.length === 0) {
      const li = document.createElement('li');
      li.className = 'list-group-item text-muted';
      li.textContent = 'Carrito vacío';
      cartListEl.appendChild(li);
    }
    if (cartInput) cartInput.value = JSON.stringify(cart.map(i => ({product_id: i.id, qty: i.qty})));
  }

  function addCurrentToCart() {
    const opt = productSelect.options[productSelect.selectedIndex];
    if (!opt || !opt.value) return;
    const id = opt.value;
    const name = opt.textContent.trim();
    let qty = Math.max(1, parseInt(quantityInput?.value || '1', 10));
    const available = parseInt(opt.dataset.stock || '0', 10);
    if (qty > available) {
      showError(`Stock insuficiente. Disponible: ${available}`);
      return;
    }
    cart.push({id, name, qty});
    renderCart();
    // clear selection
    productSelect.selectedIndex = 0;
    quantityInput.value = '1';
    validateStockAndTotals();
  }

  addToCartButton?.addEventListener('click', addCurrentToCart);

  cartListEl?.addEventListener('click', (e) => {
    const btn = e.target.closest('.remove-cart');
    if (!btn) return;
    const idx = parseInt(btn.dataset.idx, 10);
    if (!isNaN(idx)) {
      cart.splice(idx, 1);
      renderCart();
    }
  });

  // decrement quantity
  cartListEl?.addEventListener('click', (e) => {
    const btn = e.target.closest('.cart-decr');
    if (!btn) return;
    const idx = parseInt(btn.dataset.idx, 10);
    if (!isNaN(idx) && cart[idx]) {
      cart[idx].qty = Math.max(1, parseInt(cart[idx].qty, 10) - 1);
      renderCart();
    }
  });

  // qty input change
  cartListEl?.addEventListener('input', (e) => {
    const inp = e.target.closest('.cart-qty');
    if (!inp) return;
    const idx = parseInt(inp.dataset.idx, 10);
    const v = parseInt(inp.value || '1', 10);
    if (!isNaN(idx) && cart[idx]) {
      cart[idx].qty = Math.max(1, isNaN(v) ? 1 : v);
      renderCart();
    }
  });

  // ensure hidden input is set on submit
  const saleForm = document.getElementById('sale-form');
  saleForm?.addEventListener('submit', (e) => {
    if (cart.length > 0) {
      if (cartInput) cartInput.value = JSON.stringify(cart.map(i => ({product_id: i.id, qty: i.qty})));
    }
  });

  const searchInput = document.getElementById('inventory-search');
  const categoryFilter = document.getElementById('inventory-filter-category');
  const table       = document.getElementById('inventory-table');
  if ((searchInput || categoryFilter) && table) {
    const rows = Array.from(table.querySelectorAll('tbody tr'));
    function applyFilters() {
      const q = (searchInput?.value || '').trim().toLowerCase();
      const selectedCat = (categoryFilter?.value || '').trim();
      rows.forEach(tr => {
        const sku  = (tr.querySelector('[data-col="sku"]')?.innerText || '').toLowerCase();
        const name = (tr.querySelector('[data-col="name"]')?.innerText || '').toLowerCase();
        const cat = tr.dataset.category || '';
        const matchSearch = !q || sku.includes(q) || name.includes(q);
        const matchCategory = !selectedCat || cat === selectedCat;
        tr.style.display = (matchSearch && matchCategory) ? '' : 'none';
      });
    }
    searchInput?.addEventListener('input', applyFilters);
    categoryFilter?.addEventListener('change', applyFilters);
  }


  const tickerWrap  = document.querySelector('.ticker-wrap');
  const tickerItems = tickerWrap ? Array.from(tickerWrap.querySelectorAll('.ticker-item')) : [];

  if (tickerWrap && tickerItems.length) {
    const TICKER_LIFETIME_MS = 50000; // mostrar 50s por defecto
    const STAGGER_MS         = 250;
    const FADE_MS            = 350;
    const WRAP_FADE_MS       = 600;
    const LAST_SHOWN_KEY = 'tu_pyme_ticker_last_shown';
    const REAPPEAR_MS = 10 * 60 * 1000; // 10 minutos

    const shouldShow = () => {
      try {
        const last = sessionStorage.getItem(LAST_SHOWN_KEY);
        if (!last) return true;
        const elapsed = Date.now() - parseInt(last, 10);
        return elapsed >= REAPPEAR_MS;
      } catch (e) { return true; }
    }

    if (shouldShow()) {
      sessionStorage.setItem(LAST_SHOWN_KEY, String(Date.now()));
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
    } else {
      // hide immediately if recently shown
      tickerWrap.classList.add('is-gone');
      setTimeout(() => tickerWrap.remove(), WRAP_FADE_MS);
    }
  }

  // Auto-hide Django flash messages and info tips after 50s
  setTimeout(() => {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(a => {
      try { a.classList.add('fade'); a.classList.remove('show'); a.remove(); } catch(e){}
    });
    // also clear notifications list periodically
    const notCount = document.getElementById('notificationsCount');
    if (notCount) { notCount.style.display = 'none'; }
  }, 50000);

  // Order detail modal: read row content and show modal
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.open-order-detail');
    if (!btn) return;
    
    // Get data from button attributes (from orders table)
    const orderNum = btn.dataset.orderNumber || '';
    const customer = btn.dataset.customer || '';
    const createdAt = btn.dataset.createdAt || '';
    
    // Get items from the table row
    const tr = btn.closest('tr');
    let itemsHtml = '';
    if (tr) {
      const itemsCell = tr.querySelector('td:nth-child(4)');
      if (itemsCell) {
        itemsHtml = itemsCell.innerHTML;
      }
    }
    
    const total = tr?.querySelectorAll('td')[4]?.innerText || '';

    const body = document.getElementById('order-detail-body');
    if (!body) return;
    body.innerHTML = `
      <p><strong>Pedido:</strong> ${orderNum}</p>
      <p><strong>Cliente:</strong> ${customer}</p>
      <p><strong>Fecha:</strong> ${createdAt}</p>
      <h6>Items</h6>
      <div>${itemsHtml}</div>
      <hr>
      <p class="text-end"><strong>Total:</strong> ${total}</p>
    `;

    try {
      const modalEl = document.getElementById('orderDetailModal');
      const modal = new bootstrap.Modal(modalEl);
      modal.show();
    } catch (err) {
      console.warn('Bootstrap modal not available', err);
    }
  });
});
