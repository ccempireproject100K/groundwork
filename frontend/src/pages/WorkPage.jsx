import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api";
import ReadAloud from "../components/ReadAloud";
import ResumeAssist, { ResumeFileButtons } from "../components/ResumeAssist";
import { INTERVIEW_QUESTIONS, scoreInterview } from "../data/phase3";
export default function WorkPage() {
  const { t } = useTranslation();
  const [jobs, setJobs] = useState([]);
  const [name, setName] = useState("");
  const [resume, setResume] = useState(null);
  const [qid, setQid] = useState("q1");
  const [answer, setAnswer] = useState("");
  const [score, setScore] = useState(null);
  const [gig, setGig] = useState("");
  const [msg, setMsg] = useState("");
  const [apps, setApps] = useState([]);
  const [gigs, setGigs] = useState([]);
  const [gigMsg, setGigMsg] = useState("");
  const [resumes, setResumes] = useState([]);
  async function loadResumes() { try { setResumes((await api("/api/work/resume_builder")).resumes || []); } catch {} }
  async function delResume(rid) { try { await api(`/api/work/resume_builder/${rid}`, { method: "DELETE" }); loadResumes(); } catch (e) { setMsg(e.message); } }
  async function loadApps() { try { setApps((await api("/api/work/application_tracker")).applications || []); } catch {} }
  async function loadGigs() { try { setGigs((await api("/api/work/micro_gigs")).gigs || []); } catch {} }
  useEffect(() => { api("/api/work/job_board?second_chance=true").then((d) => setJobs(d.jobs || [])).catch(() => {}); loadApps(); loadGigs(); loadResumes(); }, []);
  async function track(job) { try { await api("/api/work/application_tracker", { method: "POST", body: { job_id: job.id, status: "applied" } }); loadApps(); } catch (e) { setMsg(e.message); } }
  async function applyGig(g) { try { await api(`/api/work/micro_gigs/${g._id}/apply`, { method: "POST", body: { message: gigMsg || "I am interested in this gig." } }); setMsg(t("gap.applied")); } catch (e) { setMsg(e.message); } }
  async function build() {
    try { setResume(await api("/api/work/resume_builder", { method: "POST", body: { full_name: name || "Alex", headline: "", summary: "", skills: [], experience: [] } })); }
    catch { setResume({ full_name: name || "Alex", text: `${name || "Alex"}` }); }
    loadResumes();
  }
  async function grade() {
    const local = scoreInterview(qid, answer);
    try { setScore(await api("/api/work/interview_coach/sessions", { method: "POST", body: { question_id: qid, answer } })); }
    catch { setScore(local); }
  }
  async function postGig() { try { await api("/api/work/micro_gigs", { method: "POST", body: { title: gig, description: gig } }); setMsg(gig); setGig(""); loadGigs(); } catch (e) { setMsg(e.message); } }
  return (
    <section>
      <h1>{t("nav.work")}</h1>
      <h2>{t("work.jobsTitle")}</h2>
      <p>{t("work.paroleNote")}</p>
      <ul>{jobs.map((j) => <li key={j.id}>{j.title} — {j.company}, {j.location} <button type="button" onClick={() => track(j)}>{t("gap.trackJob")}</button></li>)}</ul>
      <div data-testid="tracker-section"><h2>{t("gap.trackerTitle")}</h2>
        {apps.length === 0 ? <p>{t("gap.trackerEmpty")}</p> : <ul>{apps.map((a) => <li key={a._id}>{a.job_id} — {t("gap.statusLabel")}: {a.status}</li>)}</ul>}</div>
      <div data-testid="resume-section"><h2>{t("phase3.resumeTitle")}</h2><p>{t("phase3.resumeHelp")}</p><ReadAloud text={t("phase3.resumeHelp")} />
        <ResumeAssist onChanged={loadResumes} />
        <label>{t("phase3.fullName")} <input value={name} onChange={(e) => setName(e.target.value)} /></label>
        <button type="button" onClick={build}>{t("phase3.buildResume")}</button>
        {resume && <p role="status">{resume.full_name}</p>}
        {resumes.length > 0 && <><h3>{t("gap.resumesMine")}</h3><ul>{resumes.map((r) => <li key={r._id}>{r.full_name}{r.ai_draft && <> <span className="badge">{t("resumeAi.aiDraftBadge")}</span></>} <ResumeFileButtons rid={r._id} onError={setMsg} /> <button type="button" onClick={() => delResume(r._id)}>{t("gap.remove")}</button></li>)}</ul></>}</div>
      <div data-testid="interview-section"><h2>{t("phase3.interviewTitle")}</h2><p>{t("phase3.interviewHelp")}</p><ReadAloud text={t("phase3.interviewHelp")} />
        <label>Q <select value={qid} onChange={(e) => setQid(e.target.value)}>{INTERVIEW_QUESTIONS.map((q) => <option key={q.id} value={q.id}>{q.prompt}</option>)}</select></label>
        <label>{t("phase3.answer")} <textarea value={answer} onChange={(e) => setAnswer(e.target.value)} /></label>
        <button type="button" onClick={grade}>{t("phase3.score")}</button>
        {score && <p role="status">{score.score}</p>}</div>
      <div data-testid="gigs-section"><h2>{t("phase3.gigsTitle")}</h2><p>{t("phase3.gigsHelp")}</p><ReadAloud text={t("phase3.gigsHelp")} />
        <label>{t("phase3.gigTitle")} <input value={gig} onChange={(e) => setGig(e.target.value)} /></label>
        <button type="button" onClick={postGig}>{t("phase3.postGig")}</button>
        <label>{t("gap.gigMessage")} <input value={gigMsg} onChange={(e) => setGigMsg(e.target.value)} /></label>
        {gigs.length === 0 ? <p>{t("gap.gigsEmpty")}</p> : <ul>{gigs.map((g) => <li key={g._id}>{g.title} — {g.city} <button type="button" onClick={() => applyGig(g)}>{t("gap.applyGig")}</button></li>)}</ul>}
        {msg && <p role="status">{msg}</p>}</div>
    </section>
  );
}
