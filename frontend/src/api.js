const KEY = "gw_token";
export function getToken() { return localStorage.getItem(KEY) || ""; }
export function setToken(t) { t ? localStorage.setItem(KEY, t) : localStorage.removeItem(KEY); }
export async function api(path, opts = {}) {
  const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
  const tok = getToken();
  if (tok) headers.Authorization = `Bearer ${tok}`;
  const res = await fetch(path, { ...opts, headers, body: opts.body && typeof opts.body !== "string" ? JSON.stringify(opts.body) : opts.body });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(data.detail || `HTTP ${res.status}`), { status: res.status, data });
  return data;
}
export const register = (handle, password, welcomeChoice = null, welcomeDisplayName = null) =>
  api("/api/auth/register", { method: "POST", body: { handle, password, welcome_choice: welcomeChoice, welcome_display_name: welcomeDisplayName } });
export const login = (handle, password) => api("/api/auth/login", { method: "POST", body: { handle, password } });
export const getAuthProviders = () => api("/api/auth/providers");
export const getWelcomeFeed = () => api("/api/welcome/feed");
export const getWelcomePreference = () => api("/api/welcome/me");
export const setWelcomePreference = (choice, displayName = null) =>
  api("/api/welcome/choice", { method: "PUT", body: { choice, display_name: displayName } });
export const getBillingStatus = () => api("/api/billing/status");
// The server builds the Stripe Checkout Session (plan, price and return URLs
// come from its own config); the page only follows the returned URL.
export const startCheckout = () => api("/api/billing/checkout", { method: "POST" });
