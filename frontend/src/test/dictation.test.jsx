import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

// Minimal fake of the browser's SpeechRecognition: the component drives it,
// the test feeds it final transcripts and session ends. The component reads
// window.SpeechRecognition at module load (like Trade Circle's), so tests
// stub it BEFORE importing the page, with a fresh module registry per test.
class FakeRecognition {
  static instances = [];
  constructor() { this.lang = ""; FakeRecognition.instances.push(this); }
  start() { this.started = true; }
  stop() { this.stopped = true; if (this.onend) this.onend(); }
  abort() { if (this.onend) this.onend(); }
  emit(text) {
    const result = [{ 0: { transcript: text }, isFinal: true, length: 1 }];
    this.onresult({ resultIndex: 0, results: result });
  }
  end() { if (this.onend) this.onend(); }
}

function lastRecognizer() {
  return FakeRecognition.instances[FakeRecognition.instances.length - 1];
}

async function importSettingsPage() {
  vi.resetModules();
  const mod = await import("../pages/SettingsPage.jsx");
  return mod.default;
}

describe("dictation on the public account form", () => {
  afterEach(() => {
    delete window.SpeechRecognition;
    FakeRecognition.instances = [];
    localStorage.clear();
  });

  it("hides every mic control where the browser lacks speech recognition", async () => {
    delete window.SpeechRecognition;
    const SettingsPage = await importSettingsPage();
    render(<MemoryRouter><SettingsPage /></MemoryRouter>);
    expect(screen.queryByRole("button", { name: "Fill it in by talking" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Talk" })).toBeNull();
  });

  it("guided walk asks for the handle, fills it from speech, and never touches the password", async () => {
    window.SpeechRecognition = FakeRecognition;
    const SettingsPage = await importSettingsPage();
    const { container } = render(<MemoryRouter><SettingsPage /></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: "Fill it in by talking" }));
    expect(await screen.findByText("What is your Handle?")).toBeInTheDocument();
    const handleInput = container.querySelector("#settings-handle");
    expect(handleInput.classList.contains("guided-active")).toBe(true);
    const rec = lastRecognizer();
    expect(rec.started).toBe(true);
    expect(rec.lang).toBe("en-US");
    rec.emit("myhandle");
    await waitFor(() => expect(handleInput.value).toBe("myhandle"));
    // One field only: the walk ends with the review note, nothing submitted.
    expect(await screen.findByText(/nothing was submitted/)).toBeInTheDocument();
    const pw = container.querySelector('input[type="password"]');
    expect(pw.value).toBe("");
    expect(handleInput.classList.contains("guided-active")).toBe(false);
  });

  it("spoken 'stop' ends the walk without filling anything", async () => {
    window.SpeechRecognition = FakeRecognition;
    const SettingsPage = await importSettingsPage();
    const { container } = render(<MemoryRouter><SettingsPage /></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: "Fill it in by talking" }));
    expect(await screen.findByText("What is your Handle?")).toBeInTheDocument();
    lastRecognizer().emit("stop");
    expect(await screen.findByText(/nothing was submitted/)).toBeInTheDocument();
    expect(container.querySelector("#settings-handle").value).toBe("");
  });

  it("the small per-field mic fills the handle as a correction tool", async () => {
    window.SpeechRecognition = FakeRecognition;
    const SettingsPage = await importSettingsPage();
    const { container } = render(<MemoryRouter><SettingsPage /></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: "Talk" }));
    lastRecognizer().emit("voicehandle");
    await waitFor(() => expect(container.querySelector("#settings-handle").value).toBe("voicehandle"));
  });

  it("recognition language follows the page language", async () => {
    vi.resetModules();
    const { recognitionLang } = await import("../components/Dictation.jsx");
    expect(recognitionLang("en")).toBe("en-US");
    expect(recognitionLang("es")).toBe("es-ES");
    expect(recognitionLang("zh")).toBe("zh-CN");
    expect(recognitionLang("ru")).toBe("ru-RU");
    expect(recognitionLang("my")).toBe("my-MM");
    expect(recognitionLang("pt-BR")).toBe("pt-BR");
    expect(recognitionLang("de")).toBe("de-DE");
    expect(recognitionLang("ja")).toBe("ja-JP");
  });

  it("pins a recognition tag for every one of the app's 21 page languages", async () => {
    vi.resetModules();
    const { recognitionLang } = await import("../components/Dictation.jsx");
    const tags = {
      en: "en-US", es: "es-ES", fr: "fr-FR", hi: "hi-IN", vi: "vi-VN", ar: "ar-SA",
      tl: "tl-PH", ht: "ht-HT", zh: "zh-CN", ko: "ko-KR", pt: "pt-BR", ru: "ru-RU",
      so: "so-SO", ur: "ur-PK", bn: "bn-BD", pa: "pa-IN", fa: "fa-IR", am: "am-ET",
      my: "my-MM", ne: "ne-NP", sw: "sw-KE",
    };
    expect(Object.keys(tags)).toHaveLength(21);
    for (const [lng, tag] of Object.entries(tags)) {
      expect(recognitionLang(lng), lng).toBe(tag);
    }
  });
});
