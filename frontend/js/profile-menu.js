// Fixed top-right profile icon shown on every page once a user is logged
// in (via login.html). Not shown for anonymous visitors/collaborators —
// those never touch Auth/JWT at all, so nothing here affects them.
(function () {
  if (typeof Auth === "undefined" || !Auth.isLoggedIn()) return;

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function buildWidget(email) {
    const initial = (email || "?").trim().charAt(0).toUpperCase() || "?";

    const wrap = document.createElement("div");
    wrap.className = "profile-widget";
    wrap.innerHTML = `
      <button type="button" class="profile-avatar-btn" id="profile-avatar-btn" aria-label="Account menu">${initial}</button>
      <div class="profile-dropdown" id="profile-dropdown">
        ${email ? `<div class="profile-dropdown-email">${escapeHtml(email)}</div>` : ""}
        <a class="profile-dropdown-item" href="my-trips.html">Trip history</a>
        <button type="button" class="profile-dropdown-item danger" id="profile-logout-btn">Log out</button>
      </div>
    `;
    document.body.appendChild(wrap);

    const avatarBtn = wrap.querySelector("#profile-avatar-btn");
    const dropdown = wrap.querySelector("#profile-dropdown");
    const logoutBtn = wrap.querySelector("#profile-logout-btn");

    avatarBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      dropdown.classList.toggle("open");
    });

    document.addEventListener("click", (e) => {
      if (!wrap.contains(e.target)) dropdown.classList.remove("open");
    });

    logoutBtn.addEventListener("click", () => {
      Auth.clearToken();
      window.location.href = "index.html";
    });
  }

  // Best-effort: show the user's email in the dropdown. If the token turns
  // out to be expired/invalid, quietly clear it and skip the widget rather
  // than showing a broken menu — the rest of the page still works exactly
  // as it would for an anonymous visitor.
  if (typeof Api !== "undefined" && Api.me) {
    Api.me()
      .then((user) => buildWidget(user.email))
      .catch(() => Auth.clearToken());
  } else {
    buildWidget(null);
  }
})();
