function showToast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 2200);
}

function fmtMoney(n) {
  const rounded = Math.round(n * 100) / 100;
  const isWhole = Math.abs(rounded - Math.round(rounded)) < 0.001;
  return "₹" + (isWhole ? Math.round(rounded).toLocaleString("en-IN") : rounded.toFixed(2));
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function showFatalError(msg) {
  document.getElementById("loading").style.display = "none";
  const box = document.getElementById("error-box");
  box.textContent = msg;
  box.style.display = "block";
}

async function loadMyTrips() {
  if (!Auth.isLoggedIn()) {
    window.location.href = "login.html";
    return;
  }

  try {
    const [trips, stats] = await Promise.all([Api.myTrips(), Api.myStats()]);
    document.getElementById("loading").style.display = "none";
    document.getElementById("my-trips-root").style.display = "block";
    renderStats(stats);
    renderTrips(trips);
  } catch (err) {
    if (String(err.message || "").toLowerCase().includes("credentials")) {
      Auth.clearToken();
      window.location.href = "login.html";
      return;
    }
    showFatalError(err.message || "Couldn't load your trips.");
  }
}

function renderStats(stats) {
  document.getElementById("stats-total").textContent = fmtMoney(stats.total_spend);
  const body = document.getElementById("stats-table-body");

  if (stats.trips.length === 0) {
    body.innerHTML = `<tr><td colspan="2" style="padding:8px 4px; color:var(--ink-soft);">No trips yet.</td></tr>`;
    return;
  }

  body.innerHTML = stats.trips
    .map(
      (t) => `
    <tr style="border-top:1px solid rgba(20,23,31,0.08);">
      <td style="padding:10px 4px;">${escapeHtml(t.trip_name)}</td>
      <td style="padding:10px 4px;">${fmtMoney(t.total_spend)}</td>
    </tr>`
    )
    .join("");
}

function renderTrips(trips) {
  const list = document.getElementById("trips-list");

  if (trips.length === 0) {
    list.innerHTML = `<div class="empty-state"><h3>No trips yet</h3><p>Create a trip while logged in and it'll show up here.</p></div>`;
    return;
  }

  list.innerHTML = trips
    .map(
      (t) => `
    <div class="row-card" data-trip-id="${t.id}">
      <a class="row-main" href="trip.html?t=${t.edit_token}" style="text-decoration:none; color:inherit;">
        <div class="row-title">${escapeHtml(t.name)}</div>
        <div class="row-sub">${t.member_count} member${t.member_count === 1 ? "" : "s"} · ${fmtMoney(t.total_spend)} spent</div>
      </a>
      <button type="button" class="pill-btn danger delete-trip-btn" data-edit-token="${t.edit_token}" data-trip-name="${escapeHtml(t.name)}" title="Delete trip">Delete</button>
    </div>`
    )
    .join("");

  list.querySelectorAll(".delete-trip-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      handleDeleteTrip(btn.dataset.editToken, btn.dataset.tripName);
    });
  });
}

async function handleDeleteTrip(editToken, tripName) {
  const confirmed = window.confirm(`Delete "${tripName}"? This removes all its members and expenses and can't be undone.`);
  if (!confirmed) return;

  try {
    await Api.deleteTrip(editToken);
    showToast("Trip deleted");
    const [trips, stats] = await Promise.all([Api.myTrips(), Api.myStats()]);
    renderStats(stats);
    renderTrips(trips);
  } catch (err) {
    showToast(err.message || "Couldn't delete that trip.");
  }
}

document.getElementById("new-trip-btn").addEventListener("click", () => {
  window.location.href = "index.html";
});

loadMyTrips();
