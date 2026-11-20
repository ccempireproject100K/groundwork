// Visitor market face (owner ruling 2026-11-01). The precedence lives on the
// server (GET /api/market): the visitor's stored choice, sent as the `market`
// parameter, wins; else the edge's detected country when the deployment
// trusts it; else the US default. This module only persists the choice and
// asks the endpoint. It never invents a face and detection never locks: the
// switcher stays visible. Plan prices stay in US dollars under every face,
// and the crisis lines (988, 911) never change with the face.
import { api } from "../api";

export const MARKET_STORAGE_KEY = "gw_market";

export function readMarketChoice() {
  try {
    return window.localStorage.getItem(MARKET_STORAGE_KEY) || "";
  } catch {
    return "";
  }
}

export function writeMarketChoice(id) {
  try {
    if (id) window.localStorage.setItem(MARKET_STORAGE_KEY, id);
    else window.localStorage.removeItem(MARKET_STORAGE_KEY);
  } catch {
    /* storage unavailable: the choice just won't persist */
  }
}

/** Ask the server which face this visitor gets (sends the stored choice). */
export function resolveVisitorFace(request = api) {
  const choice = readMarketChoice();
  return request(`/api/market${choice ? `?market=${encodeURIComponent(choice)}` : ""}`);
}
