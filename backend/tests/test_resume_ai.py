"""AI résumé assist (owner-approved 2026-11-01): provider honesty, metering,
anti-fabrication, and the draft flow. The model is stubbed at the transport —
no real API calls ever happen in tests."""
import asyncio
import json

import pytest

from app import ai_bank
from app.providers import (ProviderBadOutput, ProviderNotConfigured,
                           ResumeWriterProvider)
from app.routers import work as work_router
from app.routers.work import ResumeIn


def reg(client, handle="alex", tier="paid"):
    r = client.post("/api/auth/register", json={"handle": handle, "password": "password123", "tier": tier, "phone": "817-555-0100"})
    assert r.status_code == 201, r.text
    return r.json()


def auth(tok):
    return {"Authorization": f"Bearer {tok}"}


def uid_of(db, handle):
    return asyncio.run(db.users.find_one({"handle": handle}))["_id"]


def validate(d):
    ResumeIn(**d)


GOOD = {"full_name": "Alex Ray", "headline": "Warehouse worker", "summary": "Reliable worker.",
        "skills": ["forklift"], "experience": [{"title": "Picker", "company": "BigMart", "summary": "Picked orders."}]}


def stub_writer(calls, replies):
    """A ResumeWriterProvider whose transport replays `replies` (content strings)
    and records every call. Usage is fixed at 2500 in / 1200 out (~1c)."""
    def transport(messages, max_tokens):
        calls.append(messages)
        content = replies[min(len(calls) - 1, len(replies) - 1)]
        return content, {"input_tokens": 2500, "output_tokens": 1200}
    return ResumeWriterProvider(api_key="test-key", transport=transport)


@pytest.fixture
def writer(monkeypatch):
    calls = []
    w = stub_writer(calls, [json.dumps(GOOD)])
    monkeypatch.setattr(work_router, "resume_writer", w)
    return calls


# ---- provider unit tests ----

def test_provider_guided_answers_to_valid_resume():
    calls = []
    w = stub_writer(calls, [json.dumps(GOOD)])
    data, usages = w.draft_from_answers(
        [{"question_id": "name", "answer": "Alex Ray"},
         {"question_id": "work_history", "answer": "Picker at BigMart"}], "warehouse", validate)
    assert data == GOOD
    assert usages == [{"input_tokens": 2500, "output_tokens": 1200}]
    assert len(calls) == 1  # exactly ONE call per draft


def test_provider_import_structures_paste():
    calls = []
    w = stub_writer(calls, [json.dumps(GOOD)])
    data, usages = w.structure_pasted_text("Alex Ray — picker at BigMart...", validate)
    assert data["full_name"] == "Alex Ray" and len(usages) == 1 and len(calls) == 1


def test_provider_not_configured_never_fakes():
    w = ResumeWriterProvider(api_key="")
    assert w.configured is False
    with pytest.raises(ProviderNotConfigured):
        w.draft_from_answers([{"question_id": "name", "answer": "Alex"}], None, validate)


def test_provider_repair_retry_then_bad_output():
    calls = []
    w = stub_writer(calls, ["not json", "still not json"])
    with pytest.raises(ProviderBadOutput) as e:
        w.draft_from_answers([{"question_id": "name", "answer": "Alex"}], None, validate)
    assert len(calls) == 2  # one attempt + exactly one repair
    assert len(e.value.usages) == 2


def test_anti_fabrication_fixture():
    # The stub returns only facts present in the fixture input; the prompt the
    # provider sends must carry the anti-fabrication rules, and the validated
    # output must contain no employer that was not in the member's answers.
    calls = []
    w = stub_writer(calls, [json.dumps(GOOD)])
    data, _ = w.draft_from_answers(
        [{"question_id": "work_history", "answer": "Picker at BigMart for two years"}], None, validate)
    system = calls[0][0]["content"]
    assert "Never invent employers" in system and "Gaps stay gaps" in system
    companies = {j["company"] for j in data["experience"]}
    assert companies <= {"BigMart"}


# ---- metering unit tests ----

