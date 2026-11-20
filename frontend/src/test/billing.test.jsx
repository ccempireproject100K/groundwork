import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import SettingsPage from "../pages/SettingsPage";

const STATUS = { configured: true, tier: "free", plan: { tier: "paid", name: "Paid", price_cents: 399, currency: "usd", interval: "month" } };

function stubApi({ me = { handle: "m1", role: "member", tier: "free" }, status = STATUS, checkout = { ok: true, status: 200, json: async () => ({ url: "https://checkout.stripe.com/c/pay/x" }) } } = {}) {
  const calls = [];
  vi.stubGlobal("fetch", vi.fn(async (url, opts = {}) => {
    calls.push([String(url), opts]);
    const u = String(url);
    if (u.includes("/api/auth/me")) return { ok: true, status: 200, json: async () => me };
    if (u.includes("/api/billing/status")) return { ok: true, status: 200, json: async () => status };
    if (u.includes("/api/billing/checkout")) return checkout;
    if (u.includes("/api/welcome/me")) return { ok: true, status: 200, json: async () => ({}) };
    return { ok: true, status: 200, json: async () => ({ providers: [], announcements: [] }) };
  }));
  return calls;
}

describe("upgrade button", () => {
  let assign;
  beforeEach(() => {
    localStorage.setItem("gw_token", "tok");
    assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign, search: "", hash: "", pathname: "/settings" });
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it("shows the plan price from the server and redirects to the returned checkout URL", async () => {
    const calls = stubApi();
    render(<MemoryRouter><SettingsPage /></MemoryRouter>);
    const btn = await screen.findByRole("button", { name: /Upgrade to the paid plan/ });
    expect(btn).toHaveTextContent("$3.99 per month");
    fireEvent.click(btn);
    await waitFor(() => expect(assign).toHaveBeenCalledWith("https://checkout.stripe.com/c/pay/x"));
    const [, opts] = calls.find(([u]) => u.includes("/api/billing/checkout"));
    expect(opts.method).toBe("POST");
    expect(opts.body).toBeUndefined();
  });

  it("is hidden when billing is not configured", async () => {
    stubApi({ status: { ...STATUS, configured: false } });
    render(<MemoryRouter><SettingsPage /></MemoryRouter>);
    await screen.findByText(/Signed in as/);
    await waitFor(() => expect(screen.queryByRole("button", { name: /Upgrade/ })).toBeNull());
  });

  it("is hidden for a member who is already on the paid plan", async () => {
    stubApi({ me: { handle: "m1", role: "member", tier: "paid" }, status: { ...STATUS, tier: "paid" } });
    render(<MemoryRouter><SettingsPage /></MemoryRouter>);
    await screen.findByText(/Signed in as/);
    expect(screen.queryByRole("button", { name: /Upgrade/ })).toBeNull();
  });

  it("shows a plain message when checkout is unavailable and does not redirect", async () => {
    stubApi({ checkout: { ok: false, status: 503, json: async () => ({ detail: "billing is not configured" }) } });
    render(<MemoryRouter><SettingsPage /></MemoryRouter>);
    fireEvent.click(await screen.findByRole("button", { name: /Upgrade to the paid plan/ }));
    expect(await screen.findByText("Upgrading is not available right now.")).toBeInTheDocument();
    expect(assign).not.toHaveBeenCalled();
  });
});
