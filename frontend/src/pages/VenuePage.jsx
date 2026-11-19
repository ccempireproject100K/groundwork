import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api";

export const VENUE_STOPS = ["entrance", "zero-proof bar", "lounge", "stage", "dining"];

// Raw stop names (from the backend seed / API) -> i18n key suffixes.
const STOP_KEYS = {
  entrance: "entrance",
  "zero-proof bar": "bar",
  lounge: "lounge",
  stage: "stage",
  dining: "dining",
};

function stopKey(stop) {
  return STOP_KEYS[stop] || null;
}

export default function VenuePage() {
  const { t } = useTranslation();
  const [venue, setVenue] = useState(null);
  const [stops, setStops] = useState(VENUE_STOPS);
  const [selected, setSelected] = useState(0);

  // Public endpoint (no auth). Any error keeps the built-in stop list.
  useEffect(() => {
    api("/api/venue/virtual_venue")
      .then((d) => {
        const v = d?.venue;
        if (!v) return;
        setVenue(v);
        if (Array.isArray(v.stops) && v.stops.length > 0) setStops(v.stops);
      })
      .catch(() => {});
  }, []);

  const active = Math.min(selected, stops.length - 1);
  const current = stops[active];
  const titleFor = (stop) => {
    const k = stopKey(stop);
    return k ? t(`venue.stop.${k}`) : stop;
  };
  const descFor = (stop) => {
    const k = stopKey(stop);
    return k ? t(`venue.desc.${k}`) : "";
  };
  const go = (index) => setSelected(Math.max(0, Math.min(index, stops.length - 1)));

  return (
    <section className="page">
      <div className="page-head">
        <h1>{t("nav.venue")}</h1>
        <p className="lede">{t("venue.lede")}</p>
        {(venue?.zero_proof || venue?.alcohol_free) && (
          <div>
            {venue.zero_proof && <span className="chip">{t("venue.zeroProof")}</span>}
            {venue.alcohol_free && <span className="chip">{t("venue.alcoholFree")}</span>}
          </div>
        )}
      </div>

      <div className="venue-stage">
        <div className={`venue-frame venue-frame--${active}`} data-stop={current} aria-hidden="true" />
        <div className="venue-caption">
          <h2>{titleFor(current)}</h2>
          <p>{descFor(current)}</p>
        </div>
      </div>

      <nav className="venue-stops" aria-label={t("nav.venue")}>
        <button type="button" className="btn btn-ghost btn-small" onClick={() => go(active - 1)} disabled={active === 0}>
          {t("venue.prev")}
        </button>
        {stops.map((stop, i) => (
          <button
            key={stop}
            type="button"
            className="venue-dot"
            aria-current={i === active ? "true" : undefined}
            onClick={() => go(i)}
          >
            {titleFor(stop)}
          </button>
        ))}
        <button
          type="button"
          className="btn btn-ghost btn-small"
          onClick={() => go(active + 1)}
          disabled={active === stops.length - 1}
        >
          {t("venue.next")}
        </button>
      </nav>

      <div className="card-grid">
        {stops.map((stop, i) => (
          <button
            key={stop}
            type="button"
            className="card stop-card"
            aria-current={i === active ? "true" : undefined}
            onClick={() => go(i)}
          >
            <strong>{titleFor(stop)}</strong>
            <span>{descFor(stop)}</span>
          </button>
        ))}
      </div>

      <div className="section-block">
        <span className="badge badge-sample">{t("venue.conceptBadge")}</span>
        <p data-testid="venue-placeholder" className="notice">
          {t("venue.placeholder")}
        </p>
        <p className="muted">{t("venue.photosNote")}</p>
      </div>
    </section>
  );
}
