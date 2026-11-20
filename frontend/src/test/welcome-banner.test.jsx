import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import WelcomeBanner, { PARADE_SITES } from "../components/WelcomeBanner";
import { MemoryRouter } from "react-router-dom";
import SettingsPage from "../pages/SettingsPage";
import { APP_NAME, SIBLING_NAME } from "../brand";

// Test fixtures only — labeled as such; the live feed is never fabricated.
// Entries without a `paid` mark here are FREE announcements (`free: true`),
// exactly as the onboarding-complete trigger produces them.
const FIXTURE_FEED = {
  announcements: [
    { kind: "named", display_name: "Fixture Fern", free: true, created_at: "2026-11-02T00:00:00+00:00" },
    { kind: "anonymous", free: true, created_at: "2026-11-02T00:01:00+00:00" },
    { kind: "generic", free: true, created_at: "2026-11-02T00:02:00+00:00" },
  ],
};

// Paid announcements, exactly as note_payment_collected() produces them:
// marked `paid: true`, never carrying the free tag.
const PAID_FIXTURE_FEED = {
  announcements: [
    { kind: "named", display_name: "Fixture Payer", paid: true, created_at: "2026-11-03T00:00:00+00:00" },
    { kind: "anonymous", paid: true, created_at: "2026-11-03T00:01:00+00:00" },
  ],
};