def test_cost_math_rounding_and_floor():
    assert ai_bank.cost_cents(0, 0) == 1            # 1c minimum per call
    assert ai_bank.cost_cents(2500, 1200) == 1      # 0.3125c + 0.51c = 0.8225c -> 1c
    assert ai_bank.cost_cents(8000, 8000) == 5      # 1.0c + 3.4c = 4.4c -> 5c (rounded up)
    assert ai_bank.pool_cents_for("paid") == 13     # owner's entry pool governs until he sets a tier slot


# ---- endpoint tests ----

def test_questions_endpoint_reports_provider_state(client, writer):
    u = reg(client)
    r = client.get("/api/work/resume_builder/assist/questions", headers=auth(u["token"]))
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "meta-model-api"
    assert any(q["id"] == "informal_work" for q in body["questions"])


def test_generate_creates_ai_draft(client, writer, db):
    u = reg(client)
    r = client.post("/api/work/resume_builder/assist/generate",
                    json={"answers": [{"question_id": "name", "answer": "Alex Ray"}], "target_job": "warehouse"},
                    headers=auth(u["token"]))
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["source"] == "ai_guided" and doc["ai_draft"] is True
    assert doc["full_name"] == "Alex Ray" and "BigMart" in doc["text"]
    used = asyncio.run(ai_bank.used_this_month_cents(db, uid_of(db, "alex")))
    assert used == 1  # one call debited at actual usage


def test_import_creates_ai_draft(client, writer):
    u = reg(client)
    r = client.post("/api/work/resume_builder/assist/import",
                    json={"text": "Alex Ray, picker at BigMart"}, headers=auth(u["token"]))
    assert r.status_code == 201, r.text
    assert r.json()["source"] == "ai_import" and r.json()["ai_draft"] is True


def test_feature_tier_is_unassigned_so_no_tier_is_invented(client, writer):
    # The owner has not assigned a tier to resume_ai_assist, so it is open to
    # every tier during the scaffold; spend is still bounded by the ai_bank
    # pool, and the whole feature is off until GW_META_MODEL_API_KEY is set.
    from app import registry
    assert registry.get("resume_ai_assist").tier == "unassigned"
    u = reg(client, handle="freeuser", tier="free")
    r = client.post("/api/work/resume_builder/assist/generate",
                    json={"answers": [{"question_id": "name", "answer": "Sam"}]}, headers=auth(u["token"]))
    assert r.status_code != 402 or "month" in r.json()["detail"]


def test_pool_empty_blocks_with_zero_model_calls(client, writer, db, monkeypatch):
    u = reg(client)
    monkeypatch.setattr(ai_bank, "ENTRY_POOL_CENTS", 1)  # worst case (2c) no longer fits
    r = client.post("/api/work/resume_builder/assist/generate",
                    json={"answers": [{"question_id": "name", "answer": "Alex Ray"}]}, headers=auth(u["token"]))
    assert r.status_code == 402
    body = r.json()
    assert body["pool"] == {"pool_cents": 1, "used_cents": 0}
    assert "still build or edit" in body["detail"]  # honest pause copy: manual builder stays free
    assert writer == []  # pre-flight blocked BEFORE any call


def test_not_configured_503_and_no_ledger_writes(client, monkeypatch, db):
    monkeypatch.setattr(work_router, "resume_writer", ResumeWriterProvider(api_key=""))
    u = reg(client)
    r = client.post("/api/work/resume_builder/assist/generate",
                    json={"answers": [{"question_id": "name", "answer": "Alex Ray"}]}, headers=auth(u["token"]))
    assert r.status_code == 503
    assert "isn't set up" in r.json()["detail"]
    assert asyncio.run(db.ai_usage.count_documents({})) == 0
    assert asyncio.run(db.resumes.count_documents({})) == 0


def test_double_invalid_json_502_echoes_answers_and_debits_both_calls(client, monkeypatch, db):
    calls = []
    monkeypatch.setattr(work_router, "resume_writer", stub_writer(calls, ["nope", "nope again"]))
    u = reg(client)
    answers = [{"question_id": "name", "answer": "Alex Ray"}]
    r = client.post("/api/work/resume_builder/assist/generate",
                    json={"answers": answers}, headers=auth(u["token"]))
    assert r.status_code == 502
    assert r.json()["answers"] == answers  # nothing the member typed is lost
    assert asyncio.run(db.resumes.count_documents({})) == 0
    assert asyncio.run(ai_bank.used_this_month_cents(db, uid_of(db, "alex"))) == 2  # both real calls debited


