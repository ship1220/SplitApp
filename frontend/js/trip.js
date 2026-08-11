const params = new URLSearchParams(window.location.search);
const TOKEN = params.get("t");

let trip = null;
let isEditor = false;
let activeSplitType = "equal";
let activeTab = "activity";

const AVATAR_PALETTE = ["1", "2", "3", "4", "5"];

function avatarClassFor(memberId) {
  let hash = 0;
  for (const ch of memberId) hash = (hash * 31 + ch.charCodeAt(0)) % 997;
  const idx = hash % AVATAR_PALETTE.length;
  return AVATAR_PALETTE[idx];
}

function initials(name) {
  return (name || "?").trim().charAt(0).toUpperCase();
}

function fmtMoney(n) {
  const rounded = Math.round(n * 100) / 100;
  const isWhole = Math.abs(rounded - Math.round(rounded)) < 0.001;
  return "₹" + (isWhole ? Math.round(rounded).toLocaleString("en-IN") : rounded.toFixed(2));
}

function showToast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 2200);
}

function avatarEl(memberId, name, extraStyle = "") {
  const cls = avatarClassFor(memberId);
  return `<div class="avatar" style="background:var(--avatar-${cls}-bg); color:var(--avatar-${cls}-fg); ${extraStyle}">${initials(name)}</div>`;
}

// ---------- Load & render ----------

async function loadTrip() {
  if (!TOKEN) {
    showFatalError("No trip link found. Check the URL you were given.");
    return;
  }
  try {
    trip = await Api.getTrip(TOKEN);
    isEditor = trip.edit_token === TOKEN;
    document.getElementById("loading").style.display = "none";
    document.getElementById("trip-root").style.display = "block";
    document.getElementById("add-expense-fab").style.display = isEditor ? "flex" : "none";
    document.getElementById("view-only-badge").style.display = isEditor ? "none" : "inline-flex";
    renderAll();
  } catch (err) {
    showFatalError(err.message || "Couldn't load this trip.");
  }
}

function showFatalError(msg) {
  document.getElementById("loading").style.display = "none";
  const box = document.getElementById("error-box");
  box.textContent = msg;
  box.style.display = "block";
}

function renderAll() {
  document.getElementById("trip-title").textContent = trip.name;
  document.getElementById("member-count-chip").textContent = `${trip.members.length} member${trip.members.length === 1 ? "" : "s"}`;
  renderActivity();
  renderPeople();
  renderSettle();
  if (calculationToggle?.getAttribute("aria-expanded") === "true") {
    renderCalculationWalkthrough();
  }
}

function renderActivity() {
  document.getElementById("total-spend").textContent = fmtMoney(trip.total_spend);
  const list = document.getElementById("expense-list");

  if (trip.expenses.length === 0) {
    list.innerHTML = `<div class="empty-state"><h3>No expenses yet</h3><p>Add your first expense to start tracking.</p></div>`;
    return;
  }

  list.innerHTML = trip.expenses
    .map(
      (e) => `
    <button class="row-card" data-expense-id="${e.id}">
      ${avatarEl(e.paid_by, e.paid_by_name)}
      <div class="row-main">
        <div class="row-title">${escapeHtml(e.description)}</div>
        <div class="row-sub">Paid by ${escapeHtml(e.paid_by_name)}</div>
      </div>
      <div class="row-amount">${fmtMoney(e.amount)}</div>
      <div class="row-chevron">›</div>
    </button>
  `
    )
    .join("");

  list.querySelectorAll(".row-card").forEach((btn) => {
    btn.addEventListener("click", () => openExpenseDetail(btn.dataset.expenseId));
  });
}

function renderPeople() {
  document.getElementById("member-total").textContent = String(trip.members.length).padStart(2, "0");
  const list = document.getElementById("people-list");

  list.innerHTML = trip.balances
    .map((b) => {
      const positive = b.net >= 0;
      return `
      <div class="row-card" style="cursor:default;">
        ${avatarEl(b.member_id, b.name)}
        <div class="row-main">
          <div class="row-title">${escapeHtml(b.name)}</div>
          <div class="row-sub">Paid ${fmtMoney(b.total_paid)}</div>
        </div>
        <div class="row-amount ${positive ? "positive" : "negative"}">${positive ? "+" : "-"}${fmtMoney(Math.abs(b.net))}</div>
      </div>
    `;
    })
    .join("");
}

