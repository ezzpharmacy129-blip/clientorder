/* EZZ UI ROUTING CONTRACT FIX v2
   Runs synchronously so app.js always finds the legacy modal DOM it expects.
*/
(function () {
  if (window.__EZZ_UI_CONTRACT_V2__) return;
  window.__EZZ_UI_CONTRACT_V2__ = true;

  function ensure(id, html, classes) {
    var node = document.getElementById(id);
    if (node) return node;
    node = document.createElement("div");
    node.id = id;
    node.className = classes || "modal-overlay hidden";
    node.setAttribute("aria-hidden", "true");
    node.innerHTML = html;
    document.body.appendChild(node);
    return node;
  }

  if (!document.getElementById("ezz-ui-contract-style")) {
    var css = document.createElement("style");
    css.id = "ezz-ui-contract-style";
    css.textContent =
      ".modal-overlay{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;padding:16px;background:rgba(8,25,40,.48);z-index:10000}" +
      ".modal-overlay.hidden{display:none!important}" +
      ".modal{width:min(960px,96vw);max-height:92vh;overflow:auto;background:#fff;border-radius:18px;box-shadow:0 20px 80px rgba(0,0,0,.22);padding:20px;direction:rtl;box-sizing:border-box}" +
      ".modal-header{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px}" +
      ".modal-title{font-size:20px;font-weight:800}" +
      ".modal-close{border:0;background:#eef3f6;border-radius:10px;padding:9px 14px;cursor:pointer}" +
      ".modal-body{min-height:40px}" +
      ".availability-items{display:grid;gap:10px}" +
      ".availability-row{border:1px solid #dfe7ec;border-radius:12px;padding:12px}" +
      ".availability-row label{display:block;margin:6px 0}" +
      ".modal-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}" +
      ".postpone-quick{margin-inline-end:6px}" +
      "@media(max-width:700px){.modal{width:96vw;padding:14px}}";
    document.head.appendChild(css);
  }

  ensure("order-modal",
    '<div class="modal">' +
      '<div class="modal-header">' +
        '<div id="modal-title" class="modal-title">تفاصيل الطلب</div>' +
        '<button id="modal-close-btn" type="button" class="modal-close">إغلاق ✕</button>' +
      '</div>' +
      '<div id="modal-body" class="modal-body"></div>' +
    '</div>'
  );

  ensure("availability-modal",
    '<div class="modal">' +
      '<div class="modal-header">' +
        '<div class="modal-title">تحديث توفر المنتجات</div>' +
        '<button id="availability-close-btn" type="button" class="modal-close">إغلاق ✕</button>' +
      '</div>' +
      '<div id="availability-items" class="availability-items"></div>' +
      '<div class="modal-actions">' +
        '<button id="availability-save-btn" type="button" class="btn btn-primary">حفظ</button>' +
        '<button id="availability-cancel-btn" type="button" class="btn btn-secondary">إلغاء</button>' +
      '</div>' +
    '</div>'
  );

  ensure("confirm-modal",
    '<div class="modal">' +
      '<div class="modal-header">' +
        '<div class="modal-title">تأكيد العملية</div>' +
        '<button id="confirm-no-btn" type="button" class="modal-close">إغلاق</button>' +
      '</div>' +
      '<div id="confirm-message" class="modal-body"></div>' +
      '<div class="modal-actions">' +
        '<button id="confirm-yes-btn" type="button" class="btn btn-primary">نعم</button>' +
        '<button id="confirm-no-btn-2" type="button" class="btn btn-secondary">لا</button>' +
      '</div>' +
    '</div>'
  );

  var confirmNo2 = document.getElementById("confirm-no-btn-2");
  if (confirmNo2 && !confirmNo2.__ezzBound) {
    confirmNo2.__ezzBound = true;
    confirmNo2.addEventListener("click", function () {
      var close = document.getElementById("confirm-no-btn");
      if (close) close.click();
    });
  }

  ensure("postpone-modal",
    '<div class="modal">' +
      '<div class="modal-header">' +
        '<div class="modal-title">تأجيل المتابعة</div>' +
        '<button id="postpone-close-btn" type="button" class="modal-close">إغلاق ✕</button>' +
      '</div>' +
      '<div class="modal-body">' +
        '<div style="margin-bottom:10px">اختر موعدًا سريعًا:</div>' +
        '<button type="button" class="postpone-quick btn btn-outline" data-days="1">غدًا</button>' +
        '<button type="button" class="postpone-quick btn btn-outline" data-days="3">بعد 3 أيام</button>' +
        '<button type="button" class="postpone-quick btn btn-outline" data-days="7">بعد أسبوع</button>' +
        '<div style="margin-top:14px">' +
          '<label>أو اختر تاريخًا</label>' +
          '<input id="postpone-custom-date" type="date" />' +
        '</div>' +
      '</div>' +
      '<div class="modal-actions">' +
        '<button id="postpone-custom-confirm" type="button" class="btn btn-primary">تأكيد التأجيل</button>' +
        '<button id="postpone-cancel-btn" type="button" class="btn btn-secondary">إلغاء</button>' +
      '</div>' +
    '</div>'
  );
})();
