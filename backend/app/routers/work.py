"""Work: job board, tracker, resume builder, interview coach, micro-gigs."""
import html
import re
import uuid
from datetime import datetime, timezone
from fastapi import Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field
from .. import ai_bank, crisis_reply, moderation, safety, tiers as tiers_lib
from ..deps import get_current_user
from ..providers import (INTERVIEW_QUESTIONS, RESUME_QUESTIONS, InterviewCoachProvider,
                         ProviderBadOutput, ProviderNotConfigured, ResumeWriterProvider)
from ..seed_data import JOBS
from ._stub import stub_router

router = stub_router("work", exclude={"job_board", "application_tracker", "resume_builder", "resume_ai_assist", "interview_coach", "micro_gigs"})
coach = InterviewCoachProvider()
resume_writer = ResumeWriterProvider()

class AppIn(BaseModel):
    job_id: str
    status: str = "applied"
class JobExp(BaseModel):
    title: str = ""
    company: str = ""
    summary: str = ""
class ResumeIn(BaseModel):
    full_name: str = Field(max_length=80)
    headline: str = ""
    summary: str = ""
    skills: list[str] = []
    experience: list[JobExp] = []
class ResumeAnswerIn(BaseModel):
    question_id: str
    answer: str = Field(default="", max_length=2000)
class ResumeGuidedIn(BaseModel):
    answers: list[ResumeAnswerIn] = Field(default=[], max_length=20)
    target_job: str | None = Field(default=None, max_length=120)
class ResumeImportIn(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
class AnswerIn(BaseModel):
    question_id: str
    answer: str = Field(min_length=1, max_length=3000)
class GigIn(BaseModel):
    title: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=1, max_length=2000)
    city: str = "Fort Worth"
    pay_note: str = "Pay discussed directly. Check parole conditions with your officer."
class GigApplyIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)

def render_resume(doc):
    lines = [doc.get("full_name", ""), doc.get("headline", ""), "", doc.get("summary", ""), "", "Skills: " + ", ".join(doc.get("skills", []))]
    for j in doc.get("experience", []):
        lines += ["", f"{j.get('title','')} — {j.get('company','')}", j.get("summary", "")]
    return "\n".join(lines)

@router.get("/job_board")
async def jobs(second_chance: bool | None = None, q: str | None = None):
    items = JOBS
    if second_chance is not None: items = [j for j in items if j["second_chance"] == second_chance]
    if q: items = [j for j in items if q.lower() in (j["title"] + j["company"]).lower()]
    return {"jobs": items, "note": "Check parole or probation conditions with your officer before applying."}
@router.get("/job_board/{job_id}")
async def job(job_id: str):
    for j in JOBS:
        if j["id"] == job_id: return j
    raise HTTPException(404, "job not found")
@router.post("/application_tracker", status_code=201)
async def track(body: AppIn, request: Request, user=Depends(get_current_user)):
    doc = {"_id": uuid.uuid4().hex, "user_id": user["_id"], "job_id": body.job_id, "status": body.status}
    await request.app.state.db.applications.insert_one(doc)
    return {k: v for k, v in doc.items()}
@router.get("/application_tracker")
async def list_apps(request: Request, user=Depends(get_current_user)):
    items = await request.app.state.db.applications.find({"user_id": user["_id"]}).to_list(100)
    return {"applications": [{k: v for k, v in d.items()} for d in items]}

async def _store_resume(request: Request, user, data: dict, extra: dict | None = None):
    """The one insert path for résumés — manual create and both AI paths use it."""
    doc = {"_id": uuid.uuid4().hex, "user_id": user["_id"], **data, "created_at": datetime.now(timezone.utc).isoformat()}
    if extra:
        doc.update(extra)
    doc["text"] = render_resume(doc)
    await request.app.state.db.resumes.insert_one(doc)
    return {k: v for k, v in doc.items()}


@router.post("/resume_builder", status_code=201)
async def create_resume(body: ResumeIn, request: Request, user=Depends(get_current_user)):
    return await _store_resume(request, user, body.model_dump())
