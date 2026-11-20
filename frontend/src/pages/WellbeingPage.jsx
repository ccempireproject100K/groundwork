import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import { isRough, suggestFilters } from "../lib/mood";
import ReadAloud from "../components/ReadAloud";
const MOODS = ["good", "okay", "rough", "struggling", "craving"];
const LOCK_KINDS = [["week", "gap.kindWeek"], ["two_weeks", "gap.kindTwoWeeks"], ["month", "gap.kindMonth"], ["permanent", "gap.kindPermanent"]];
export default function WellbeingPage() {
  const { t } = useTranslation();
  const [mood, setMood] = useState("okay");
  const [msg, setMsg] = useState("");
  const [lockTarget, setLockTarget] = useState("community_feed");
  const [lockKind, setLockKind] = useState("week");
  const [history, setHistory] = useState([]);
  const [filters, setFilters] = useState([]);
  const [activeFilters, setActiveFilters] = useState([]);
  const [locks, setLocks] = useState([]);
  const suggested = suggestFilters(mood);
  async function loadAll() {
    try { setHistory((await api("/api/wellbeing/mood_checkins")).checkins || []); } catch {}
    try { const d = await api("/api/wellbeing/filters"); setFilters(d.filters || []); setActiveFilters(d.active || []); } catch {}
    try { setLocks((await api("/api/wellbeing/locks")).locks || []); } catch {}
  }
  useEffect(() => { loadAll(); }, []);
  async function submit() {
    try { const r = await api("/api/wellbeing/mood_checkins", { method: "POST", body: { mood } }); setMsg(r.show_crisis ? t("wellbeing.roughHelp") : t("wellbeing.saved")); loadAll(); }
    catch { setMsg(t("wellbeing.loginNeeded")); }
  }
  async function addLock() {
    try { await api("/api/wellbeing/locks", { method: "POST", body: { target: lockTarget, kind: lockKind } }); setMsg(t("wellbeing.lockSaved")); loadAll(); } catch (e) { setMsg(e.message); }
  }
  async function removeLock(lid) { try { await api(`/api/wellbeing/locks/${lid}`, { method: "DELETE" }); loadAll(); } catch (e) { setMsg(e.message); } }
  async function dontRemind(lid) { try { await api(`/api/wellbeing/locks/${lid}/dont_remind`, { method: "POST" }); loadAll(); } catch (e) { setMsg(e.message); } }
  async function addFilter(target) { try { await api("/api/wellbeing/filters", { method: "POST", body: { target } }); setMsg(t("gap.savedGeneric")); loadAll(); } catch (e) { setMsg(e.message); } }
  async function removeFilter(fid) { try { await api(`/api/wellbeing/filters/${fid}`, { method: "DELETE" }); loadAll(); } catch (e) { setMsg(e.message); } }
  return (
    <section>
      <h1>{t("nav.wellbeing")}</h1>
      <h2>{t("wellbeing.checkinTitle")}</h2>
      <div role="radiogroup" aria-label={t("wellbeing.checkinTitle")}>{MOODS.map((m) => <label key={m}><input type="radio" name="mood" checked={mood === m} onChange={() => setMood(m)} /> {t(`wellbeing.mood.${m}`)}</label>)}</div>
      <button type="button" onClick={submit}>{t("wellbeing.save")}</button>
      {isRough(mood) && <div data-testid="filter-suggestion"><p>{t("wellbeing.suggestFilters")}: {suggested.join(", ")}</p><p>{t("wellbeing.roughHelp")}</p></div>}
      <ReadAloud text={t("wellbeing.checkinTitle")} />
      <div data-testid="filters-section"><h2>{t("gap.filtersTitle")}</h2><p>{t("gap.filtersHelp")}</p>
        {suggested.map((s) => <p key={s}>{s} <button type="button" onClick={() => addFilter(s)}>{t("gap.addFilter")}</button></p>)}
        <ul>{filters.map((f) => <li key={f._id}>{f.target} — {f.set_on}{activeFilters.includes(f.target) ? ` (${t("gap.active")})` : ""} <button type="button" onClick={() => removeFilter(f._id)}>{t("gap.remove")}</button></li>)}</ul></div>
      <h2>{t("wellbeing.locksTitle")}</h2>
      <p>{t("wellbeing.locksHelp")}</p>
      <label>{t("wellbeing.lockTarget")} <select value={lockTarget} onChange={(e) => setLockTarget(e.target.value)}><option value="community_feed">community_feed</option><option value="peer_messaging">peer_messaging</option><option value="ai_matching">ai_matching</option></select></label>
      <label>{t("gap.lockKind")} <select value={lockKind} onChange={(e) => setLockKind(e.target.value)}>{LOCK_KINDS.map(([k, label]) => <option key={k} value={k}>{t(label)}</option>)}</select></label>
      <button type="button" onClick={addLock}>{t("wellbeing.addLock")}</button>
      <div data-testid="locks-section"><h3>{t("gap.myLocks")}</h3>
        {locks.length === 0 ? <p>{t("gap.locksEmpty")}</p> : <ul>{locks.map((l) => <li key={l._id}>{l.target} — {l.kind} ({l.active ? t("gap.active") : t("gap.ended")}) <button type="button" onClick={() => removeLock(l._id)}>{t("gap.remove")}</button>{l.kind === "permanent" && !l.dont_remind && <button type="button" onClick={() => dontRemind(l._id)}>{t("gap.dontRemind")}</button>}</li>)}</ul>}</div>
      <div data-testid="mood-history"><h2>{t("gap.historyTitle")}</h2>
        {history.length === 0 ? <p>{t("gap.historyEmpty")}</p> : <ul>{history.slice(-10).reverse().map((c) => <li key={c._id}>{c.mood} — {String(c.created_at || "").slice(0, 10)}</li>)}</ul>}</div>
      {msg && <p role="status">{msg}</p>}
    </section>
  );
}
