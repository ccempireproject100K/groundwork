import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import App from "../App";
import en from "../locales/en/common.json";

// Gap-sweep wiring (2026-11-01): features whose backends existed but had no
// reachable UI. These tests pin that each section now renders on its page
// (offline: API calls fail soft and the sections show their empty states).
const at = (p) => render(<MemoryRouter initialEntries={[p]}><App /></MemoryRouter>);

describe("gap-sweep wiring", () => {
  it("reentry page wires the court calendar", { timeout: 20000 }, () => {
    at("/reentry");
    expect(screen.getByTestId("court-section")).toHaveTextContent(/Court dates/);
    expect(screen.getByRole("button", { name: /Add court date/ })).toBeInTheDocument();
  });
  it("work page wires the application tracker and gig list", () => {
    at("/work");
    expect(screen.getByTestId("tracker-section")).toHaveTextContent(/Application tracker/);
    expect(screen.getByTestId("gigs-section")).toHaveTextContent(/No gigs posted yet/);
  });
  it("wellbeing page wires filters, lock management and mood history", () => {
    at("/wellbeing");
    expect(screen.getByTestId("filters-section")).toHaveTextContent(/Filters for today/);
    expect(screen.getByTestId("locks-section")).toHaveTextContent(/Your locks/);
    expect(screen.getByTestId("mood-history")).toHaveTextContent(/Recent check-ins/);
  });
  it("community page wires inbox, media list and Q&A answers", () => {
    at("/feed");
    expect(screen.getByTestId("inbox-section")).toHaveTextContent(/Your messages/);
    expect(screen.getByTestId("media-section")).toHaveTextContent(/Your uploads/);
    expect(screen.getByTestId("meetings-section")).toHaveTextContent(/No virtual meetings yet/);
    expect(screen.getByTestId("events-section")).toHaveTextContent(/No events yet/);
    expect(screen.getByTestId("groups-section")).toHaveTextContent(/No program groups yet/);
  });
  it("support page wires counseling, mentorship, geolocation and needs-a-ride", () => {
    at("/support");
    expect(screen.getByTestId("counseling-section")).toHaveTextContent(/Counseling referrals/);
    expect(screen.getByTestId("mentorship-section")).toHaveTextContent(/Save my mentorship profile/);
    expect(screen.getByTestId("geo-section")).toHaveTextContent(/Share my city only/);
    expect(screen.getByTestId("ride-section")).toHaveTextContent(/Ride requests/);
  });
  it("journey page wires share card creation, archive sealing and token redeem", () => {
    at("/journey");
    expect(screen.getByTestId("share-section")).toHaveTextContent(/Make my card/);
    expect(screen.getByTestId("archive-section")).toHaveTextContent(/Nothing sealed yet/);
    expect(screen.getByTestId("tokens-section")).toHaveTextContent(/Redeem tokens/);
  });
  it("family page wires the shared-portfolio view", () => {
    at("/family");
    expect(screen.getByRole("button", { name: /View shared portfolio/ })).toBeInTheDocument();
  });
  it("public share route renders its honest missing state offline", async () => {
    at("/p/sometoken");
    expect(await screen.findByText(/share link is not available/)).toBeInTheDocument();
  });
  it("match page wires the decisions history", () => {
    at("/match");
    expect(screen.getByTestId("match-decisions")).toHaveTextContent(/past match decisions/);
  });
  it("gap keys exist in English with real copy", () => {
    const need = ["courtTitle", "trackerTitle", "counselingTitle", "mentorSave", "filtersTitle", "familyViewBtn", "sharedTitle"];
    for (const k of need) expect(en.gap[k], `gap.${k}`).toBeTruthy();
  });
});
