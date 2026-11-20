import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { readMarketChoice, resolveVisitorFace, writeMarketChoice } from "../lib/marketFace";

// Visible market switcher, in the footer of every page (owner ruling
// 2026-11-01). Shows the edition in use and why, and lets the visitor pick
// another or go back to Automatic. If the server cannot be reached the control
// still renders and the note says the US default is showing. It never touches
// the crisis surfaces.
export default function MarketFaceSwitcher() {
  const { t } = useTranslation();
  const [face, setFace] = useState(null);
  const [choice, setChoice] = useState(() => readMarketChoice());

  const load = () => resolveVisitorFace().then(setFace).catch(() => setFace(null));
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const pick = (id) => {
    writeMarketChoice(id);
    setChoice(id);
    load();
  };

  const name = face?.market?.name || "";
  const source = face?.market_source || "default";
  const note = source === "choice" ? t("marketFace.choice", { name })
    : source === "detected" ? t("marketFace.detected", { name })
    : t("marketFace.defaultNote");
  const usd = face && face.market_id && face.market_id !== "us" ? ` ${t("marketFace.usd")}` : "";

  return (
    <div className="market-switch" data-testid="market-switch">
      <label>
        {t("marketFace.label")}{" "}
        <select value={choice} onChange={(e) => pick(e.target.value)} aria-label={t("marketFace.label")}>
          <option value="">{t("marketFace.automatic")}</option>
          {(face?.markets || []).map((m) => <option key={m.id} value={m.id}>{m.flag} {m.name}</option>)}
        </select>
      </label>
      <p className="muted" role="status" data-testid="market-note">{note}{usd}</p>
    </div>
  );
}
