import { NavLink, Outlet } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { APP_NAME } from "../brand";
import { AREAS } from "../areas";
import CrisisButton from "./CrisisButton";
import LanguageSwitcher from "./LanguageSwitcher";
import MarketFaceSwitcher from "./MarketFaceSwitcher";
import WelcomeBanner from "./WelcomeBanner";

export default function Shell() {
  const { t } = useTranslation();
  return (
    <div className="shell">
      <header className="shell-header">
        <div className="brand">
          <img className="brand-mark" src="/favicon.svg" alt="" />
          {APP_NAME}
        </div>
        <CrisisButton />
      </header>
      <WelcomeBanner />
      <nav className="shell-nav" aria-label="main">
        <NavLink to="/">{t("nav.home")}</NavLink>
        {AREAS.map((a) => <NavLink key={a.path} to={`/${a.path}`}>{t(`nav.${a.key}`)}</NavLink>)}
      </nav>
      <main className="shell-main"><Outlet /></main>
      <footer className="shell-footer">
        <span className="footer-note">{APP_NAME}</span>
        <LanguageSwitcher />
        <MarketFaceSwitcher />
      </footer>
    </div>
  );
}
