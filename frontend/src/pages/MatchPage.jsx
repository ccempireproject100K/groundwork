import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import ReadAloud from "../components/ReadAloud";
import { negotiate } from "../data/phase3";
import { api } from "../api";

export default function MatchPage() {
  const { t } = useTranslation();
  const [interests, setInterests] = useState("music, walking");
  const [results, setResults] = useState([]);
  const [decisions, setDecisions] = useState([]);
  const [msg, setMsg] = useState("");

  function parsedInterests() {
    return interests
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
  }

  // Friend matching only: dating stays off until a minimum-days rule is
  // set, so the profile is always intent "friend" + friends_only.
  async function postProfile() {
    await api("/api/matching/ai_matching/profile", {
      method: "POST",
      body: { intent: "friend", interests: parsedInterests(), dealbreakers: [], friends_only: true },
    });
  }

  function localPreview(error) {
    // local deterministic preview so the page still explains the flow offline
    const demo = negotiate(
      { interests: parsedInterests(), dealbreakers: [] },
      { interests: ["music"], attributes: {} }
    );
    setResults([{ candidate: { handle: "demo" }, ...demo }]);
    if (error) setMsg(error.message);
  }

  async function loadDecisions() { try { setDecisions((await api("/api/matching/ai_matching/decisions")).decisions || []); } catch {} }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { loadDecisions(); }, []);

  async function run() {
    try {
      await postProfile();
    } catch {
      // offline: ignore and let the run attempt produce the fallback
    }
    try {
      const r = await api("/api/matching/ai_matching/run", { method: "POST" });
      setResults(r.results || []); loadDecisions();
    } catch (e) {
      localPreview(e);
    }
  }

  async function rematch() {
    try {
      await postProfile();
    } catch {
      // offline: ignore and let the rematch attempt produce the fallback
    }
    try {
      const r = await api("/api/matching/ai_matching/rematch", { method: "POST" });
      setResults(r.results || []); loadDecisions();
    } catch {
      await run();
    }
  }

  async function override(h) {
    try {
      await api("/api/matching/ai_matching/override", {
        method: "POST",
        body: { candidate_handle: h },
      });
      setMsg(t("phase3.override"));
    } catch (e) {
      setMsg(e.message);
    }
  }

  function fitBadge(r) {
    if (r.fit === "accept") return { cls: "fit-accept", label: t("match.goodFit") };
    if (r.fit === "excluded") return { cls: "fit-excluded", label: t("phase3.notAvailable") };
    return { cls: "fit-reject", label: t("match.notYet") };
  }

  return (
    <section className="page">
      <div className="page-head">
        <h1>{t("nav.matching")}</h1>
      </div>

      <div className="card section-block">
        <h2>{t("phase3.matchTitle")}</h2>
        <p>{t("phase3.matchHelp")}</p>
        <p className="notice-warm">{t("phase3.datingOff")}</p>
        <p className="muted">{t("match.friendNote")}</p>
        <ReadAloud text={t("phase3.matchHelp")} />
        <div className="field-row">
          <label>
            {t("phase3.interests")}{" "}
            <input value={interests} onChange={(e) => setInterests(e.target.value)} />
          </label>
        </div>
        <button type="button" className="btn" onClick={run}>
          {t("phase3.findMatches")}
        </button>
        <button type="button" className="btn-ghost" onClick={rematch}>
          {t("phase3.rematch")}
        </button>
      </div>

      {results.length > 0 && (
        <div className="card-grid">
          {results.map((r, i) => {
            const handle = r.candidate?.handle || "";
            const badge = fitBadge(r);
            return (
              <article key={`${handle}-${i}`} className="match-card">
                <div className="avatar-disc" aria-hidden="true">
                  {handle.charAt(0).toUpperCase()}
                </div>
                <h3>{handle}</h3>
                <span className={badge.cls}>{badge.label}</span>
                <p className="match-score">
                  {t("match.scoreLabel")}: {r.score}
                </p>
                {(r.reasons || []).length > 0 && (
                  <div>
                    <h4>{t("match.whyTitle")}</h4>
                    <ul>
                      {(r.reasons || []).map((reason, j) => (
                        <li key={j}>{reason}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {r.fit === "reject" && (
                  <button type="button" className="btn-small" onClick={() => override(handle)}>
                    {t("phase3.override")}
                  </button>
                )}
              </article>
            );
          })}
        </div>
      )}

      <div data-testid="match-decisions"><h2>{t("gap.decisionsTitle")}</h2>
        {decisions.length === 0 ? null : <ul>{decisions.map((d) => <li key={d._id}>{d.candidate_handle} — {d.fit} ({d.score})</li>)}</ul>}</div>
      {msg && <p role="status">{msg}</p>}
    </section>
  );
}