function renderSettle() {
  document.getElementById("transfer-count").textContent = trip.transfers.length;
  const list = document.getElementById("settle-list");

  if (trip.transfers.length === 0) {
    list.innerHTML = `<div class="empty-state"><h3>All settled up 🎉</h3><p>Nobody owes anybody anything.</p></div>`;
    return;
  }

  list.innerHTML = trip.transfers
    .map(
      (t) => `
    <div class="row-card" style="cursor:default;">
      <div class="transfer-avatars">
        ${avatarEl(t.from_id, t.from_name)}
        ${avatarEl(t.to_id, t.to_name)}
      </div>
      <div class="row-main">
        <div class="transfer-people">${escapeHtml(t.from_name)} <span class="transfer-arrow">→</span> ${escapeHtml(t.to_name)}</div>
      </div>
      <div class="row-amount">${fmtMoney(t.amount)}</div>
    </div>
  `
    )
    .join("");
}

function calculationStep(number, title, body) {
  return `
    <section class="calculation-step">
      <div class="calculation-step-title"><span>${number}</span><h3>${title}</h3></div>
      ${body}
    </section>`;
}

function matrixMemberCell(member) {
  return `<div class="matrix-member">${avatarEl(member.id, member.name, "width:36px;height:36px;font-size:12px;")}<strong>${escapeHtml(member.name)}</strong></div>`;
}

