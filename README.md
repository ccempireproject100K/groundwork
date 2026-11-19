# Groundwork (working name)

Groundwork is the adults' site: a reentry and recovery social app. One community, one feed and one identity, for people coming home from incarceration and people in substance-use recovery (including people who were never incarcerated). Its sibling is **Groundwork YEE** (Young Entrepreneurs Edition), a separate site and repo for young people entering the workforce, preparing for adulthood and starting businesses.

> The name is a placeholder. Finalists are Groundwork and Commissary Club ("Refresh" is taken). Rename by changing `backend/app/config.py` (`DEFAULT_APP_NAME`, or env `GW_APP_NAME`) and `frontend/src/brand.js` (or env `VITE_APP_NAME`). The sibling's name for the welcome banner lives in `brand.js` too (`VITE_SIBLING_NAME`).

**Status: built out, pre-launch.** All 51 registered features have a working backend module and a screen. Tests: 206 backend, 96 frontend, all passing. What is working:
- the crisis button on every screen (988 call or text, 911), the relapse protocol placeholder, and the lock and filter policy
- reentry checklist (Brann's 33 steps), court calendar, resource directory, 12-step locator, counseling referrals
- work: job board, application tracker, resume builder (print and PDF), interview coach, micro-gigs
- community: feed with anonymous posting, events, program groups, virtual meetings, video, photo and voice posts, anonymous Q&A, mentorship, peer messaging
- journey portfolio (private by default), milestones, day-one archive, merch rewards, progress share card, housing savings
- document vault (envelope encryption) and one-tap real-delete wipe
- family mode (member controls visibility, every share defaults to off), AI matching, virtual venue preview, courses, music player, read aloud, dictation
- federated sign-in (env-gated, see below), a new-member welcome banner, and 90 locales (Arabic, Urdu, Persian, Hebrew, Pashto, Dari and Yiddish are RTL; crisis and safety copy stays English until a human reviews it)

Not done: Brann's clinical and relapse-protocol wording stays a draft for review, tiers for 33 features are unassigned until he assigns them, and no payment provider is built (the paid plan exists only in `backend/app/tiers.py`).

## Plans and prices
Set by Brann on 2026-11-19, the same on both sites: **Free $0** and **Paid $3.99/month** (`price_cents: 399`). There is no top tier. The paid plan's name stays "Paid". Plans live only in `backend/app/tiers.py`.

## Run
```bash
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
GW_JWT_SECRET=$(python3 -c 'import secrets;print(secrets.token_hex(32))') .venv/bin/uvicorn app.main:create_app --factory --reload
cd ../frontend && npm ci && npx vitest run && npm run build && npm run dev
```
Every backend environment variable is listed (names only) in `backend/.env.example`; only `GW_JWT_SECRET` is required. `GW_VAULT_KEK` is the base64 of 32 random bytes (`python3 -c 'import base64,os;print(base64.b64encode(os.urandom(32)).decode())'`); the vault refuses to run without it.

## Optional features that are off by default
- **AI resume assist** (talk it through, or paste an old resume; the draft is always reviewed by the member): refuses with a plain 503 until the env var `GW_META_MODEL_API_KEY` is set (optional `GW_META_MODEL_API_URL`). No paid API call is ever made without it; with it, every call is metered per member per month by `backend/app/ai_bank.py`. The owner has not approved this spending, so leave the key unset. Building a resume by hand never depends on it.
- **Paid plan billing** (Stripe Checkout, subscription mode): `POST /api/billing/checkout` starts a Checkout Session for the paid plan, with the price read from `backend/app/tiers.py`. `POST /api/billing/webhook` verifies the `Stripe-Signature` header, processes each event id once, and switches a member to the paid plan only after the payment amount and currency match the plan. A cancelled or unpaid subscription returns the member to free. `GET /api/billing/status` reports the member's plan. Set `GW_STRIPE_SECRET_KEY`, `GW_STRIPE_WEBHOOK_SECRET` and `GW_PUBLIC_URL`; with any of them unset the endpoints answer 503 and grant nothing. In the Stripe dashboard, point a webhook endpoint at `<site>/api/billing/webhook` for `checkout.session.completed`, `customer.subscription.updated` and `customer.subscription.deleted`. New accounts always start free.
- **Federated sign-in** (Google, Facebook, Microsoft, LinkedIn): each provider is invisible until its `GW_<PROVIDER>_CLIENT_ID` and secret are set. Apple is ready but gated. Set each provider's redirect URI (`GW_<PROVIDER>_REDIRECT_URI`) to the backend's `/api/auth/<provider>/callback`, and keep `GW_FRONTEND_ORIGIN` pointed at the frontend that should receive the session. Sign-in state expires after 10 minutes and is bound to the browser that started it with a short-lived cookie.
- **Welcome banner**: members choose a display name, anonymous, or opt out; nothing is announced until they choose.

## Relation to other repos
This repo supersedes **Groundwork-1.5** (the newer built-out adult app with the federated sign-in layer): its frontend, federated sign-in and tests were merged here, on top of this repo's 90-locale set. Groundwork-1.5 is kept as a read-only reference. A few adult-relevant pieces from the YEE line (welcome banner, AI resume assist, the Brother's Keeper spec) were also brought over from GW-Yee-Lilmagic. The sibling site is **Groundwork YEE** (`Groundwork-YEE`).

## Docs
- [AGENTS.md](AGENTS.md): rules for agents, including the safety defaults
- [docs/features.md](docs/features.md): the 51 features, with tier, build type and OSS candidates
- [docs/roadmap.md](docs/roadmap.md)
- [docs/domain-notes.md](docs/domain-notes.md)
- [docs/open-questions.md](docs/open-questions.md)
- [docs/TRANSLATION_PLAN.md](docs/TRANSLATION_PLAN.md) and [REDO_STATUS.md](REDO_STATUS.md): locale status
