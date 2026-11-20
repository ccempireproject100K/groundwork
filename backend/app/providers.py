"""Pluggable local providers. No external APIs or keys. Swap class to use a real provider later.

One exception, added 2026-11-01: ResumeWriterProvider (bottom of this file)
calls the Meta Model API when its key is configured, and refuses honestly
when it is not — it never falls back to a deterministic fake.
"""
import json
import os
from dataclasses import dataclass

INTERVIEW_QUESTIONS = [
    {"id": "q1", "prompt": "Tell me about a time you solved a problem at work.", "keywords": ["example", "learned", "result", "helped", "finished"]},
    {"id": "q2", "prompt": "How do you handle a disagreement with a coworker?", "keywords": ["listen", "calm", "talk", "respect", "solution"]},
    {"id": "q3", "prompt": "Why should we hire you for this role?", "keywords": ["reliable", "safety", "team", "show up", "learn"]},
]

class InterviewCoachProvider:
    name = "deterministic-local-v1"
    def score(self, question_id: str, answer: str) -> dict:
        q = next((x for x in INTERVIEW_QUESTIONS if x["id"] == question_id), INTERVIEW_QUESTIONS[0])
        low = (answer or "").lower()
        hits = [k for k in q["keywords"] if k in low]
        length_bonus = 20 if len(answer or "") >= 120 else 10 if len(answer or "") >= 50 else 0
        score = min(100, 30 + len(hits) * 12 + length_bonus)
        tips = []
        if len(hits) < 2: tips.append("Add a concrete example and what you learned.")
        if len(answer or "") < 50: tips.append("Say a little more: situation, action, result.")
        if not tips: tips.append("Strong answer. Keep that example ready.")
        return {"score": score, "matched": hits, "tips": tips, "provider": self.name}

@dataclass
class MatcherAgent:
    """Deterministic fake behind the negotiation interface (ai-matcher skill)."""
    name: str = "deterministic-local-v1"
    def negotiate(self, brief_a: dict, brief_b: dict) -> dict:
        a_int = set(x.lower() for x in brief_a.get("interests", []))
        b_int = set(x.lower() for x in brief_b.get("interests", []))
        shared = sorted(a_int & b_int)
        # Dealbreakers are checked against the OTHER brief's disclosed attributes, from A's side only here.
        b_attrs = {str(v).lower() for v in brief_b.get("attributes", {}).values()}
        a_attrs = {str(v).lower() for v in brief_a.get("attributes", {}).values()}
        a_blocks = [d for d in brief_a.get("dealbreakers", []) if d.lower() in b_attrs]
        b_blocks = [d for d in brief_b.get("dealbreakers", []) if d.lower() in a_attrs]
        score = min(100, 40 + len(shared) * 15)
        if a_blocks or b_blocks:
            return {"fit": "reject", "score": score, "shared": shared, "a_blocks": a_blocks, "b_blocks": b_blocks, "provider": self.name}
        if score < 55:
            return {"fit": "reject", "score": score, "shared": shared, "a_blocks": [], "b_blocks": [], "provider": self.name}
        return {"fit": "accept", "score": score, "shared": shared, "a_blocks": [], "b_blocks": [], "provider": self.name}

COURSES = [
    {"id": "parole_navigation", "title": "Parole navigation (DRAFT — for Brann's review)", "draft": True, "modules": [
        {"id": "pn1", "title": "Know your conditions", "objective": "List three of your supervision conditions.", "content": "General information only. Always check your specific conditions with your officer.", "quiz": [{"prompt": "Who confirms your specific conditions?", "options": ["Your officer", "A coworker", "Social media", "No one"], "answer": 0}]},
        {"id": "pn2", "title": "Check-ins and calendars", "objective": "Put every check-in on a calendar.", "content": "Write down dates the day you get them.", "quiz": [{"prompt": "When should you record a check-in date?", "options": ["Next month", "The day you get it", "Never", "After it passes"], "answer": 1}]}]},
    {"id": "job_interviews", "title": "Job interviews (DRAFT — for Brann's review)", "draft": True, "modules": [
        {"id": "ji1", "title": "Tell your story briefly", "objective": "Practice a 60-second introduction.", "content": "Focus on skills, reliability, and what you can do now.", "quiz": [{"prompt": "A good intro focuses on?", "options": ["Skills you bring now", "Blaming others", "Case details", "Pay first"], "answer": 0}]}]},
    {"id": "relapse_prevention", "title": "Relapse prevention (DRAFT — for Brann's review)", "draft": True, "modules": [
        {"id": "rp1", "title": "Know your triggers", "objective": "Name three personal triggers and one plan for each.", "content": "Draft for peer-specialist review. Not clinical advice. If you're in crisis, call or text 988. Emergency: 911.", "quiz": [{"prompt": "If you're in crisis, what number do you call or text?", "options": ["988", "411", "0", "211"], "answer": 0}]}]},
    {"id": "small_business", "title": "Starting a small business (DRAFT — for Brann's review)", "draft": True, "modules": [
        {"id": "sb1", "title": "Check conditions first", "objective": "Check whether self-employment fits your supervision conditions.", "content": "Some conditions restrict self-employment. Check with your officer first.", "quiz": [{"prompt": "Before starting, check self-employment with?", "options": ["Your officer", "A customer", "No one", "A bank only"], "answer": 0}]}]},
]

