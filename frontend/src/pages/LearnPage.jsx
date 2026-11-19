import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import ReadAloud from "../components/ReadAloud";
import { COURSES } from "../data/phase3";
import { api } from "../api";

const KEY_BY_ID = Object.fromEntries(COURSES.map((c) => [c.id, c.key]));
const COUNT_BY_ID = Object.fromEntries(COURSES.map((c) => [c.id, c.modules]));

function doneKey(courseId, moduleId) {
  return `${courseId}:${moduleId}`;
}

function normalizeDone(list) {
  const out = new Set();
  (list || []).forEach((d) => {
    if (typeof d === "string") {
      if (d.includes(":")) out.add(d);
    } else if (d && d.course_id && d.module_id) {
      out.add(doneKey(d.course_id, d.module_id));
    }
  });
  return out;
}

function localCatalog() {
  return COURSES.map((c) => ({ id: c.id, key: c.key, title: null, count: c.modules, modules: null }));
}

function serverCatalog(list) {
  return (list || []).map((c) => ({
    id: c.id,
    key: KEY_BY_ID[c.id] || null,
    title: c.title || null,
    count: Array.isArray(c.modules) ? c.modules.length : COUNT_BY_ID[c.id] || 0,
    modules: Array.isArray(c.modules) ? c.modules : null,
  }));
}

