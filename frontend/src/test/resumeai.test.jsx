import { describe, expect, it, vi, afterEach, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

// Same SpeechRecognition stub pattern as dictation.test.jsx: the Dictation
// component reads window.SpeechRecognition at module load, so stub it BEFORE
// importing the page, with a fresh module registry per test.
class FakeRecognition {
  static instances = [];
  constructor() { this.lang = ""; FakeRecognition.instances.push(this); }
  start() { this.started = true; }
  stop() { this.stopped = true; if (this.onend) this.onend(); }
  abort() { if (this.onend) this.onend(); }
}

const QUESTIONS = [
  { id: "name", prompt: "What is your full name?", help: "Use the name you want an employer to see." },
  { id: "work_history", prompt: "Tell me about the jobs you have had.", help: "Paid jobs of any kind count." },
];
const DRAFT = { _id: "r1", full_name: "Alex Ray", headline: "Warehouse worker", summary: "Reliable.",
  skills: ["forklift"], experience: [], text: "Alex Ray\nWarehouse worker", source: "ai_guided", ai_draft: true };

let generateResponder = null;

function respond(body, status = 200) {
  return { ok: status < 300, status, json: async () => body, blob: async () => new Blob([""]) };
}

beforeEach(() => {
  generateResponder = null;
  global.fetch = vi.fn(async (url, opts = {}) => {
    const method = opts.method || "GET";
    if (url.includes("/assist/questions")) return respond({ questions: QUESTIONS, provider: "meta-model-api" });
    if (url.includes("/assist/generate") && method === "POST") return generateResponder();
    if (url.includes("/assist/import") && method === "POST") return generateResponder();
    if (url.includes("/resume_builder") && method === "GET") return respond({ resumes: [] });
    if (url.includes("/job_board")) return respond({ jobs: [] });
    if (url.includes("/application_tracker")) return respond({ applications: [] });
    if (url.includes("/micro_gigs")) return respond({ gigs: [] });
    return respond({});
  });
});

afterEach(() => {
  delete window.SpeechRecognition;
  FakeRecognition.instances = [];
  localStorage.clear();
  vi.restoreAllMocks();
});

async function importWorkPage() {
  vi.resetModules();
  await import("../i18n");
  const mod = await import("../pages/WorkPage.jsx");
  return mod.default;
}

describe("AI resume assist on the work page", () => {
  it("shows both entry cards above the blank builder", async () => {
    window.SpeechRecognition = FakeRecognition;
    const WorkPage = await importWorkPage();
    render(<WorkPage />);
    expect(screen.getByTestId("resume-ai-section")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Talk it through" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Paste an old resume" })).toBeInTheDocument();
  });

  it("guided view renders the questions, each with a dictate control", async () => {
    window.SpeechRecognition = FakeRecognition;
    const WorkPage = await importWorkPage();
    render(<WorkPage />);
    fireEvent.click(screen.getByRole("button", { name: "Talk it through" }));
    await waitFor(() => expect(screen.getByLabelText("What is your full name?")).toBeInTheDocument());
    expect(screen.getByLabelText("Tell me about the jobs you have had.")).toBeInTheDocument();
    // one DictateButton per question field (its label is the dictation "Talk" string)
    expect(screen.getAllByRole("button", { name: "Talk" }).length).toBe(QUESTIONS.length);
  });

  it("import view renders the paste box with a dictate control", async () => {
    window.SpeechRecognition = FakeRecognition;
    const WorkPage = await importWorkPage();
    render(<WorkPage />);
    fireEvent.click(screen.getByRole("button", { name: "Paste an old resume" }));
    await waitFor(() => expect(screen.getByTestId("resume-ai-import")).toBeInTheDocument());
    expect(screen.getByPlaceholderText("Paste your old resume here…")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Talk" }).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Clean up my resume" })).toBeInTheDocument();
  });

  it("pool-empty renders the API's honest pause message", async () => {
    window.SpeechRecognition = FakeRecognition;
    generateResponder = () => respond({ detail: "You've used this month's AI help for résumé writing. You can still build or edit a résumé yourself for free.", pool: { pool_cents: 13, used_cents: 13 } }, 402);
    const WorkPage = await importWorkPage();
    render(<WorkPage />);
    fireEvent.click(screen.getByRole("button", { name: "Talk it through" }));
    await waitFor(() => expect(screen.getByLabelText("What is your full name?")).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText("What is your full name?"), { target: { value: "Alex Ray" } });
    fireEvent.click(screen.getByRole("button", { name: "Write my resume" }));
    await waitFor(() => expect(screen.getByText(/used this month's AI help/)).toBeInTheDocument());
  });

  it("a created draft shows the AI-draft banner", async () => {
    window.SpeechRecognition = FakeRecognition;
    generateResponder = () => respond(DRAFT, 201);
    const WorkPage = await importWorkPage();
    render(<WorkPage />);
    fireEvent.click(screen.getByRole("button", { name: "Talk it through" }));
    await waitFor(() => expect(screen.getByLabelText("What is your full name?")).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText("What is your full name?"), { target: { value: "Alex Ray" } });
    fireEvent.click(screen.getByRole("button", { name: "Write my resume" }));
    await waitFor(() => expect(screen.getByText("AI draft — check it over, change anything that isn't right")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Print / save as PDF" })).toBeInTheDocument();
  });

  it("download PDF fetches the pdf endpoint with auth and saves the file", async () => {
    window.SpeechRecognition = FakeRecognition;
    URL.createObjectURL = vi.fn(() => "blob:resume-pdf");
    URL.revokeObjectURL = vi.fn();
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
    generateResponder = () => respond(DRAFT, 201);
    const WorkPage = await importWorkPage();
    render(<WorkPage />);
    fireEvent.click(screen.getByRole("button", { name: "Talk it through" }));
    await waitFor(() => expect(screen.getByLabelText("What is your full name?")).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText("What is your full name?"), { target: { value: "Alex Ray" } });
    fireEvent.click(screen.getByRole("button", { name: "Write my resume" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Download PDF" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Download PDF" }));
    await waitFor(() => expect(clickSpy).toHaveBeenCalled());
    const pdfCall = global.fetch.mock.calls.find(([url]) => String(url).includes("/resume_builder/r1/pdf"));
    expect(pdfCall).toBeTruthy();
    expect(pdfCall[1].headers.Authorization).toContain("Bearer");
    delete URL.createObjectURL;
    delete URL.revokeObjectURL;
  });
});