# ---------------------------------------------------------------------------
# AI résumé assist (owner-approved 2026-11-01; spec §5 of
# ~/workspace/buildout/ai-resume-builder/REPORT.md).
#
# Two input paths, one metered model call each:
#   A) Talk it through — RESUME_QUESTIONS, a deterministic script (zero LLM
#      calls to collect answers).
#   B) Paste an old résumé — the model structures and tidies ONLY.
# Both return a dict shaped exactly like the work router's ResumeIn model.
# ---------------------------------------------------------------------------

RESUME_QUESTIONS = [
    {"id": "name", "prompt": "What is your full name, the way you want it at the top of your résumé?", "help": "Use the name you want an employer to see."},
    {"id": "target_job", "prompt": "What kind of job are you looking for?", "help": "For example: warehouse work, cooking, driving, cleaning, construction help."},
    {"id": "work_history", "prompt": "Tell me about the jobs you have had. Where did you work, and what was your job there?", "help": "One job at a time is fine. Paid jobs of any kind count."},
    {"id": "day_to_day", "prompt": "At those jobs, what did you actually do day to day?", "help": "The real tasks: what your hands did, what tools you used, who you helped."},
    {"id": "informal_work", "prompt": "Have you done work that was not a regular job — family business, side jobs, volunteering, work assignments inside, or taking care of family?", "help": "That work counts. Say what you did, just like a job."},
    {"id": "skills", "prompt": "What skills, tools, or machines do you know how to use?", "help": "Anything an employer would care about: forklift, cooking, cleaning, fixing things, computers, driving."},
    {"id": "certifications", "prompt": "Do you have any licenses or certificates? Expired ones count too — just say they are expired.", "help": "For example: driver's license, food handler card, forklift certificate, GED classes."},
    {"id": "education", "prompt": "What schooling or classes have you finished?", "help": "School, GED, classes inside, training programs — whatever you have."},
    {"id": "availability", "prompt": "Is there anything about when or where you can work that an employer should know?", "help": "Only if you want it on the résumé. You can leave this blank."},
]

RESUME_SYSTEM_PROMPT = """You write résumés for people re-entering the workforce. Follow these rules without exception:

1. Use ONLY what the member gave you. Never invent employers, job titles, dates, metrics, certifications, or skills that are not in their answers. Gaps stay gaps — omit, never fill.
2. Turn task descriptions into plain, honest résumé bullets in the member's own register; translate informal work into standard job language WITHOUT upgrading the facts ("helped my uncle's crew pour driveways" becomes concrete-laying laborer duties, not "concrete foreman").
3. Plain language throughout. No corporate filler — phrases like "results-driven synergist" are banned. Write at a reading level a busy hiring manager can skim in seconds.
4. Output ONLY a JSON object with exactly these fields: {"full_name": string, "headline": string, "summary": string, "skills": [string], "experience": [{"title": string, "company": string, "summary": string}]}. No prose, no markdown fences, nothing else. Use "" or [] where the member gave you nothing."""

RESUME_IMPORT_SYSTEM_PROMPT = RESUME_SYSTEM_PROMPT + """

This member pasted an old résumé. Your job is structure and tidy ONLY: preserve every fact from the paste, organize the same facts into the JSON fields, clean up formatting, and lightly polish wording for clarity. No embellishment and no new facts. Where the paste conflicts with itself, keep the more specific version. Never "fix" a date or a title into something else."""

class ProviderNotConfigured(Exception):
    """No model key is configured. The feature answers honestly, never fakes it."""

class ProviderBadOutput(Exception):
    """The model failed to produce a valid résumé after one repair retry.
    Carries the usage of every call actually made, so the endpoint can debit
    exactly those calls and nothing more."""
    def __init__(self, usages: list[dict]):
        super().__init__("model did not return a valid résumé")
        self.usages = usages