@router.get("/resume_builder")
async def list_resumes(request: Request, user=Depends(get_current_user)):
    items = await request.app.state.db.resumes.find({"user_id": user["_id"]}).to_list(100)
    return {"resumes": [{k: v for k, v in d.items()} for d in items]}
@router.get("/resume_builder/{rid}")
async def get_resume(rid: str, request: Request, user=Depends(get_current_user)):
    d = await request.app.state.db.resumes.find_one({"_id": rid, "user_id": user["_id"]})
    if not d: raise HTTPException(404, "not found")
    return {k: v for k, v in d.items()}
@router.delete("/resume_builder/{rid}")
async def del_resume(rid: str, request: Request, user=Depends(get_current_user)):
    r = await request.app.state.db.resumes.delete_one({"_id": rid, "user_id": user["_id"]})
    if r.deleted_count == 0: raise HTTPException(404, "not found")
    return {"deleted": True}
@router.put("/resume_builder/{rid}")
async def update_resume(rid: str, body: ResumeIn, request: Request, user=Depends(get_current_user)):
    db = request.app.state.db
    existing = await db.resumes.find_one({"_id": rid, "user_id": user["_id"]})
    if not existing: raise HTTPException(404, "not found")
    updates = body.model_dump()
    updates["text"] = render_resume(updates)
    updates.pop("ai_draft", None)
    # A member save means a person has reviewed it: the AI-draft flag clears.
    await db.resumes.update_one({"_id": rid, "user_id": user["_id"]}, {"$set": updates, "$unset": {"ai_draft": ""}})
    d = await db.resumes.find_one({"_id": rid, "user_id": user["_id"]})
    return {k: v for k, v in d.items()}

def _resume_print_html(doc) -> str:
    esc = html.escape
    exp = "".join(
        f"<h2>{esc(j.get('title', ''))} — {esc(j.get('company', ''))}</h2><p>{esc(j.get('summary', ''))}</p>"
        for j in doc.get("experience", []))
    skills = ", ".join(esc(s) for s in doc.get("skills", []))
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>{esc(doc.get('full_name', 'Resume'))}</title>"
            "<style>body{font-family:Georgia,serif;max-width:700px;margin:40px auto;color:#111;line-height:1.45}"
            "h1{margin-bottom:0}h2{font-size:1.05em;margin-bottom:0}.headline{color:#444;margin-top:2px}"
            "@media print{body{margin:0}}</style></head><body>"
            f"<h1>{esc(doc.get('full_name', ''))}</h1>"
            f"<p class='headline'>{esc(doc.get('headline', ''))}</p>"
            f"<p>{esc(doc.get('summary', ''))}</p>"
            + (f"<p><strong>Skills:</strong> {skills}</p>" if skills else "")
            + exp + "</body></html>")

@router.get("/resume_builder/{rid}/print", response_class=HTMLResponse)
async def print_resume(rid: str, request: Request, user=Depends(get_current_user)):
    """Print-clean single template; the browser's print dialog saves it as PDF."""
    d = await request.app.state.db.resumes.find_one({"_id": rid, "user_id": user["_id"]})
    if not d: raise HTTPException(404, "not found")
    return HTMLResponse(_resume_print_html(d))

