import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, getToken } from "../api";
import { DictateButton } from "./Dictation";

// AI resume assist: two entry paths (talk it through / paste an old resume).
// The backend (app/routers/work.py) is OFF until GW_META_MODEL_API_KEY is
// set: it then answers 503 with an honest message, which is shown as-is. The
// draft opens in editable fields; a save goes through PUT, which clears the
// AI-draft mark. Building a resume yourself never depends on any of this.

async function fetchFile(rid, kind) {
  const res = await fetch(`/api/work/resume_builder/${rid}/${kind}`, { headers: { Authorization: `Bearer ${getToken()}` } });
  if (!res.ok) throw new Error(`${kind} failed (${res.status})`);
  return res.blob();
}

export async function printResume(rid) {
  const blob = await fetchFile(rid, "print");
  window.open(URL.createObjectURL(blob), "_blank");
}

export async function downloadPdf(rid) {
  const blob = await fetchFile(rid, "pdf");
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "resume.pdf";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// Print and PDF buttons for one stored resume (also used in the saved list).
export function ResumeFileButtons({ rid, onError }) {
  const { t } = useTranslation();
  const run = (fn) => async () => { try { await fn(rid); } catch (e) { if (onError) onError(e.message); } };
  return (
    <>
      <button type="button" className="btn-ghost btn-small" onClick={run(printResume)}>{t("resumeAi.printPdf")}</button>{" "}
      <button type="button" className="btn-ghost btn-small" onClick={run(downloadPdf)}>{t("resumeAi.downloadPdf")}</button>
    </>
  );
}

export default function ResumeAssist({ onChanged }) {
  const { t } = useTranslation();
  const [mode, setMode] = useState("");
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [targetJob, setTargetJob] = useState("");
  const [pasteText, setPasteText] = useState("");
  const [msg, setMsg] = useState("");
  const [draft, setDraft] = useState(null);
  const [fullName, setFullName] = useState("");
  const [headline, setHeadline] = useState("");
  const [summary, setSummary] = useState("");
  const [skills, setSkills] = useState("");

  useEffect(() => {
    api("/api/work/resume_builder/assist/questions").then((d) => setQuestions(d.questions || [])).catch(() => {});
  }, []);

  function openDraft(d) {
    setDraft(d);
    setFullName(d.full_name || "");
    setHeadline(d.headline || "");
    setSummary(d.summary || "");
    setSkills((d.skills || []).join(", "));
    if (onChanged) onChanged();
  }
  const fail = (e) => setMsg(e.data?.detail || e.message || t("resumeAi.failed"));

  async function generate() {
    setMsg("");
    try {
      const list = Object.entries(answers).filter(([, v]) => v && v.trim()).map(([question_id, answer]) => ({ question_id, answer }));
      openDraft(await api("/api/work/resume_builder/assist/generate", { method: "POST", body: { answers: list, target_job: targetJob || null } }));
    } catch (e) { fail(e); }
  }
  async function importPasted() {
    setMsg("");
    try {
      openDraft(await api("/api/work/resume_builder/assist/import", { method: "POST", body: { text: pasteText } }));
    } catch (e) { fail(e); }
  }
  async function save() {
    if (!draft) return;
    try {
      const d = await api(`/api/work/resume_builder/${draft._id}`, {
        method: "PUT",
        body: { full_name: fullName || draft.full_name, headline, summary, skills: skills.split(",").map((x) => x.trim()).filter(Boolean), experience: draft.experience || [] },
      });
      setDraft(d);
      setMsg(t("resumeAi.savedNote"));
      if (onChanged) onChanged();
    } catch (e) { setMsg(e.message); }
  }

  return (
    <div data-testid="resume-ai-section">
      <h3>{t("resumeAi.assistTitle")}</h3>
      <p className="muted">{t("resumeAi.assistHelp")}</p>
      <button type="button" className="btn" onClick={() => setMode("guided")}>{t("resumeAi.talkTitle")}</button>{" "}
      <button type="button" className="btn-ghost" onClick={() => setMode("import")}>{t("resumeAi.pasteTitle")}</button>
      {mode === "guided" && (
        <div data-testid="resume-ai-guided">
          <p className="muted">{t("resumeAi.talkHelp")}</p>
          <label>{t("resumeAi.targetJob")} <input aria-label={t("resumeAi.targetJob")} value={targetJob} onChange={(e) => setTargetJob(e.target.value)} /></label>
          {questions.map((q) => (
            <div key={q.id}>
              <label>{q.prompt} <textarea aria-label={q.prompt} value={answers[q.id] || ""} onChange={(e) => setAnswers((prev) => ({ ...prev, [q.id]: e.target.value }))} /></label>
              <DictateButton onText={(text) => setAnswers((prev) => ({ ...prev, [q.id]: ((prev[q.id] || "") + " " + text).trim() }))} />
              {q.help && <p className="muted">{q.help}</p>}
            </div>
          ))}
          <button type="button" className="btn" onClick={generate}>{t("resumeAi.writeMine")}</button>
        </div>
      )}
      {mode === "import" && (
        <div data-testid="resume-ai-import">
          <p className="muted">{t("resumeAi.pasteHelp")}</p>
          <label>{t("resumeAi.pasteTitle")} <textarea aria-label={t("resumeAi.pasteTitle")} placeholder={t("resumeAi.pastePlaceholder")} value={pasteText} onChange={(e) => setPasteText(e.target.value)} /></label>
          <DictateButton onText={(text) => setPasteText((prev) => ((prev || "") + " " + text).trim())} />
          <button type="button" className="btn" onClick={importPasted}>{t("resumeAi.cleanItUp")}</button>
        </div>
      )}
      {msg && <p role="status" className="notice">{msg}</p>}
      {draft && (
        <div data-testid="resume-draft">
          {draft.ai_draft && <p role="status" className="notice">{t("resumeAi.draftBanner")}</p>}
          <label>{t("phase3.fullName")} <input aria-label={t("phase3.fullName")} value={fullName} onChange={(e) => setFullName(e.target.value)} /></label>
          <label>{t("phase3.headline")} <input aria-label={t("phase3.headline")} value={headline} onChange={(e) => setHeadline(e.target.value)} /></label>
          <label>{t("phase3.summary")} <textarea aria-label={t("phase3.summary")} value={summary} onChange={(e) => setSummary(e.target.value)} /></label>
          <label>{t("phase3.skills")} <input aria-label={t("phase3.skills")} value={skills} onChange={(e) => setSkills(e.target.value)} /></label>
          <pre>{draft.text}</pre>
          <button type="button" className="btn" onClick={save}>{t("resumeAi.saveChanges")}</button>{" "}
          <ResumeFileButtons rid={draft._id} onError={setMsg} />
        </div>
      )}
    </div>
  );
}