class ResumeWriterProvider:
    """One metered Muse Spark call per résumé draft (empire Meta Model API
    pattern: server-side key from env, hard per-call budget cap)."""

    name = "meta-model-api"
    model = "muse-spark-1.3"
    api_url = "https://api.meta.ai/v1/chat/completions"
    per_call_max_usd = 0.05  # hard cap; a capped call's worst case is ~1.5c
    guided_max_tokens = 1500
    import_max_tokens = 2000

    def __init__(self, api_key: str | None = None, transport=None):
        self._api_key = api_key if api_key is not None else os.environ.get("GW_META_MODEL_API_KEY", "")
        self._api_url = os.environ.get("GW_META_MODEL_API_URL", self.api_url)
        self._transport = transport  # tests inject a stub: (messages, max_tokens) -> (content, usage)

    @property
    def configured(self) -> bool:
        return bool(self._api_key) or self._transport is not None

    def _call(self, messages: list[dict], max_tokens: int) -> tuple[str, dict]:
        if self._transport is not None:
            return self._transport(messages, max_tokens)
        if not self._api_key:
            raise ProviderNotConfigured("GW_META_MODEL_API_KEY is not set")
        # Budget-cap projection, like the empire bots' helper: refuse before
        # spending when the projected worst case exceeds the per-call cap.
        est_input = sum(len(m.get("content", "")) for m in messages) // 4
        projected = est_input * (1.25 / 1_000_000) + max_tokens * (4.25 / 1_000_000)
        if projected > self.per_call_max_usd:
            raise ProviderBadOutput([])
        import httpx
        resp = httpx.post(
            self._api_url,
            headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
            json={"model": self.model, "messages": messages, "max_tokens": max_tokens},
            timeout=240,
        )
        resp.raise_for_status()
        data = resp.json()
        usage = data.get("usage", {})
        return data["choices"][0]["message"]["content"], {
            "input_tokens": int(usage.get("prompt_tokens", 0)),
            "output_tokens": int(usage.get("completion_tokens", 0)),
        }

    @staticmethod
    def _parse(content: str, validate) -> dict:
        try:
            parsed = json.loads((content or "").strip())
        except Exception as e:
            raise ValueError(f"model output was not valid JSON: {e}") from e
        if not isinstance(parsed, dict):
            raise ValueError("model output was not a JSON object")
        validate(parsed)  # raises ValueError when the shape is wrong
        return parsed

    def _generate(self, system: str, user_text: str, max_tokens: int, validate) -> tuple[dict, list[dict]]:
        if not self.configured:
            raise ProviderNotConfigured("GW_META_MODEL_API_KEY is not set")
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user_text}]
        usages: list[dict] = []
        try:
            content, usage = self._call(messages, max_tokens)
        except (ProviderBadOutput, ProviderNotConfigured):
            raise
        except Exception:
            # Transport failure (timeout / 5xx / malformed reply): no usage was
            # reported, so nothing is debited; the endpoint answers 502 and
            # echoes the member's input back (spec §5.3 failure honesty).
            raise ProviderBadOutput(usages) from None
        usages.append(usage)
        try:
            return self._parse(content, validate), usages
        except ValueError as e:
            repair = messages + [
                {"role": "assistant", "content": content},
                {"role": "user", "content": f"That reply was not usable: {e}. Reply again with ONLY the JSON object, following every rule."},
            ]
            try:
                content2, usage2 = self._call(repair, max_tokens)
            except (ProviderBadOutput, ProviderNotConfigured):
                raise
            except Exception:
                raise ProviderBadOutput(usages) from None
            usages.append(usage2)
            try:
                return self._parse(content2, validate), usages
            except ValueError:
                raise ProviderBadOutput(usages) from None

    def draft_from_answers(self, answers: list[dict], target_job: str | None, validate) -> tuple[dict, list[dict]]:
        prompts = {q["id"]: q["prompt"] for q in RESUME_QUESTIONS}
        lines = []
        if target_job:
            lines.append(f"Target job: {target_job}")
        for a in answers:
            answer = (a.get("answer") or "")[:2000].strip()
            if not answer:
                continue
            lines.append(f"Q: {prompts.get(a.get('question_id'), a.get('question_id'))}\nA: {answer}")
        return self._generate(RESUME_SYSTEM_PROMPT, "\n\n".join(lines), self.guided_max_tokens, validate)

    def structure_pasted_text(self, text: str, validate) -> tuple[dict, list[dict]]:
        return self._generate(RESUME_IMPORT_SYSTEM_PROMPT, (text or "")[:20000], self.import_max_tokens, validate)
