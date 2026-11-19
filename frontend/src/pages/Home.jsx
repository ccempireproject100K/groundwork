import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { APP_NAME } from "../brand";
import { MILESTONE_DAYS } from "../lib/mood";

// "Start here" cards link only to routes that already exist (see App.jsx / areas.js).
const CARDS = [
  { to: "/feed", titleKey: "nav.community", descKey: "home.cardFeed" },
  { to: "/reentry", titleKey: "reentry.checklistTitle", descKey: "home.cardReentry", chipKey: "home.steps33" },
  { to: "/wellbeing", titleKey: "nav.wellbeing", descKey: "home.cardWellbeing" },
  { to: "/support", titleKey: "nav.support", descKey: "home.cardSupport" },
  { to: "/journey", titleKey: "nav.journey", descKey: "home.cardJourney", chipText: "30 · 60 · 90 · 180 · 365" },
  { to: "/safety", titleKey: "nav.safety", descKey: "home.cardSafety" },
];

export default function Home() {
  const { t } = useTranslation();
  return (
    <section className="page">
      <div className="hero">
        <p className="kicker">{t("home.kicker")}</p>
        <h1>{t("home.title", { app: APP_NAME })}</h1>
        <p className="lede">{t("home.tagline")}</p>
        <div className="hero-art" aria-hidden="true">
          <div className="glow-ring" />
        </div>
      </div>

      <div className="crisis-strip">
        <p>{t("home.crisisNote")}</p>
        <a href="tel:988">{t("crisis.call988")}</a>
        {" · "}
        <a href="sms:988">{t("crisis.text988")}</a>
        {" · "}
        <a href="tel:911">{t("crisis.call911")}</a>
      </div>

      <div className="section-block">
        <h2>{t("home.startHere")}</h2>
        <div className="card-grid">
          {CARDS.map((card) => (
            <Link key={card.to} to={card.to} className="card card-link">
              <h3>{t(card.titleKey)}</h3>
              <p>{t(card.descKey)}</p>
              {card.chipKey && <span className="chip">{t(card.chipKey)}</span>}
              {card.chipText && <span className="chip">{card.chipText}</span>}
            </Link>
          ))}
        </div>
      </div>

      <div className="section-block">
        <h2>{t("reentry.milestones")}</h2>
        <div className="stat-row">
          {MILESTONE_DAYS.map((day) => (
            <div key={day} className="stat">
              <span className="stat-num">{day}</span>
              <span className="stat-label">{t("home.milestoneDays")}</span>
            </div>
          ))}
        </div>
      </div>

      <p className="notice">
        {t("home.newHere")} <Link to="/settings">{t("nav.platform")}</Link>
      </p>
    </section>
  );
}
