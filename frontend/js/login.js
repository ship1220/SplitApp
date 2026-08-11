function showToast(msg) {
  const el = document.getElementById("toast");
  el.textContent = msg;
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 2200);
}

function readCredentials() {
  return {
    email: document.getElementById("auth-email").value.trim(),
    password: document.getElementById("auth-password").value,
  };
}

function showAuthError(msg) {
  const errorEl = document.getElementById("auth-error");
  errorEl.textContent = msg;
  errorEl.style.display = "block";
}

async function handleAuth(action, btn, otherBtn) {
  const errorEl = document.getElementById("auth-error");
  errorEl.style.display = "none";

  const { email, password } = readCredentials();
  if (!email || !password) {
    showAuthError("Enter both an email and a password.");
    return;
  }

  btn.disabled = true;
  otherBtn.disabled = true;
  const originalText = btn.textContent;
  btn.textContent = "Please wait…";

  try {
    const { access_token } = await action(email, password);
    Auth.setToken(access_token);
    window.location.href = "my-trips.html";
  } catch (err) {
    showAuthError(err.message || "Something went wrong.");
    btn.disabled = false;
    otherBtn.disabled = false;
    btn.textContent = originalText;
  }
}

const loginBtn = document.getElementById("login-btn");
const signupBtn = document.getElementById("signup-btn");

loginBtn.addEventListener("click", () => handleAuth(Api.login, loginBtn, signupBtn));
signupBtn.addEventListener("click", () => handleAuth(Api.signup, signupBtn, loginBtn));

if (Auth.isLoggedIn()) {
  window.location.href = "my-trips.html";
}