function renderCalculationWalkthrough() {
  const content = document.getElementById("calculation-content");
  if (!trip) return;

  const members = trip.members;
  const fairShare = members.length ? trip.total_spend / members.length : 0;
  const balanceByMember = new Map(trip.balances.map((balance) => [balance.member_id, balance]));
  const paidFor = new Map(members.map((payer) => [payer.id, new Map(members.map((member) => [member.id, 0]))]));

  trip.expenses.forEach((expense) => {
    const payerRows = paidFor.get(expense.paid_by);
    if (!payerRows) return;
    expense.shares.forEach((share) => {
      payerRows.set(share.member_id, (payerRows.get(share.member_id) || 0) + share.amount);
    });
  });

  const rawMatrixRows = members.map((payer) => {
    const balance = balanceByMember.get(payer.id);
    return `<tr>
      <th scope="row">${matrixMemberCell(payer)}</th>
      ${members.map((member) => `<td class="${payer.id === member.id ? "matrix-muted" : "matrix-paid"}">${payer.id === member.id ? "—" : fmtMoney(paidFor.get(payer.id).get(member.id) || 0)}</td>`).join("")}
      <td class="matrix-total-paid">${fmtMoney(balance?.total_paid || 0)}</td>
    </tr>`;
  }).join("");

  const receivedRow = `<tr class="matrix-summary-row"><th scope="row">Total received</th>${members.map((member) => `<td>${fmtMoney(balanceByMember.get(member.id)?.total_share || 0)}</td>`).join("")}<td>${fmtMoney(trip.total_spend)}</td></tr>`;

  const netRows = trip.balances.map((balance) => {
    const net = Math.round(balance.net * 100) / 100;
    const netClass = net > 0.01 ? "net-positive" : net < -0.01 ? "net-negative" : "net-zero";
    const prefix = net > 0.01 ? "+" : net < -0.01 ? "−" : "";
    return `<tr>
      <th scope="row">${matrixMemberCell({ id: balance.member_id, name: balance.name })}</th>
      <td class="matrix-total-paid">${fmtMoney(balance.total_paid)}</td>
      <td class="matrix-total-received">${fmtMoney(balance.total_share)}</td>
      <td>${fmtMoney(fairShare)}</td>
      <td><span class="net-pill ${netClass}">${prefix}${fmtMoney(Math.abs(net))}</span></td>
    </tr>`;
  }).join("");

  const transferMatrix = new Map(members.map((from) => [from.id, new Map(members.map((to) => [to.id, 0]))]));
  trip.transfers.forEach((transfer) => transferMatrix.get(transfer.from_id)?.set(transfer.to_id, transfer.amount));
  const settlementRows = members.map((from) => `<tr>
    <th scope="row">${matrixMemberCell(from)}</th>
    ${members.map((to) => `<td class="${from.id === to.id ? "matrix-muted" : "matrix-owes"}">${from.id === to.id ? "—" : fmtMoney(transferMatrix.get(from.id).get(to.id) || 0)}</td>`).join("")}
  </tr>`).join("");

  const transferCards = trip.transfers.length
    ? trip.transfers.map((transfer, index) => `<div class="simplified-transfer">
        <span class="transfer-index">${index + 1}</span>
        ${avatarEl(transfer.from_id, transfer.from_name, "width:40px;height:40px;font-size:13px;")}
        <strong>${escapeHtml(transfer.from_name)}</strong>
        <span class="simplified-arrow">→</span>
        ${avatarEl(transfer.to_id, transfer.to_name, "width:40px;height:40px;font-size:13px;")}
        <strong>${escapeHtml(transfer.to_name)}</strong>
        <strong class="simplified-amount">${fmtMoney(transfer.amount)}</strong>
      </div>`).join("")
    : `<div class="walkthrough-empty">Everyone is already settled up.</div>`;

  content.innerHTML = [
    calculationStep(1, "Raw Expense Matrix — Who Paid for Whom", `
      <p class="calculation-description">Each cell <strong>[Row → Column]</strong> shows how much the <em>row person</em> paid on behalf of the <em>column person</em>.</p>
      <div class="matrix-scroll"><table class="calculation-matrix"><thead><tr><th>Payer ↓ &#92; For →</th>${members.map((member) => `<th>${escapeHtml(member.name)}</th>`).join("")}<th class="matrix-total-paid">Total paid</th></tr></thead><tbody>${rawMatrixRows}${receivedRow}</tbody></table></div>
      <p class="matrix-legend"><span class="legend-blue">Blue column</span> = total each person paid out <span class="legend-orange">Orange row</span> = total each person received</p>`),
    calculationStep(2, "Net Balance Per Person", `
      <p class="calculation-description">Grand total = <strong>${fmtMoney(trip.total_spend)}</strong> ÷ ${members.length} members = <strong>${fmtMoney(fairShare)} fair share each</strong>.</p>
      <div class="matrix-scroll"><table class="calculation-matrix net-matrix"><thead><tr><th>Member</th><th>Total paid</th><th>Total received</th><th>Fair share</th><th>Net (paid − share)</th></tr></thead><tbody>${netRows}</tbody></table></div>
      <p class="matrix-legend"><span class="legend-green">Green (+)</span> = owed money back <span class="legend-orange">Orange (−)</span> = owes money</p>`),
    calculationStep(3, "Settlement Matrix — Who Owes Whom", `
      <p class="calculation-description">Each cell shows the final payment from the <em>row person</em> to the <em>column person</em>, after all balances are netted.</p>
      <div class="matrix-scroll"><table class="calculation-matrix"><thead><tr><th>Owes ↓ &#92; To →</th>${members.map((member) => `<th>${escapeHtml(member.name)}</th>`).join("")}</tr></thead><tbody>${settlementRows}</tbody></table></div>`),
    calculationStep(4, "Simplified Transfers — Minimum Transactions", `
      <p class="calculation-description">The greedy two-pointer algorithm matches the biggest debtor with the biggest creditor each round, minimizing total payments.</p>
      <div class="simplified-transfer-list">${transferCards}</div>
      <p class="algorithm-note"><strong>Algorithm:</strong> Sort debtors (most negative first) and creditors (most positive first). Each iteration settles <code>min(|debtor.net|, creditor.net)</code>, then advances whichever pointer reaches zero.</p>`),
  ].join("");
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// ---------- Tabs ----------

document.querySelectorAll(".tab").forEach((tabBtn) => {
  tabBtn.addEventListener("click", () => {
    activeTab = tabBtn.dataset.tab;
    document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b === tabBtn));
    document.getElementById("tab-activity").style.display = activeTab === "activity" ? "block" : "none";
    document.getElementById("tab-people").style.display = activeTab === "people" ? "block" : "none";
    document.getElementById("tab-settle").style.display = activeTab === "settle" ? "block" : "none";
  });
});

// ---------- Calculation walkthrough ----------