def _resume_pdf_bytes(doc) -> bytes:
    """Server-rendered PDF of the stored résumé — the same content the print
    view renders (name, headline, summary, skills, experience), one clean
    template, as a real file the member can download in one click."""
    from io import BytesIO
    from xml.sax.saxutils import escape
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate

    name_style = ParagraphStyle("resume-name", fontName="Times-Bold", fontSize=20, leading=24, spaceAfter=2)
    headline_style = ParagraphStyle("resume-headline", fontName="Times-Italic", fontSize=11.5, leading=15,
                                    textColor=HexColor("#444444"), spaceAfter=10)
    body_style = ParagraphStyle("resume-body", fontName="Times-Roman", fontSize=11.5, leading=16, spaceAfter=10)
    job_style = ParagraphStyle("resume-job", fontName="Times-Bold", fontSize=12, leading=16, spaceBefore=8, spaceAfter=2)

    def para(text, style):
        return Paragraph(escape(text or ""), style)

    story = [para(doc.get("full_name", ""), name_style)]
    if doc.get("headline"):
        story.append(para(doc["headline"], headline_style))
    if doc.get("summary"):
        story.append(para(doc["summary"], body_style))
    skills = [s for s in doc.get("skills", []) if s]
    if skills:
        story.append(Paragraph("<b>Skills:</b> " + escape(", ".join(skills)), body_style))
    for j in doc.get("experience", []):
        heading = " — ".join(x for x in [j.get("title", ""), j.get("company", "")] if x)
        if heading:
            story.append(para(heading, job_style))
        if j.get("summary"):
            story.append(para(j["summary"], body_style))

    buf = BytesIO()
    pdf = SimpleDocTemplate(buf, pagesize=letter,
                            leftMargin=0.9 * inch, rightMargin=0.9 * inch,
                            topMargin=0.9 * inch, bottomMargin=0.9 * inch,
                            title=doc.get("full_name") or "Resume",
                            author=doc.get("full_name") or "")
    pdf.build(story)
    return buf.getvalue()

def _pdf_filename(doc) -> str:
    """resume-<first-name>.pdf — the name is reduced to [A-Za-z0-9_-] so the
    header value can never break out of its quotes."""
    first = (doc.get("full_name") or "").strip().split(" ")[0]
    first = re.sub(r"[^A-Za-z0-9_-]+", "", first)
    return f"resume-{first}.pdf" if first else "resume.pdf"