function stubFeed(payload) {
  const fetchMock = vi.fn(async (url) => {
    if (String(url).includes("/api/welcome/feed")) {
      return { ok: true, status: 200, json: async () => payload };
    }
    return { ok: true, status: 200, json: async () => ({}) };
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe("welcome banner", () => {
  it("empty feed shows only the parade and the generic happy message — nobody fabricated", async () => {
    stubFeed({ announcements: [] });
    render(<WelcomeBanner />);
    expect((await screen.findAllByText(`We're happy you're here — welcome to ${APP_NAME}!`)).length).toBeGreaterThan(0);
    expect(screen.queryByText(/Fixture/)).toBeNull();
    expect(screen.queryByText(/Everyone welcome our newest/)).toBeNull();
  });

  it("celebrates named, anonymous, and opt-out free members with the same ticker", async () => {
    stubFeed(FIXTURE_FEED);
    render(<WelcomeBanner />);
    expect((await screen.findAllByText(`Welcome to ${APP_NAME}, Fixture Fern!`)).length).toBeGreaterThan(0);
    expect(screen.getAllByText("A new member joined — welcome!").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Welcome to a new customer — we're happy you're here!").length).toBeGreaterThan(0);
    const banner = screen.getByLabelText("Welcome banner");
    // No tier / price / paid language rides along on free entries — the
    // "Free member" tag is the only type label.
    expect(banner.textContent).not.toMatch(/paid|tier|\$/i);
  });

  it("renders the Free member tag next to a free member's display name, and only on free entries", async () => {
    stubFeed(FIXTURE_FEED);
    render(<WelcomeBanner />);
    await screen.findAllByText(`Welcome to ${APP_NAME}, Fixture Fern!`);
    const tag = document.querySelector(".welcome-messages li .welcome-free-tag");
    expect(tag).toBeTruthy();
    expect(tag.textContent).toBe("Free member");
    // The tag sits in the same ticker item as the named welcome message.
    expect(tag.closest("li").textContent).toContain("Fixture Fern");
  });

  it("renders paid announcements with the paid template and NO free tag", async () => {
    stubFeed(PAID_FIXTURE_FEED);
    render(<WelcomeBanner />);
    // Named payer: their display name is slotted into the template.
    expect((await screen.findAllByText("Fixture Payer just started their paid membership — welcome to the paid circle, referral ready now!")).length).toBeGreaterThan(0);
    // Anonymous payer: the generic name is slotted instead.
    expect(screen.getAllByText("a new customer just started their paid membership — welcome to the paid circle, referral ready now!").length).toBeGreaterThan(0);
    // Payer entries carry no free tag anywhere in the banner.
    expect(document.querySelector(".welcome-free-tag")).toBeNull();
    expect(screen.queryByText("Free member")).toBeNull();
  });

  it("parades both family sites (names from brand.js) as badge floats underneath the ticker", async () => {
    stubFeed({ announcements: [] });
    render(<WelcomeBanner />);
    await screen.findAllByText(`We're happy you're here — welcome to ${APP_NAME}!`);
    const parade = screen.getByLabelText("Our family of sites");
    const names = [...parade.querySelectorAll(".parade-name")].map((n) => n.textContent);
    expect(names).toEqual([APP_NAME, SIBLING_NAME]);
    expect(parade.querySelectorAll(".parade-float svg.parade-badge")).toHaveLength(PARADE_SITES.length);
    // Ticker sits above the parade in the document.
    const ticker = document.querySelector(".welcome-ticker");
    expect(ticker.compareDocumentPosition(parade) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("pause control is a real keyboard-focusable button that stills the track", async () => {
    stubFeed(FIXTURE_FEED);
    render(<WelcomeBanner />);
    const pause = await screen.findByRole("button", { name: "Pause welcome ticker" });
    pause.focus();
    expect(document.activeElement).toBe(pause);
    expect(pause.getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(pause);
    expect(pause.getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("button", { name: "Resume welcome ticker" })).toBe(pause);
    expect(document.querySelector(".welcome-track").classList.contains("is-still")).toBe(true);
  });

  it("reduced motion renders a static ticker with no looping duplicate", async () => {
    stubFeed(FIXTURE_FEED);
    vi.stubGlobal("matchMedia", (q) => ({ matches: q.includes("prefers-reduced-motion"), media: q, addEventListener() {}, removeEventListener() {} }));
    render(<WelcomeBanner />);
    await screen.findAllByText(`Welcome to ${APP_NAME}, Fixture Fern!`);
    expect(document.querySelectorAll(".welcome-messages")).toHaveLength(1);
    expect(document.querySelector(".welcome-track").classList.contains("is-still")).toBe(true);
    // The stylesheet's own reduced-motion block is verified by grep in the
    // build report; here we pin the component's static rendering.
  });

  it("a failed feed fetch still shows the generic welcome and parade", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new Error("offline"); }));
    render(<WelcomeBanner />);
    expect((await screen.findAllByText(`We're happy you're here — welcome to ${APP_NAME}!`)).length).toBeGreaterThan(0);
    expect(screen.getByLabelText("Our family of sites")).toBeTruthy();
  });
});

describe("onboarding welcome choice", () => {
  it("is the first fieldset of the account card, with no choice preselected", async () => {
    stubFeed({ announcements: [] });
    render(<MemoryRouter><SettingsPage /></MemoryRouter>);
    const legend = await screen.findByText("How should we welcome you?");
    const card = legend.closest(".card");
    const fieldset = card.querySelector("fieldset.welcome-choice");
    const handleInput = card.querySelector("#settings-handle");
    expect(fieldset.compareDocumentPosition(handleInput) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    for (const v of ["named", "anonymous", "optout"]) {
      const radio = card.querySelector(`input[type="radio"][value="${v}"]`);
      expect(radio, v).toBeTruthy();
      expect(radio.checked, v).toBe(false);
    }
  });

  it("registration sends the chosen banner option and display name", async () => {
    const calls = [];
    vi.stubGlobal("fetch", vi.fn(async (url, opts = {}) => {
      calls.push([String(url), opts]);
      if (String(url).includes("/api/auth/register")) return { ok: true, status: 201, json: async () => ({ token: "tok", user: {} }) };
      if (String(url).includes("/api/auth/me")) return { ok: true, status: 200, json: async () => ({ handle: "newbie", role: "member", tier: "free" }) };
      if (String(url).includes("/api/welcome/me")) return { ok: true, status: 200, json: async () => ({ welcome_choice: "named", welcome_display_name: "Fixture Fern" }) };
      return { ok: true, status: 200, json: async () => ({ announcements: [] }) };
    }));
    render(<MemoryRouter><SettingsPage /></MemoryRouter>);
    const card = (await screen.findByText("How should we welcome you?")).closest(".card");
    fireEvent.click(card.querySelector('input[type="radio"][value="named"]'));
    const nameInput = await waitFor(() => card.querySelector('fieldset.welcome-choice label input:not([type="radio"])'));
    fireEvent.change(nameInput, { target: { value: "Fixture Fern" } });
    fireEvent.change(card.querySelector("#settings-handle"), { target: { value: "newbie" } });
    fireEvent.change(card.querySelector('input[type="password"]'), { target: { value: "long-enough-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Create account" }));
    await waitFor(() => expect(calls.some(([u]) => u.includes("/api/auth/register"))).toBe(true));
    const [, opts] = calls.find(([u]) => u.includes("/api/auth/register"));
    const body = JSON.parse(opts.body);
    expect(body.welcome_choice).toBe("named");
    expect(body.welcome_display_name).toBe("Fixture Fern");
  });

  it("opt-out value matches the backend vocabulary (optout)", async () => {
    stubFeed({ announcements: [] });
    render(<MemoryRouter><SettingsPage /></MemoryRouter>);
    const card = (await screen.findByText("How should we welcome you?")).closest(".card");
    expect(card.querySelector('input[type="radio"][value="opt_out"]')).toBeNull();
  });
});