const calculationToggle = document.getElementById("calculation-toggle");
const calculationContent = document.getElementById("calculation-content");

calculationToggle.addEventListener("click", () => {
  const isExpanded = calculationToggle.getAttribute("aria-expanded") === "true";
  calculationToggle.setAttribute("aria-expanded", String(!isExpanded));
  calculationContent.hidden = isExpanded;
  if (!isExpanded) renderCalculationWalkthrough();
});

// ---------- Add expense modal ----------

const expenseModal = document.getElementById("expense-modal");

function openExpenseModal() {
  document.getElementById("exp-desc").value = "";
  document.getElementById("exp-amount").value = "";
  const paidBySel = document.getElementById("exp-paidby");
  paidBySel.innerHTML = trip.members.map((m) => `<option value="${m.id}">${escapeHtml(m.name)}</option>`).join("");

  activeSplitType = "equal";
  document.querySelectorAll("#split-type-toggle button").forEach((b) => b.classList.toggle("active", b.dataset.split === "equal"));
  renderSplitRows();
  expenseModal.style.display = "flex";
}

document.getElementById("add-expense-fab").addEventListener("click", openExpenseModal);
document.getElementById("expense-cancel-btn").addEventListener("click", () => (expenseModal.style.display = "none"));

document.querySelectorAll("#split-type-toggle button").forEach((btn) => {
  btn.addEventListener("click", () => {
    activeSplitType = btn.dataset.split;
    document.querySelectorAll("#split-type-toggle button").forEach((b) => b.classList.toggle("active", b === btn));
    renderSplitRows();
  });
});

document.getElementById("exp-amount").addEventListener("input", updateSplitHint);

function renderSplitRows() {
  const container = document.getElementById("split-rows");
  container.innerHTML = trip.members
    .map((m) => {
      if (activeSplitType === "equal") {
        return `
        <div class="split-row" data-member="${m.id}">
          <span class="name">${avatarEl(m.id, m.name, "width:26px;height:26px;font-size:11px;")} ${escapeHtml(m.name)}</span>
          <input type="checkbox" class="split-include" checked />
        </div>`;
      }
      const placeholder = activeSplitType === "percentage" ? "%" : "₹";
      return `
      <div class="split-row" data-member="${m.id}">
        <span class="name">${avatarEl(m.id, m.name, "width:26px;height:26px;font-size:11px;")} ${escapeHtml(m.name)}</span>
        <input type="number" class="split-value" min="0" step="0.01" placeholder="0 ${placeholder}" />
      </div>`;
    })
    .join("");
  updateSplitHint();
}

function updateSplitHint() {
  const hint = document.getElementById("split-hint");
  const amount = parseFloat(document.getElementById("exp-amount").value) || 0;

  if (activeSplitType === "equal") {
    const included = document.querySelectorAll(".split-include:checked").length;
    hint.className = "split-hint";
    hint.textContent = included > 0 ? `Split equally between ${included} ${included === 1 ? "person" : "people"} — ${fmtMoney(amount / (included || 1))} each` : "Select at least one person";
    return;
  }

  const values = Array.from(document.querySelectorAll(".split-value")).map((i) => parseFloat(i.value) || 0);
  const total = values.reduce((a, b) => a + b, 0);

  if (activeSplitType === "percentage") {
    const ok = Math.abs(total - 100) < 0.01;
    hint.className = ok ? "split-hint" : "split-hint error";
    hint.textContent = `Total: ${total.toFixed(1)}% ${ok ? "✓" : "(must add up to 100%)"}`;
  } else {
    const ok = Math.abs(total - amount) < 0.01;
    hint.className = ok ? "split-hint" : "split-hint error";
    hint.textContent = `Total: ${fmtMoney(total)} of ${fmtMoney(amount)} ${ok ? "✓" : "(must match the amount)"}`;
  }
}

document.getElementById("split-rows").addEventListener("input", updateSplitHint);
document.getElementById("split-rows").addEventListener("change", updateSplitHint);

