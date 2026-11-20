import { describe, expect, it, vi, afterEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import MarketFaceSwitcher from "../components/MarketFaceSwitcher";
import { MARKET_STORAGE_KEY, readMarketChoice, resolveVisitorFace, writeMarketChoice } from "../lib/marketFace";

const MARKETS = [
  { id: "us", name: "United States", flag: "" },
  { id: "gb", name: "United Kingdom", flag: "" },
];
const face = (id, source) => ({
  market_id: id,
  market_source: source,
  market: { id, name: MARKETS.find((m) => m.id === id).name },
  markets: MARKETS,
});

function stubFetch(handler) {
  const calls = [];
  vi.spyOn(globalThis, "fetch").mockImplementation(async (url) => {
    calls.push(String(url));
    const body = handler(String(url));
    if (body === null) return new Response("{}", { status: 500 });
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  });
  return calls;
}

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe("market choice storage and resolution", () => {
  it("persists, reads back and clears the stored choice", () => {
    expect(readMarketChoice()).toBe("");
    writeMarketChoice("gb");
    expect(localStorage.getItem(MARKET_STORAGE_KEY)).toBe("gb");
    expect(readMarketChoice()).toBe("gb");
    writeMarketChoice("");
    expect(readMarketChoice()).toBe("");
  });

  it("sends the stored choice to the server and sends none otherwise", async () => {
    const calls = stubFetch(() => face("us", "default"));
    await resolveVisitorFace();
    writeMarketChoice("gb");
    await resolveVisitorFace();
    expect(calls[0]).toBe("/api/market");
    expect(calls[1]).toBe("/api/market?market=gb");
  });
});

describe("MarketFaceSwitcher", () => {
  it("shows the US default with a labelled switcher, then persists a pick", async () => {
    const calls = stubFetch((url) => (url.includes("market=gb") ? face("gb", "choice") : face("us", "default")));
    render(<MarketFaceSwitcher />);
    const select = screen.getByRole("combobox", { name: "Your market" });
    await waitFor(() => expect(screen.getByRole("option", { name: /United Kingdom/ })).toBeInTheDocument());
    expect(screen.getByTestId("market-note")).toHaveTextContent("United States edition, our default");
    expect(screen.getByTestId("market-note")).not.toHaveTextContent("US dollars");
    fireEvent.change(select, { target: { value: "gb" } });
    await waitFor(() => expect(screen.getByTestId("market-note")).toHaveTextContent("United Kingdom edition, your saved choice"));
    expect(screen.getByTestId("market-note")).toHaveTextContent("All prices are in US dollars (USD).");
    expect(readMarketChoice()).toBe("gb");
    expect(calls.at(-1)).toBe("/api/market?market=gb");
    fireEvent.change(select, { target: { value: "" } });
    await waitFor(() => expect(screen.getByTestId("market-note")).toHaveTextContent("our default"));
    expect(readMarketChoice()).toBe("");
  });

  it("explains a detected face", async () => {
    stubFetch(() => face("gb", "detected"));
    render(<MarketFaceSwitcher />);
    await waitFor(() => expect(screen.getByTestId("market-note")).toHaveTextContent("We detected United Kingdom"));
  });

  it("still renders when the server cannot be reached", async () => {
    stubFetch(() => null);
    render(<MarketFaceSwitcher />);
    expect(screen.getByRole("combobox", { name: "Your market" })).toBeInTheDocument();
    expect(screen.getByTestId("market-note")).toHaveTextContent("United States edition, our default");
  });
});
