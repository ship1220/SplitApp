// Thin wrapper around sessionStorage for the JWT. sessionStorage (rather
// than localStorage) so the token clears when the tab closes — this is a
// prototype-grade "remember me for this session" convention, not meant to
// survive across browser restarts. Anonymous/token-based trip access
// (frontend/js/trip.js) never reads this and is completely unaffected.
const Auth = {
  TOKEN_KEY: "split_jwt",

  setToken(token) {
    sessionStorage.setItem(this.TOKEN_KEY, token);
  },

  getToken() {
    return sessionStorage.getItem(this.TOKEN_KEY);
  },

  clearToken() {
    sessionStorage.removeItem(this.TOKEN_KEY);
  },

  isLoggedIn() {
    return !!this.getToken();
  },

  authHeaders() {
    const token = this.getToken();
    return token ? { Authorization: `Bearer ${token}` } : {};
  },
};
