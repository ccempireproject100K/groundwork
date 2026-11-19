# Groundwork (working name)

A reentry and recovery social app: one community, one feed and one identity, for people coming home from incarceration and people in substance-use recovery (including people who were never incarcerated).

> The name is a placeholder. Finalists are Groundwork and Commissary Club ("Refresh" is taken). Rename by changing `backend/app/config.py` (`DEFAULT_APP_NAME`, or env `GW_APP_NAME`) and `frontend/src/brand.js` (or env `VITE_APP_NAME`).

**Status: scaffold.** All 45 features are registered as stubs. The working parts are:
- health, features and plans endpoints
- the crisis endpoint and the crisis button on every screen
- the lock and filter policy
- anonymity and phone-number redaction helpers
- vault envelope encryption
- real-delete wipe
- the i18n shell with 8 locales (Arabic RTL)

## Run
```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
GW_JWT_SECRET=$(python3 -c 'import secrets;print(secrets.token_hex(32))') .venv/bin/uvicorn app.main:create_app --factory --reload
cd ../frontend && npm install && npx vitest run && npm run dev
```

## Optional features that are off by default
- **AI resume assist** (talk it through, or paste an old resume; the draft is always reviewed by the member): refuses with a plain 503 until the env var `GW_META_MODEL_API_KEY` is set (optional `GW_META_MODEL_API_URL`). No paid API call is ever made without it; with it, every call is metered per member per month by `backend/app/ai_bank.py`. The owner has not approved this spending, so leave the key unset. Building a resume by hand never depends on it.
- **Federated sign-in** (Google, Facebook, Microsoft, LinkedIn): each provider is invisible until its `GW_<PROVIDER>_CLIENT_ID` and secret are set. Apple is ready but gated.
- **Welcome banner**: members choose a display name, anonymous, or opt out; nothing is announced until they choose.

## Docs
- [AGENTS.md](AGENTS.md): rules for agents, including the safety defaults
- [docs/features.md](docs/features.md): the 45 features, with tier, build type and OSS candidates
- [docs/roadmap.md](docs/roadmap.md)
- [docs/domain-notes.md](docs/domain-notes.md)
- [docs/open-questions.md](docs/open-questions.md)