def test_member_save_via_put_clears_ai_draft(client, writer):
    u = reg(client)
    r = client.post("/api/work/resume_builder/assist/generate",
                    json={"answers": [{"question_id": "name", "answer": "Alex Ray"}]}, headers=auth(u["token"]))
    rid = r.json()["_id"]
    body = {"full_name": "Alex Ray", "headline": "Warehouse worker", "summary": "Edited by me.",
            "skills": ["forklift"], "experience": [{"title": "Picker", "company": "BigMart", "summary": "Picked orders."}]}
    r2 = client.put(f"/api/work/resume_builder/{rid}", json=body, headers=auth(u["token"]))
    assert r2.status_code == 200, r2.text
    assert "ai_draft" not in r2.json() and r2.json()["summary"] == "Edited by me."
    # owner-scoped: another member cannot touch it
    other = reg(client, handle="other")
    assert client.put(f"/api/work/resume_builder/{rid}", json=body, headers=auth(other["token"])).status_code == 404


def test_print_export_serves_stored_resume(client, writer):
    u = reg(client)
    r = client.post("/api/work/resume_builder", json={"full_name": "Alex Ray", "headline": "Warehouse worker",
                    "summary": "Reliable.", "skills": ["forklift"],
                    "experience": [{"title": "Picker", "company": "BigMart", "summary": "Picked orders."}]},
                    headers=auth(u["token"]))
    rid = r.json()["_id"]
    page = client.get(f"/api/work/resume_builder/{rid}/print", headers=auth(u["token"]))
    assert page.status_code == 200 and "text/html" in page.headers["content-type"]
    assert "Alex Ray" in page.text and "BigMart" in page.text and "@media print" in page.text
    other = reg(client, handle="other2")
    assert client.get(f"/api/work/resume_builder/{rid}/print", headers=auth(other["token"])).status_code == 404


def test_pdf_export_downloads_a_real_pdf(client):
    u = reg(client)
    r = client.post("/api/work/resume_builder", json={"full_name": "Alex Ray", "headline": "Warehouse worker",
                    "summary": "Reliable.", "skills": ["forklift"],
                    "experience": [{"title": "Picker", "company": "BigMart", "summary": "Picked orders."}]},
                    headers=auth(u["token"]))
    rid = r.json()["_id"]
    pdf = client.get(f"/api/work/resume_builder/{rid}/pdf", headers=auth(u["token"]))
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content.startswith(b"%PDF") and len(pdf.content) > 500
    cd = pdf.headers["content-disposition"]
    assert "attachment" in cd and 'filename="resume-Alex.pdf"' in cd
    # owner-scoped exactly like print: another member gets the 404, and a
    # missing résumé is a 404 too
    other = reg(client, handle="other3")
    assert client.get(f"/api/work/resume_builder/{rid}/pdf", headers=auth(other["token"])).status_code == 404
    assert client.get("/api/work/resume_builder/nope/pdf", headers=auth(u["token"])).status_code == 404


def test_pdf_filename_is_sanitized():
    from app.routers.work import _pdf_filename
    assert _pdf_filename({"full_name": "Alex Ray"}) == "resume-Alex.pdf"
    assert _pdf_filename({"full_name": "  Mary-Jane O'Brien"}) == "resume-Mary-Jane.pdf"
    assert _pdf_filename({"full_name": "Al/ex \"Q\" Ray"}) == "resume-Alex.pdf"
    assert _pdf_filename({"full_name": "!!!"}) == "resume.pdf"
    assert _pdf_filename({"full_name": ""}) == "resume.pdf"
    assert _pdf_filename({}) == "resume.pdf"


def test_concurrent_calls_cannot_exceed_pool():
    import asyncio
    from mongomock_motor import AsyncMongoMockClient
    from app import ai_bank

    async def run():
        db = AsyncMongoMockClient()["gw_bank_race"]
        results = await asyncio.gather(*[ai_bank.reserve(db, "u1", "paid", "guided") for _ in range(20)])
        return sum(1 for check, rid in results if rid)

    assert run_sync(run()) == ai_bank.ENTRY_POOL_CENTS // ai_bank.WORST_CASE_CENTS["guided"]


def run_sync(coro):
    import asyncio
    return asyncio.run(coro)
