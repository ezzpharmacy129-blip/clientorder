(function(){
  "use strict";

  let initialized = false;

  function escUser(value){
    return String(value ?? "")
      .replace(/&/g,"&amp;")
      .replace(/</g,"&lt;")
      .replace(/>/g,"&gt;")
      .replace(/"/g,"&quot;")
      .replace(/'/g,"&#39;");
  }

  async function loadUsers(){
    const root = document.getElementById("users-list");
    if(!root) return;

    root.innerHTML = '<div class="users-admin-empty">جارِ تحميل المستخدمين...</div>';

    try{
      const data = await apiFetch("/api/admin/users");
      const rows = Array.isArray(data?.users) ? data.users : [];
      const count = document.getElementById("users-count");
      if(count) count.textContent = rows.length + " مستخدم";

      if(!rows.length){
        root.innerHTML = '<div class="users-admin-empty">لا يوجد مستخدمون.</div>';
        return;
      }

      root.innerHTML =
        '<table class="users-admin-table"><thead><tr>' +
        '<th>الاسم</th><th>اسم المستخدم</th><th>الدور</th><th>الحالة</th><th>آخر دخول</th><th>الإجراءات</th>' +
        '</tr></thead><tbody>' +
        rows.map(user =>
          '<tr>' +
          '<td><strong>' + escUser(user.name) + '</strong></td>' +
          '<td>' + escUser(user.username) + '</td>' +
          '<td><span class="users-admin-badge ' + (user.role === "admin" ? "admin" : "employee") + '">' +
          (user.role === "admin" ? "مدير" : "موظف") +
          '</span></td>' +
          '<td><span class="users-admin-badge ' + (user.active ? "active" : "inactive") + '">' +
          (user.active ? "نشط" : "معطل") +
          '</span></td>' +
          '<td>' + escUser(user.last_login || "—") + '</td>' +
          '<td><div class="users-admin-actions">' +
          '<button type="button" class="btn btn-outline btn-sm user-toggle" data-id="' + escUser(user.user_id) + '">' +
          (user.active ? "تعطيل" : "تفعيل") +
          '</button>' +
          '<button type="button" class="btn btn-secondary btn-sm user-pass" data-id="' + escUser(user.user_id) + '">تغيير كلمة المرور</button>' +
          '</div></td>' +
          '</tr>'
        ).join("") +
        '</tbody></table>';

      root.querySelectorAll(".user-toggle").forEach(button => {
        button.addEventListener("click", async () => {
          try{
            await apiFetch("/api/admin/users/" + encodeURIComponent(button.dataset.id) + "/toggle", {
              method: "POST",
              body: JSON.stringify({})
            });
            await loadUsers();
            toast("تم تحديث حالة المستخدم");
          }catch(error){
            toast(error.message, "error");
          }
        });
      });

      root.querySelectorAll(".user-pass").forEach(button => {
        button.addEventListener("click", async () => {
          const password = prompt("أدخل كلمة المرور الجديدة (8 أحرف على الأقل):");
          if(password === null) return;
          if(password.length < 8){
            toast("كلمة المرور يجب ألا تقل عن 8 أحرف", "error");
            return;
          }

          try{
            await apiFetch("/api/admin/users/" + encodeURIComponent(button.dataset.id) + "/password", {
              method: "POST",
              body: JSON.stringify({password})
            });
            toast("تم تغيير كلمة المرور بنجاح");
          }catch(error){
            toast(error.message, "error");
          }
        });
      });
    }catch(error){
      root.innerHTML = '<div class="users-admin-empty">تعذر تحميل المستخدمين.</div>';
      toast(error.message, "error");
    }
  }

  async function initUsers(){
    if(initialized) return;
    initialized = true;

    const nav = document.getElementById("users-nav-btn");
    const view = document.getElementById("view-users");

    if(!nav || !view) return;

    try{
      const me = (await apiFetch("/api/auth/me")).user;
      if(!me || me.role !== "admin"){
        nav.remove();
        view.remove();
        return;
      }
    }catch(_error){
      nav.remove();
      view.remove();
      return;
    }

    document.getElementById("users-refresh")?.addEventListener("click", loadUsers);

    document.getElementById("users-add-form")?.addEventListener("submit", async event => {
      event.preventDefault();

      const form = event.currentTarget;
      const button = form.querySelector('button[type="submit"]');
      const data = Object.fromEntries(new FormData(form).entries());

      button.disabled = true;
      try{
        await apiFetch("/api/admin/users", {
          method: "POST",
          body: JSON.stringify(data)
        });
        form.reset();
        await loadUsers();
        toast("تم إضافة المستخدم بنجاح");
      }catch(error){
        toast(error.message, "error");
      }finally{
        button.disabled = false;
      }
    });

    nav.addEventListener("click", () => {
      if(typeof switchView === "function"){
        switchView("users");
      }
      loadUsers();
    });

    loadUsers();
  }

  document.addEventListener("DOMContentLoaded", initUsers);
})();
