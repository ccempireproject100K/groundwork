import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

// Tap-and-talk dictation, browser-native speech recognition only (the launch
// standard, mirrored from Trade Circle's Dictation.jsx via the Groundwork-YEE
// build of the same pattern). Nothing is recorded or sent to our servers: the
// browser turns voice into text, the text lands in the field as if typed,
// stays editable, and never auto-submits. Where the browser has no speech
// recognition, the controls simply do not appear.

const Recognition = typeof window !== "undefined" ? window.SpeechRecognition || window.webkitSpeechRecognition : undefined;

export function dictationSupported() {
  return Boolean(Recognition);
}

// Recognition language follows the page's selected language (this app's 21).
const LANG_TAGS = {
  en: "en-US", es: "es-ES", fr: "fr-FR", hi: "hi-IN", vi: "vi-VN", ar: "ar-SA",
  tl: "tl-PH", ht: "ht-HT", zh: "zh-CN", ko: "ko-KR", pt: "pt-BR", ru: "ru-RU",
  so: "so-SO", ur: "ur-PK", bn: "bn-BD", pa: "pa-IN", fa: "fa-IR", am: "am-ET",
  my: "my-MM", ne: "ne-NP", sw: "sw-KE",
};

export function recognitionLang(pageLang) {
  if (!pageLang) return (typeof navigator !== "undefined" && navigator.language) || "en-US";
  if (pageLang.includes("-")) return pageLang;
  return LANG_TAGS[pageLang] || (typeof navigator !== "undefined" && navigator.language) || "en-US";
}

function speakPrompt(text, lang) {
  try {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = lang;
    window.speechSynthesis.speak(u);
  } catch { /* spoken prompts are a bonus; the on-screen prompt is the walk */ }
}

function cancelSpeech() {
  try {
    if (typeof window !== "undefined" && "speechSynthesis" in window) window.speechSynthesis.cancel();
  } catch { /* nothing to cancel */ }
}

// One listening session for one piece of text. onText receives final text;
// onEnd fires when the browser ends the session (a pause ends it too, and
// callers advance gracefully — the visitor is never trapped).
export function useDictation(onText, onEnd) {
  const { i18n } = useTranslation();
  const [state, setState] = useState(Recognition ? "idle" : "unsupported"); // idle | listening | denied | error | unsupported
  const [interim, setInterim] = useState("");
  const recognizer = useRef(null);
  const textCb = useRef(onText);
  textCb.current = onText;
  const endCb = useRef(onEnd);
  endCb.current = onEnd;

  const stop = () => { recognizer.current?.stop(); };

  const start = () => {
    if (!Recognition || recognizer.current) return;
    const r = new Recognition();
    r.lang = recognitionLang(i18n.language);
    r.continuous = false;
    r.interimResults = true;
    r.onresult = (event) => {
      let finished = "";
      let pending = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const text = event.results[i][0].transcript;
        if (event.results[i].isFinal) finished += text;
        else pending += text;
      }
      if (finished.trim()) textCb.current(finished.trim());
      setInterim(pending);
    };
    r.onerror = (event) => {
      setState(event.error === "not-allowed" || event.error === "service-not-allowed" ? "denied" : "error");
    };
    r.onend = () => {
      recognizer.current = null;
      setInterim("");
      setState((s) => (s === "listening" ? "idle" : s));
      if (endCb.current) endCb.current();
    };
    recognizer.current = r;
    setState("listening");
    try { r.start(); } catch { recognizer.current = null; setState("error"); }
  };

  // Leaving the page always stops the microphone.
  useEffect(() => () => { recognizer.current?.abort(); cancelSpeech(); }, []);

  return { state, interim, start, stop };
}

// Small secondary mic for correcting one field. Never rendered where the
// browser lacks support, and never used on password fields.
export function DictateButton({ onText }) {
  const { t } = useTranslation();
  const { state, interim, start, stop } = useDictation(onText);
  if (state === "unsupported") return null;
  return (
    <span className="dictate-inline">
      {state === "listening" ? (
        <button type="button" className="btn-danger btn-small" onClick={stop}>{t("dictation.stop")}</button>
      ) : (
        <button type="button" className="btn-ghost btn-small" onClick={start}>{t("dictation.talk")}</button>
      )}
      {interim && <span className="muted">{interim}</span>}
      {state === "denied" && <span className="muted">{t("dictation.denied")}</span>}
      {state === "error" && <span className="muted">{t("dictation.error")}</span>}
    </span>
  );
}