document.getElementById("expense-save-btn").addEventListener("click", async () => {
  const description = document.getElementById("exp-desc").value.trim();
  const amount = parseFloat(document.getElementById("exp-amount").value);
  const paidBy = document.getElementById("exp-paidby").value;

  if (!description) return showToast("Add a description");
  if (!amount || amount <= 0) return showToast("Enter a valid amount");

  let participants = [];
  if (activeSplitType === "equal") {
    const rows = document.querySelectorAll(".split-row");
    rows.forEach((row) => {
      const checked = row.querySelector(".split-include").checked;
      if (checked) participants.push({ member_id: row.dataset.member });
    });
    if (participants.length === 0) return showToast("Select at least one person to split with");
  } else {
    const rows = document.querySelectorAll(".split-row");
    rows.forEach((row) => {
      const val = parseFloat(row.querySelector(".split-value").value) || 0;
      if (val > 0) participants.push({ member_id: row.dataset.member, value: val });
    });
    if (participants.length === 0) return showToast("Enter at least one split value");
  }

  const btn = document.getElementById("expense-save-btn");
  btn.disabled = true;
  btn.textContent = "Saving…";

  try {
    await Api.addExpense(TOKEN, {
      description,
      amount,
      paid_by: paidBy,
      split_type: activeSplitType,
      participants,
    });
    expenseModal.style.display = "none";
    trip = await Api.getTrip(TOKEN);
    renderAll();
    showToast("Expense added");
  } catch (err) {
    showToast(err.message || "Couldn't save that expense");
  } finally {
    btn.disabled = false;
    btn.textContent = "Save expense";
  }
});

// ---------- Expense detail modal ----------

const detailModal = document.getElementById("detail-modal");
let currentDetailExpenseId = null;

function openExpenseDetail(expenseId) {
  const exp = trip.expenses.find((e) => e.id === expenseId);
  if (!exp) return;
  currentDetailExpenseId = expenseId;

  document.getElementById("detail-title").textContent = exp.description;
  document.getElementById("detail-sub").textContent = `${fmtMoney(exp.amount)} paid by ${exp.paid_by_name} · split ${exp.split_type}`;
  document.getElementById("detail-shares").innerHTML = exp.shares
    .map(
      (s) => `
    <div class="row-card" style="cursor:default;">
      ${avatarEl(s.member_id, s.member_name)}
      <div class="row-main"><div class="row-title">${escapeHtml(s.member_name)}</div></div>
      <div class="row-amount">${fmtMoney(s.amount)}</div>
    </div>`
    )
    .join("");

  document.getElementById("detail-delete-btn").style.display = isEditor ? "block" : "none";
  detailModal.style.display = "flex";
}

document.getElementById("detail-close-btn").addEventListener("click", () => (detailModal.style.display = "none"));

document.getElementById("detail-delete-btn").addEventListener("click", async () => {
  if (!currentDetailExpenseId) return;
  if (!confirm("Delete this expense? This can't be undone.")) return;
  try {
    await Api.deleteExpense(TOKEN, currentDetailExpenseId);
    detailModal.style.display = "none";
    trip = await Api.getTrip(TOKEN);
    renderAll();
    showToast("Expense deleted");
  } catch (err) {
    showToast(err.message || "Couldn't delete that expense");
  }
});

// ---------- Share modal ----------

const shareModal = document.getElementById("share-modal");
document.getElementById("share-btn").addEventListener("click", () => {
  const base = window.location.origin + window.location.pathname;
  document.getElementById("edit-link").value = `${base}?t=${trip.edit_token}`;
  document.getElementById("view-link").value = `${base}?t=${trip.view_token}`;
  shareModal.style.display = "flex";
});
document.getElementById("share-close-btn").addEventListener("click", () => (shareModal.style.display = "none"));
document.querySelectorAll("[data-copy]").forEach((btn) => {
  btn.addEventListener("click", () => {
    const input = document.getElementById(btn.dataset.copy);
    input.select();
    navigator.clipboard?.writeText(input.value);
    showToast("Link copied");
  });
});

// ---------- Info modal ----------

const infoModal = document.getElementById("info-modal");
document.getElementById("info-btn").addEventListener("click", () => (infoModal.style.display = "flex"));
document.getElementById("info-close-btn").addEventListener("click", () => (infoModal.style.display = "none"));

// close modals on backdrop click
[expenseModal, detailModal, shareModal, infoModal].forEach((modal) => {
  modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.style.display = "none";
  });
});

loadTrip();