@router.get("/resume_builder/{rid}/pdf")
async def download_resume_pdf(rid: str, request: Request, user=Depends(get_current_user)):
    """One-click PDF download of the stored résumé, owner-scoped like print."""
    d = await request.app.state.db.resumes.find_one({"_id": rid, "user_id": user["_id"]})
    if not d: raise HTTPException(404, "not found")
    return Response(content=_resume_pdf_bytes(d), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{_pdf_filename(d)}"'})

def _validate_resume_dict(d: dict):
    ResumeIn(**d)  # raises ValueError (pydantic) when the shape is wrong

NOT_CONFIGURED_COPY = "AI résumé help isn't set up on this server yet. You can still build a résumé yourself for free — that always works."

@router.get("/resume_builder/assist/questions")
async def resume_assist_questions(user=Depends(get_current_user)):
    return {"questions": [{"id": q["id"], "prompt": q["prompt"], "help": q["help"]} for q in RESUME_QUESTIONS],
            "provider": resume_writer.name if resume_writer.configured else "not_configured"}

async def _run_resume_assist(request: Request, user, path: str, make_draft, echo: dict):
    tiers_lib.require(user.get("tier", "free"), "resume_ai_assist")
    if not resume_writer.configured:
        return JSONResponse(status_code=503, content={"detail": NOT_CONFIGURED_COPY})
    db = request.app.state.db
    check, rid = await ai_bank.reserve(db, user["_id"], user.get("tier", "free"), path)
    if not check["ok"]:
        return JSONResponse(status_code=402, content={"detail": ai_bank.POOL_EMPTY_COPY,
                                                       "pool": {"pool_cents": check["pool_cents"], "used_cents": check["used_cents"]}})
    try:
        try:
            data, usages = make_draft()
        except ProviderNotConfigured:
            return JSONResponse(status_code=503, content={"detail": NOT_CONFIGURED_COPY})
        except ProviderBadOutput as e:
            for u in e.usages:
                await ai_bank.debit(db, user["_id"], path, u)
            return JSONResponse(status_code=502, content={"detail": "The AI couldn't write a clean draft from that. Nothing was saved — your words are right here, so you can try again or build it yourself for free.", **echo})
        for u in usages:
            await ai_bank.debit(db, user["_id"], path, u)
    finally:
        await ai_bank.release(db, rid)
    validated = ResumeIn(**data)
    return await _store_resume(request, user, validated.model_dump(),
                               extra={"source": "ai_guided" if path == "guided" else "ai_import", "ai_draft": True})

@router.post("/resume_builder/assist/generate", status_code=201)
async def resume_assist_generate(body: ResumeGuidedIn, request: Request, user=Depends(get_current_user)):
    echo = {"answers": [a.model_dump() for a in body.answers], "target_job": body.target_job}
    result = await _run_resume_assist(
        request, user, "guided",
        lambda: resume_writer.draft_from_answers([a.model_dump() for a in body.answers], body.target_job, _validate_resume_dict),
        echo)
    if isinstance(result, JSONResponse):
        return result
    return JSONResponse(status_code=201, content=result)

@router.post("/resume_builder/assist/import", status_code=201)
async def resume_assist_import(body: ResumeImportIn, request: Request, user=Depends(get_current_user)):
    result = await _run_resume_assist(
        request, user, "import",
        lambda: resume_writer.structure_pasted_text(body.text, _validate_resume_dict),
        {"text": body.text})
    if isinstance(result, JSONResponse):
        return result
    return JSONResponse(status_code=201, content=result)

@router.get("/interview_coach/questions")
async def questions(user=Depends(get_current_user)):
    return {"questions": [{"id": q["id"], "prompt": q["prompt"]} for q in INTERVIEW_QUESTIONS], "provider": coach.name}
@router.post("/interview_coach/sessions", status_code=201)
async def answer(body: AnswerIn, request: Request, user=Depends(get_current_user)):
    if body.question_id not in {q["id"] for q in INTERVIEW_QUESTIONS}: raise HTTPException(404, "unknown question")
    result = coach.score(body.question_id, body.answer)
    doc = {"_id": uuid.uuid4().hex, "user_id": user["_id"], "question_id": body.question_id, "answer": body.answer, **result, "created_at": datetime.now(timezone.utc).isoformat()}
    await request.app.state.db.interview_sessions.insert_one(doc)
    return {k: v for k, v in doc.items()}
@router.get("/interview_coach/sessions")
async def sessions(request: Request, user=Depends(get_current_user)):
    items = await request.app.state.db.interview_sessions.find({"user_id": user["_id"]}).to_list(100)
    return {"sessions": [{k: v for k, v in d.items()} for d in items]}

@router.post("/micro_gigs", status_code=201)
async def create_gig(body: GigIn, request: Request, user=Depends(get_current_user)):
    mod = moderation.moderate_public(body.title + " " + body.description)
    _crisis = await crisis_reply.deliver(request.app.state.db, user["_id"], body.title + " " + body.description)
    if mod["decision"] == "remove": raise HTTPException(422, mod["reply"])
    status = "held" if mod["decision"] == "hold" else "published"
    doc = {"_id": uuid.uuid4().hex, "user_id": user["_id"], "author_handle": user.get("handle"), **body.model_dump(), "status": status, "moderation": mod, "created_at": datetime.now(timezone.utc).isoformat()}
    await request.app.state.db.micro_gigs.insert_one(doc)
    out = {k: v for k, v in doc.items() if k not in ("user_id",)}
    out["author"] = safety.public_member(user)
    return out
@router.get("/micro_gigs")
async def list_gigs(request: Request, user=Depends(get_current_user)):
    items = await request.app.state.db.micro_gigs.find({"status": "published"}).to_list(100)
    out = []
    for d in items:
        x = {k: v for k, v in d.items()}
        x.pop("user_id", None)
        out.append(x)
    return {"gigs": out, "note": "Check parole or probation conditions with your officer. Phone numbers are never shown."}
@router.post("/micro_gigs/{gid}/apply", status_code=201)
async def apply_gig(gid: str, body: GigApplyIn, request: Request, user=Depends(get_current_user)):
    gig = await request.app.state.db.micro_gigs.find_one({"_id": gid, "status": "published"})
    if not gig: raise HTTPException(404, "gig not found")
    mod = moderation.moderate_public(body.message)
    _crisis = await crisis_reply.deliver(request.app.state.db, user["_id"], body.message)
    if mod["decision"] == "remove": raise HTTPException(422, mod["reply"])
    doc = {"_id": uuid.uuid4().hex, "user_id": user["_id"], "gig_id": gid, "message": body.message, "moderation": mod}
    await request.app.state.db.gig_applications.insert_one(doc)
    return {"id": doc["_id"], "gig_id": gid, "applicant": safety.public_member(user)}