const NEXT_WORDS = ["next", "skip"];
const BACK_WORDS = ["go back", "back"];
const STOP_WORDS = ["stop", "done"];

function commandFor(text) {
  const w = text.trim().toLowerCase().replace(/[.!?]+$/, "");
  if (NEXT_WORDS.includes(w)) return "next";
  if (BACK_WORDS.includes(w)) return "back";
  if (STOP_WORDS.includes(w)) return "stop";
  return null;
}

// The primary control: ONE "Fill it in by talking" button per form. It walks
// the visitor field by field — highlight + on-screen prompt (spoken where
// available), listen, fill, advance. "next"/"skip", "go back", "stop"/"done"
// are spoken commands; a pause that ends the session simply advances. The
// visitor can stop at any time, review and edit everything, and submit only
// by tapping the form's own button — the walk never submits anything.
// fields: [{ id, label, setValue }] — password fields must never be passed.
export function GuidedFill({ fields }) {
  const { t, i18n } = useTranslation();
  const [active, setActive] = useState(-1); // -1 = walk not running
  const [finished, setFinished] = useState(false);
  const fieldsRef = useRef(fields);
  fieldsRef.current = fields;
  const activeRef = useRef(-1);
  const heardRef = useRef(false);
  const needStartRef = useRef(false); // a field is current but its session has not started yet

  function highlight(index) {
    fieldsRef.current.forEach((f, i) => {
      const el = typeof document !== "undefined" ? document.getElementById(f.id) : null;
      if (el) el.classList.toggle("guided-active", i === index);
    });
    const el = index >= 0 && typeof document !== "undefined" ? document.getElementById(fieldsRef.current[index].id) : null;
    if (el) { el.focus(); if (typeof el.scrollIntoView === "function") el.scrollIntoView({ block: "nearest" }); }
  }

  function endWalk() {
    activeRef.current = -1;
    needStartRef.current = false;
    setActive(-1);
    setFinished(true);
    highlight(-1);
    cancelSpeech();
    stopListening();
  }

  function goTo(index) {
    const list = fieldsRef.current;
    if (index >= list.length) { endWalk(); return; }
    if (index < 0) index = 0;
    activeRef.current = index;
    setActive(index);
    setFinished(false);
    heardRef.current = false;
    needStartRef.current = true;
    highlight(index);
    speakPrompt(t("dictation.askField", { field: list[index].label }), recognitionLang(i18n.language));
    startListening(); // no-ops if the previous session is still winding down; handleEnd retries
  }

  function handleText(text) {
    const cmd = commandFor(text);
    const index = activeRef.current;
    if (index < 0) return;
    heardRef.current = true;
    if (cmd === "stop") { endWalk(); return; }
    if (cmd === "back") { goTo(index - 1); return; }
    if (cmd === "next") { goTo(index + 1); return; }
    fieldsRef.current[index].setValue(text);
    goTo(index + 1);
  }

  function handleEnd() {
    if (activeRef.current < 0) return;
    if (needStartRef.current) { startListening(); return; }
    // A pause ended the session: if the visitor said nothing actionable,
    // advance gracefully instead of trapping them on this field.
    if (!heardRef.current) goTo(activeRef.current + 1);
  }

  const { state, interim, start: startListening, stop: stopListening } = useDictation(handleText, handleEnd);

  useEffect(() => { if (state === "listening") needStartRef.current = false; }, [state]);

  if (!dictationSupported()) return null;

  return (
    <div className="guided-fill">
      {active < 0 ? (
        <button type="button" className="btn" onClick={() => goTo(0)}>{t("dictation.fillByTalking")}</button>
      ) : (
        <div className="notice">
          <p role="status">{t("dictation.nowField", { field: fields[active].label })}</p>
          <p>{t("dictation.askField", { field: fields[active].label })}</p>
          <p className="muted">{t("dictation.commands")}</p>
          {state === "listening" && <p role="status">{t("dictation.listening")}</p>}
          {interim && <p className="muted">{interim}</p>}
          {state === "denied" && <p className="muted">{t("dictation.denied")}</p>}
          {state === "error" && <p className="muted">{t("dictation.error")}</p>}
          <button type="button" className="btn-danger btn-small" onClick={endWalk}>{t("dictation.stop")}</button>
        </div>
      )}
      {finished && active < 0 && <p role="status">{t("dictation.done")}</p>}
      <p className="muted">{t("dictation.privacy")}</p>
    </div>
  );
}
