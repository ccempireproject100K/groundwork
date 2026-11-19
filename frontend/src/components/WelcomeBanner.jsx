import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { getWelcomeFeed } from "../api";
import { APP_NAME, SIBLING_NAME } from "../brand";

// The family parade: name-in-badge marks for the two sites (this app and its
// sibling), drawn as simple inline SVG badges (no external logos, no image
// requests). Names come from brand.js, never hard-coded here. Each float bobs
// gently like a parade float; reduced motion stills them.
function initialsOf(name) {
  const words = name.trim().split(/\s+/);
  return (words.length > 1 ? words[0][0] + words[1][0] : name.slice(0, 2)).toUpperCase();
}
export const PARADE_SITES = [
  { key: "self", name: APP_NAME, initials: initialsOf(APP_NAME) },
  { key: "sibling", name: SIBLING_NAME, initials: initialsOf(SIBLING_NAME) },
];

function SiteBadge({ initials, name }) {
  return (
    <svg className="parade-badge" viewBox="0 0 48 48" role="img" aria-label={name} width="34" height="34">
      <circle cx="24" cy="24" r="21" fill="none" stroke="currentColor" strokeWidth="2.5" />
      <circle cx="24" cy="24" r="16.5" fill="currentColor" opacity="0.16" />
      <text x="24" y="29.5" textAnchor="middle" fontSize="12.5" fontWeight="700" fill="currentColor">{initials}</text>
    </svg>
  );
}

function prefersReducedMotion() {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

// Slim dark ticker with yellow lettering near the top of every page,
// celebrating new members. Feed entries are typed: a free entry carries
// `free: true` and renders a "Free member" tag next to the name; a paid
// entry carries `paid: true`, renders the paid-membership template, and
// never carries the free tag. Underneath, the family sites parade past
// as floats. An empty feed is honest: the parade plus a general "we're
// happy you're here" only — no member is ever fabricated.
export default function WelcomeBanner() {
  const { t } = useTranslation();
  const [announcements, setAnnouncements] = useState([]);
  const [paused, setPaused] = useState(false);
  const [reduced] = useState(prefersReducedMotion);

  useEffect(() => {
    let live = true;
    getWelcomeFeed()
      .then((data) => { if (live && Array.isArray(data.announcements)) setAnnouncements(data.announcements); })
      .catch(() => { /* banner degrades to the generic welcome */ });
    return () => { live = false; };
  }, []);

  const entries = announcements.map((a) => {
    if (a.paid) {
      // Paid conversion announcement: one template, name slotted — the
      // member's display name when they chose to be named, otherwise the
      // generic name ("a new customer").
      const name = a.kind === "named" && a.display_name ? a.display_name : t("welcome.aNewCustomer");
      return { text: t("welcome.paidStart", { name }), free: false };
    }
    let text;
    if (a.kind === "named" && a.display_name) text = t("welcome.named", { app: APP_NAME, name: a.display_name });
    else if (a.kind === "anonymous") text = t("welcome.anonymous");
    else text = t("welcome.generic");
    return { text, free: a.free === true };
  });
  if (entries.length > 0) {
    entries.push({ text: t("welcome.everyone"), free: false });
    entries.push({ text: t("welcome.glad"), free: false });
  } else {
    entries.push({ text: t("welcome.happyHere", { app: APP_NAME }), free: false });
  }

  const renderEntry = (e, i) => (
    <li key={i}>
      <span>{e.text}</span>
      {e.free && <span className="welcome-free-tag">{t("welcome.freeMember")}</span>}
    </li>
  );

  const scrolling = !reduced && !paused;
  const trackClass = `welcome-track${scrolling ? "" : " is-still"}`;

  return (
    <section className="welcome-banner" aria-label={t("welcome.tickerLabel")}>
      <div className="welcome-ticker-row">
        <div className="welcome-ticker">
          <div className={trackClass}>
            <ul className="welcome-messages">
              {entries.map(renderEntry)}
            </ul>
            {/* Duplicate pass for the seamless loop; hidden from AT. */}
            {!reduced && (
              <ul className="welcome-messages" aria-hidden="true">
                {entries.map(renderEntry)}
              </ul>
            )}
          </div>
        </div>
        <button
          type="button"
          className="welcome-pause"
          aria-pressed={paused}
          aria-label={paused ? t("welcome.resume") : t("welcome.pause")}
          onClick={() => setPaused((p) => !p)}
        >
          {paused ? "▶" : "❚❚"}
        </button>
      </div>
      <div className="welcome-parade" aria-label={t("welcome.paradeLabel")}>
        <ul className="parade-floats">
          {PARADE_SITES.map((site, i) => (
            <li key={site.key} className="parade-float" style={{ animationDelay: `${i * 0.45}s` }}>
              <SiteBadge initials={site.initials} name={site.name} />
              <span className="parade-name">{site.name}</span>
              <span className="parade-wheels" aria-hidden="true"><i /><i /></span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
