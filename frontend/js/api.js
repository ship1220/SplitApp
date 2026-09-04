// Set window.SPLIT_API_BASE before loading this file when you want to point
// at a different backend. Local development falls back to the FastAPI server
// on port 8000, and deployed pages can override it explicitly.
function resolveApiBase(globalScope = typeof window !== "undefined" ? window : globalThis) {
  if (globalScope.SPLIT_API_BASE) {
    return globalScope.SPLIT_API_BASE;
  }

  const hostname = globalScope.location?.hostname || "";
  if (hostname === "localhost" || hostname === "127.0.0.1" || hostname === "0.0.0.0") {
    return "http://127.0.0.1:8000";
  }

  return "https://splitapp-api-fuku.onrender.com";
}

const API_BASE = resolveApiBase();

if (typeof module !== "undefined") {
  module.exports = { resolveApiBase };
}

async function apiRequest(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  let body = null;
  try {
    body = await res.json();
  } catch (e) {
    /* no body */
  }
  if (!res.ok) {
    const msg = (body && body.detail) || `Request failed (${res.status})`;
    throw new Error(msg);
  }
  return body;
}

const Api = {
  // Sends the JWT (if logged in via login.html/my-trips.html) so the trip
  // gets owner_id set; anonymous callers just don't have a token, so this
  // header is simply omitted and trip creation works exactly as before.
  createTrip: (name, memberNames) =>
    apiRequest("/api/trips", {
      method: "POST",
      headers: typeof Auth !== "undefined" ? Auth.authHeaders() : {},
      body: JSON.stringify({ name, member_names: memberNames }),
    }),

  getTrip: (token) => apiRequest(`/api/trips/${token}`),

  addMember: (token, name) =>
    apiRequest(`/api/trips/${token}/members`, {
      method: "POST",
      body: JSON.stringify({ name }),
    }),

  addExpense: (token, payload) =>
    apiRequest(`/api/trips/${token}/expenses`, {
      method: "POST",
      // A fresh UUID per submit lets the backend dedupe retried/double-clicked
      // saves without creating a second expense.
      headers: { "Idempotency-Key": crypto.randomUUID() },
      body: JSON.stringify(payload),
    }),

  deleteExpense: (token, expenseId) =>
    apiRequest(`/api/trips/${token}/expenses/${expenseId}`, {
      method: "DELETE",
    }),

  updateExpense: (token, expenseId, payload) =>
    apiRequest(`/api/trips/${token}/expenses/${expenseId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),

  // ---- auth (optional accounts; anonymous trip flow above is unaffected) ----

  signup: (email, password) =>
    apiRequest("/api/auth/signup", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  login: (email, password) =>
    apiRequest("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  myTrips: () =>
    apiRequest("/api/me/trips", {
      headers: Auth.authHeaders(),
    }),

  myStats: () =>
    apiRequest("/api/me/stats", {
      headers: Auth.authHeaders(),
    }),

  me: () =>
    apiRequest("/api/me", {
      headers: Auth.authHeaders(),
    }),

  deleteTrip: (token) =>
    apiRequest(`/api/trips/${token}`, {
      method: "DELETE",
    }),
};
