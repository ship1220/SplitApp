if (typeof Auth !== "undefined" && Auth.isLoggedIn()) {
  const accountLink = document.getElementById("account-link");
  accountLink.textContent = "My trips →";
  accountLink.href = "my-trips.html";
}

function showToast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 2200);
}

document.getElementById("add-member-btn").addEventListener("click", () => {
  const list = document.getElementById("member-list");
  const row = document.createElement("div");
  row.className = "member-input-row";
  row.innerHTML = `<input type="text" class="member-input" placeholder="Member name" maxlength="50" />`;
  list.appendChild(row);
  row.querySelector("input").focus();
});

document.getElementById("create-trip-btn").addEventListener("click", async () => {
  const errorEl = document.getElementById("create-error");
  errorEl.style.display = "none";

  const name = document.getElementById("trip-name").value.trim();
  const memberNames = Array.from(document.querySelectorAll(".member-input"))
    .map((i) => i.value.trim())
    .filter(Boolean);

  if (!name) {
    errorEl.textContent = "Give your trip a name.";
    errorEl.style.display = "block";
    return;
  }
  if (memberNames.length < 1) {
    errorEl.textContent = "Add at least one person.";
    errorEl.style.display = "block";
    return;
  }

  const btn = document.getElementById("create-trip-btn");
  btn.disabled = true;
  btn.textContent = "Creating…";

  try {
    const trip = await Api.createTrip(name, memberNames);
    window.location.href = `trip.html?t=${trip.edit_token}`;
  } catch (err) {
    errorEl.textContent = err.message || "Something went wrong.";
    errorEl.style.display = "block";
    btn.disabled = false;
    btn.textContent = "Create trip";
  }
});
