/* EZZ ORDER FORM / PHONE FIX
   Loaded after app.js. Keeps a product input visible even if another initializer fails.
*/
(function () {
  function normalizePhoneFixed(value) {
    let s = String(value || "")
      .replace(/[٠-٩]/g, d => String("٠١٢٣٤٥٦٧٨٩".indexOf(d)))
      .replace(/[۰-۹]/g, d => String("۰۱۲۳۴۵۶۷۸۹".indexOf(d)))
      .trim();

    // Preserve an explicitly supplied international prefix.
    // +966..., 00966..., +249..., 00249..., etc. must keep that country code.
    const explicitIntl = s.startsWith("+") || /^00\d+/.test(s);
    let digits = s.replace(/\D/g, "");
    if (digits.startsWith("00")) digits = digits.slice(2);
    if (explicitIntl) return digits;

    // No country code supplied: keep the existing Saudi-local default only
    // for the normal Saudi mobile forms 05xxxxxxxx / 5xxxxxxxx.
    if (digits.startsWith("0") && digits.length === 10 && digits[1] === "5") return "966" + digits.slice(1);
    if (digits.startsWith("5") && digits.length === 9) return "966" + digits;
    return digits;
  }

  window.normalizePhoneClient = normalizePhoneFixed;

  function ensureProductRow() {
    const wrap = document.getElementById("product-items");
    if (!wrap) return;
    if (wrap.querySelector(".product-row")) return;
    if (typeof window.addProductRow === "function") {
      window.addProductRow("", 1);
      return;
    }

    const row = document.createElement("div");
    row.className = "product-row";
    row.innerHTML = `
      <div class="product-number">1</div>
      <input class="product-name" type="text" placeholder="اسم المنتج" autocomplete="off">
      <input class="product-qty" type="number" min="1" value="1" inputmode="numeric">
      <div class="product-image-cell">
        <label class="image-upload-btn">📷 صورة المنتج
          <input class="product-image" type="file" accept="image/jpeg,image/png,image/webp" hidden>
        </label>
        <div class="image-preview"></div>
      </div>
      <button type="button" class="remove-product" title="حذف المنتج">✕</button>`;
    row.querySelectorAll("input").forEach(el => el.addEventListener("input", window.updateProductTotals || function () {}));
    row.querySelector(".remove-product").addEventListener("click", () => {
      row.remove();
      ensureProductRow();
      if (typeof window.updateProductTotals === "function") window.updateProductTotals();
    });
    wrap.appendChild(row);
    if (typeof window.updateProductTotals === "function") window.updateProductTotals();
  }

  window.initNewOrder = function () {
    const form = document.getElementById("new-order-form");
    if (!form) return;
    ensureProductRow();
    const addBtn = document.getElementById("add-product-btn");
    if (addBtn && !addBtn.dataset.orderFixBound) {
      addBtn.dataset.orderFixBound = "1";
      addBtn.addEventListener("click", () => {
        if (typeof window.addProductRow === "function") window.addProductRow("", 1);
        else ensureProductRow();
      });
    }

    if (!form.dataset.orderFixBound) {
      form.dataset.orderFixBound = "1";
      form.addEventListener("reset", () => {
        setTimeout(ensureProductRow, 0);
      });
    }
  };

  document.addEventListener("DOMContentLoaded", () => {
    ensureProductRow();
    window.initNewOrder();
  });
})();
