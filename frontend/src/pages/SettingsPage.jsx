import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, getAuthProviders, getToken, getWelcomePreference, login, register, setToken, setWelcomePreference } from "../api";
import ReadAloud from "../components/ReadAloud";
import MusicPlayer from "../components/MusicPlayer";
import { DictateButton, GuidedFill } from "../components/Dictation";

// The welcome-banner choice: display a chosen name, join anonymously, or
// opt out (shown only as a generic "a new customer"). Nothing is announced
// until the member chooses — the default is no announcement.
export function WelcomeChoiceFields({ choice, setChoice, name, setName }) {
  const { t } = useTranslation();
  return (
    <fieldset className="welcome-choice">
      <legend>{t("welcome.choiceTitle")}</legend>
      <p className="muted">{t("welcome.choiceHelp")}</p>
      <label>
        <input type="radio" name="welcome-choice" value="named" checked={choice === "named"} onChange={() => setChoice("named")} />{" "}
        {t("welcome.choiceNamed")}
      </label>
      {choice === "named" && (
        <div className="field-row">
          <label>
            {t("welcome.displayName")}{" "}
            <input aria-label={t("welcome.displayName")} value={name} onChange={(e) => setName(e.target.value)} maxLength={30} />
          </label>
          <p className="muted">{t("welcome.displayNameHelp")}</p>
        </div>
      )}
      <label>
        <input type="radio" name="welcome-choice" value="anonymous" checked={choice === "anonymous"} onChange={() => setChoice("anonymous")} />{" "}
        {t("welcome.choiceAnonymous")}
      </label>
      <label>
        <input type="radio" name="welcome-choice" value="optout" checked={choice === "optout"} onChange={() => setChoice("optout")} />{" "}
        {t("welcome.choiceOptOut")}
      </label>
    </fieldset>
  );
}


export default function SettingsPage() {
  const { t } = useTranslation();
  const [handle, setHandle] = useState("");
  const [pw, setPw] = useState("");
  const [msg, setMsg] = useState("");
  const [me, setMe] = useState(null);
  const [welcomeChoice, setWelcomeChoice] = useState("");
  // Federated sign-in providers (configured only; empty = invisible).
  const [providers, setProviders] = useState([]);
  const [welcomeName, setWelcomeName] = useState("");
  const [savedChoice, setSavedChoice] = useState("");
  const [savedName, setSavedName] = useState("");

  // Read-only account summary: the backend has no profile-update
  // endpoint, so nothing here is editable.
  async function loadMe() {
    if (!getToken()) {
      setMe(null);
      return;
    }
    try {
      const r = await api("/api/auth/me");
      setMe(r);
    } catch {
      // offline or stale token: summary simply stays hidden
      setMe(null);
    }
  }

  useEffect(() => {
    // Federated callback lands here as #token=... (see backend meta.py).
    if (window.location.hash.startsWith("#token=")) {
      setToken(window.location.hash.slice("#token=".length));
      window.location.hash = "";
    }
    loadMe();
    getAuthProviders().then((r) => setProviders(r.providers || [])).catch(() => setProviders([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!me) return;
    getWelcomePreference()
      .then((p) => {
        setSavedChoice(p.welcome_choice || "");
        setSavedName(p.welcome_display_name || "");
      })
      .catch(() => {});
  }, [me]);

  async function doRegister() {
    try {
      const r = await register(handle, pw, "free", welcomeChoice || null, welcomeChoice === "named" ? welcomeName : null);
      setToken(r.token);
      setMsg(t("settings.loggedIn"));
      if (r.user) setMe(r.user);
      else await loadMe();
    } catch (e) {
      setMsg(e.message);
    }
  }

  async function saveWelcomeChoice() {
    if (!savedChoice) return;
    try {
      await setWelcomePreference(savedChoice, savedChoice === "named" ? savedName : null);
      setMsg(t("welcome.choiceSaved"));
    } catch (e) {
      setMsg(e.message);
    }
  }

  async function doLogin() {
    try {
      const r = await login(handle, pw);
      setToken(r.token);
      setMsg(t("settings.loggedIn"));
      if (r.user) setMe(r.user);
      else await loadMe();
    } catch (e) {
      setMsg(e.message);
    }
  }

  function doLogout() {
    setToken("");
    setMe(null);
    setMsg("");
  }

  return (
    <section className="page">
      <div className="page-head">
        <h1>{t("nav.platform")}</h1>
      </div>

      <div className="card section-block">
        <h2>{t("settings.accountTitle")}</h2>
        {/* FIRST onboarding question, before handle and password: how (or
            whether) the welcome banner may celebrate this member. */}
        <WelcomeChoiceFields choice={welcomeChoice} setChoice={setWelcomeChoice} name={welcomeName} setName={setWelcomeName} />
        <div className="field-row">
          <label>
            {t("settings.handle")}{" "}
            <input id="settings-handle" value={handle} onChange={(e) => setHandle(e.target.value)} />
          </label>
          <DictateButton onText={(text) => setHandle(text)} />
        </div>
        <div className="field-row">
          <label>
            {t("settings.password")}{" "}
            <input type="password" value={pw} onChange={(e) => setPw(e.target.value)} />
          </label>
        </div>
        {/* Guided talk-to-fill walk: the handle is the only field it asks
            for — the password is never dictated (no mic on passwords). */}
        <GuidedFill fields={[{ id: "settings-handle", label: t("settings.handle"), setValue: setHandle }]} />
        <button type="button" className="btn" onClick={doRegister}>
          {t("settings.register")}
        </button>
        <button type="button" className="btn-ghost" onClick={doLogin}>
          {t("settings.login")}
        </button>
        {providers.map((p) => (
          <a key={p.id} className="btn-ghost" href={`/api/auth/${p.id}/start`}>
            {t("settings.continueWith")} {p.label}
          </a>
        ))}
      </div>

      {me && (
        <div className="card section-block">
          <p>
            {t("settings.signedInAs")}: {me.handle}
          </p>
          {me.role && (
            <p className="muted">
              {t("settings.roleLabel")}: {me.role}
            </p>
          )}
          {me.tier && (
            <p className="muted">
              {t("settings.planLabel")}: {me.tier}
            </p>
          )}
          <button type="button" className="btn-ghost" onClick={doLogout}>
            {t("settings.logout")}
          </button>
        </div>
      )}

      {me && (
        <div className="card section-block">
          <h2>{t("welcome.choiceTitle")}</h2>
          <WelcomeChoiceFields choice={savedChoice} setChoice={setSavedChoice} name={savedName} setName={setSavedName} />
          <button type="button" className="btn" onClick={saveWelcomeChoice}>
            {t("welcome.saveChoice")}
          </button>
        </div>
      )}

      <div className="card section-block">
        <h2>{t("readAloud.title")}</h2>
        <p>{t("readAloud.help")}</p>
        <ReadAloud text={t("readAloud.help")} />
      </div>

      <MusicPlayer />
      {msg && <p role="status">{msg}</p>}
    </section>
  );
}