export default function LearnPage() {
  const { t } = useTranslation();
  const [catalog, setCatalog] = useState(localCatalog);
  const [doneSet, setDoneSet] = useState(() => new Set());
  const [progressKnown, setProgressKnown] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailFailed, setDetailFailed] = useState(false);
  const [activeModule, setActiveModule] = useState(null);
  const [picked, setPicked] = useState(null);
  const [quizState, setQuizState] = useState(null);
  const [msg, setMsg] = useState("");
  const openSeq = useRef(0);

  // Rich catalog + progress when signed in; any failure keeps the local
  // catalog (counts only) so the page still renders fully offline.
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const r = await api("/api/learning/courses");
        if (alive && Array.isArray(r.courses) && r.courses.length) setCatalog(serverCatalog(r.courses));
      } catch {
        // offline / no course access: local COURSES stand
      }
      try {
        const r = await api("/api/learning/courses_progress");
        if (alive && Array.isArray(r.done_modules)) {
          setDoneSet(normalizeDone(r.done_modules));
          setProgressKnown(true);
        }
      } catch {
        // progress unknown offline; cards simply omit it
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  function courseName(c) {
    return c.key ? t(`phase3.${c.key}`) : c.title || c.id;
  }

  function countDone(courseId, modules) {
    if (Array.isArray(modules)) {
      return modules.filter((m) => doneSet.has(doneKey(courseId, m.id))).length;
    }
    const prefix = `${courseId}:`;
    return [...doneSet].filter((k) => k.startsWith(prefix)).length;
  }

  async function openCourse(entry) {
    const seq = ++openSeq.current;
    setSelectedId(entry.id);
    setActiveModule(null);
    setPicked(null);
    setQuizState(null);
    if (entry.modules) {
      setDetail({ id: entry.id, modules: entry.modules });
      setDetailFailed(false);
      return;
    }
    setDetail(null);
    setDetailFailed(false);
    try {
      const r = await api(`/api/learning/courses/${entry.id}`);
      if (seq !== openSeq.current) return;
      setDetail({ id: entry.id, modules: Array.isArray(r.modules) ? r.modules : [] });
      setDetailFailed(false);
    } catch {
      if (seq !== openSeq.current) return;
      setDetail(null);
      setDetailFailed(true);
    }
  }

  function backToList() {
    openSeq.current += 1;
    setSelectedId(null);
    setDetail(null);
    setDetailFailed(false);
    setActiveModule(null);
    setPicked(null);
    setQuizState(null);
  }

  function openModule(mod) {
    setActiveModule(mod);
    setPicked(null);
    setQuizState(null);
  }

  async function checkAnswer() {
    if (!selectedId || !activeModule || activeModule.placeholder) return;
    if (picked === null) {
      setQuizState("wrong");
      setMsg(t("learn.tryAgain"));
      return;
    }
    try {
      const r = await api("/api/learning/courses/quiz", {
        method: "POST",
        body: { course_id: selectedId, module_id: activeModule.id, answer: picked },
      });
      if (!r.correct) {
        setQuizState("wrong");
        setMsg(t("learn.tryAgain"));
        return;
      }
      setQuizState("correct");
      setMsg(t("learn.correct"));
      try {
        const p = await api("/api/learning/courses/progress", {
          method: "POST",
          body: { course_id: selectedId, module_id: activeModule.id },
        });
        if (Array.isArray(p.done_modules)) {
          setDoneSet(normalizeDone(p.done_modules));
        } else {
          setDoneSet((prev) => new Set(prev).add(doneKey(selectedId, activeModule.id)));
        }
      } catch {
        setDoneSet((prev) => new Set(prev).add(doneKey(selectedId, activeModule.id)));
      }
      setProgressKnown(true);
    } catch (e) {
      setMsg(e.message);
    }
  }

  const selected = catalog.find((c) => c.id === selectedId) || null;
  const selectedModules = detail && selected && detail.id === selected.id ? detail.modules : null;
  const total = selected ? (selectedModules ? selectedModules.length : selected.count) : 0;
  const doneCount = selected ? countDone(selected.id, selectedModules) : 0;
  const pct = total ? Math.round((doneCount / total) * 100) : 0;
  const quiz = activeModule && !activeModule.placeholder && Array.isArray(activeModule.quiz) ? activeModule.quiz[0] : null;

  return (
    <section className="page">
      <div className="page-head">
        <h1>{t("nav.learning")}</h1>
      </div>

      {!selected && (
        <div className="section-block">
          <h2>{t("phase3.coursesTitle")}</h2>
          <p className="lede">{t("phase3.paidNote")}</p>
          <div className="card-grid">
            {catalog.map((c) => (
              <article key={c.id} data-testid={`course-${c.id}`} className="course-card">
                <h3>
                  {courseName(c)}{" "}
                  <span className="badge badge-draft">{t("phase3.coursesDraft")}</span>
                </h3>
                <ReadAloud text={courseName(c)} />
                <p className="muted">{t("learn.moduleCount", { count: c.count })}</p>
                {progressKnown && (
                  <p className="muted">
                    {t("learn.progressLabel")}: {countDone(c.id, c.modules)}/{c.count}
                  </p>
                )}
                {c.id === "relapse_prevention" && <p>988 / 911</p>}
                <button type="button" className="btn" onClick={() => openCourse(c)}>
                  {t("learn.open")}
                </button>
              </article>
            ))}
          </div>
        </div>
      )}

      {selected && (
        <div className="section-block">
          <button type="button" className="btn-ghost" onClick={backToList}>
            {t("learn.back")}
          </button>
          <h2>
            {courseName(selected)}{" "}
            <span className="badge badge-draft">{t("phase3.coursesDraft")}</span>
          </h2>
          {selected.id === "relapse_prevention" && <p>988 / 911</p>}
          <div
            className="progress-track"
            role="progressbar"
            aria-label={t("learn.progressLabel")}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={pct}
          >
            <div className="progress-fill" style={{ width: `${pct}%` }} />
          </div>
          <p className="muted">
            {t("learn.progressLabel")}: {doneCount}/{total} ({pct}%)
          </p>

          {selectedModules &&
            selectedModules.map((m) => {
              const done = doneSet.has(doneKey(selected.id, m.id));
              return (
                <button
                  key={m.id}
                  type="button"
                  className={`module-row${done ? " done" : ""}`}
                  onClick={() => openModule(m)}
                >
                  <span>
                    {m.title}
                    {done ? " ✓" : ""}
                  </span>
                  {m.objective && <span className="muted">{m.objective}</span>}
                </button>
              );
            })}

          {detailFailed &&
            Array.from({ length: selected.count }, (_, i) => (
              <button
                key={i}
                type="button"
                className="module-row"
                onClick={() => openModule({ placeholder: true, index: i })}
              >
                <span>{t("learn.moduleLabel", { n: i + 1 })}</span>
              </button>
            ))}

          {activeModule && activeModule.placeholder && (
            <section className="lesson-stage">
              <p className="notice">{t("learn.signInNote")}</p>
            </section>
          )}

          {activeModule && !activeModule.placeholder && (
            <section className="lesson-stage">
              <h3>{activeModule.title}</h3>
              {activeModule.objective && <p className="kicker">{activeModule.objective}</p>}
              {activeModule.content && <p>{activeModule.content}</p>}
              {activeModule.content && <ReadAloud text={activeModule.content} />}
              {quiz && (
                <>
                  <p>{quiz.prompt}</p>
                  <div className="quiz-options">
                    {(quiz.options || []).map((opt, i) => (
                      <button
                        key={i}
                        type="button"
                        className="quiz-option"
                        aria-pressed={picked === i}
                        onClick={() => {
                          setPicked(i);
                          setQuizState(null);
                        }}
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                  <button type="button" className="btn" onClick={checkAnswer}>
                    {t("phase3.checkAnswer")}
                  </button>
                  {quizState === "correct" && <p>{t("learn.correct")}</p>}
                  {quizState === "wrong" && <p>{t("learn.tryAgain")}</p>}
                </>
              )}
            </section>
          )}
        </div>
      )}

      {msg && <p role="status">{msg}</p>}
    </section>
  );
}
