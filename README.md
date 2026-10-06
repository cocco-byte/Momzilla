# Momzilla

A support chatbot for students, plus a background risk classifier that
notifies a counselor when a conversation suggests a student might need a
check-in. A real school/counseling team is the intended user - see
**Before real deployment** for what's still outstanding.

## Architecture

```
student ── chat ──▶ backend/chat_agent.py ──▶ Claude (conversational reply)
                 │
                 └─▶ backend/risk_classifier.py ──▶ Claude (risk tier only)
                          │
                          ▼
                 backend/escalation.py ──▶ backend/db.py (Postgres: alerts, no content)
                                                    ▲
counselor ── login (backend/auth.py, bcrypt + JWT) ─┘
```

Two separate model calls per message: one generates the reply the student
sees, the other classifies risk in the background. They never share output -
the classifier's reasoning is discarded after it produces a tier.

Two separate storage tiers, deliberately kept apart:
- **Conversation content** (`backend/session_store.py`) - process memory
  only, never touches disk.
- **Everything else** (`backend/db.py`, Postgres) - counselor accounts, the
  student roster, and escalation records (tier + student + timestamp,
  never message content). This is what needs to survive a restart; the
  conversations don't, by design. Any Postgres works (Aiven, Render,
  Supabase, a self-hosted instance) - `backend/db.py` just needs a
  connection string in `MOMZILLA_DATABASE_URL`.

Because conversation content is the only thing that was ever meant to be
ephemeral, and that still lives purely in process memory, the app container
itself holds no durable state - it's safe to redeploy, restart, or run as
multiple replicas without a mounted disk.

## Key safety design decisions

- **Validate feelings, never agree with harmful beliefs.** The chat system
  prompt (`backend/chat_agent.py`) explicitly instructs the model to
  reflect and validate emotion without ever affirming self-harm-supporting
  statements.
- **No conversation content is ever persisted, anywhere.** Session history
  lives in process memory only (`backend/session_store.py`) - no database
  row, no log line, no admin view of message text. This is what actually
  backs "no human can see the conversation," not an access-control policy
  layered on top of stored data.
- **Escalation is tiered and content-free.** The classifier assigns
  `none / low / medium / high / imminent`. A counselor alert fires once per
  tier increase and its entire payload (`EscalationRecord` in
  `backend/models.py`) is `student_id` + `tier` + timestamp - enforced by
  the shape of the object, not just convention.
- **Crisis resources are mentioned to the student, but sparingly**, and
  only by deterministic code (`backend/chat_agent.py`'s
  `CRISIS_RESOURCE_LINE`), never by the model improvising its own version.
  They only show up at the `imminent` tier (an explicit plan/method/
  timeline), worded to be non-diagnostic ("not saying anything's wrong,
  just figured you might not know that"), shown once per session. The
  system prompt explicitly tells the model *not* to bring up hotlines
  itself - early testing showed the model would sometimes mention 988 on
  its own *and* the deterministic line would also fire, so the student got
  it twice in one message, which read as fixating rather than listening.
- **Upfront disclosure, not a hidden trigger.** `frontend/index.html` tells
  the student before they type anything that a counselor may be quietly
  notified in some cases. Consent lives in the UI copy, not in the bot
  deciding what to hide.
- **Counselor access is authenticated and scoped.** `/counselor/alerts`
  requires a bearer token from `/auth/login`; the counselor's identity
  comes from the token, never from a client-supplied ID, so one
  counselor's login can never be used to view another's queue (see
  `tests/test_auth.py`).

## Before real deployment

Two things here are still genuinely open and are not mine to close:

- **Clinical review** of the chat persona and the classifier's risk rubric
  by an actual counselor/mental health professional - the tiers and
  wording are a reasonable starting point, not a validated instrument.
- **Legal review** for FERPA, your state's mandatory-reporting law, and
  minors' data handling - "always a no-detail ping, even for imminent
  risk" was a deliberate product choice, but confirm it holds up against
  your jurisdiction's duty-to-warn obligations before relying on it for a
  real imminent-risk case. This is the one most likely to force a change
  to `backend/escalation.py`'s payload shape.

Technical items still worth doing before a wider rollout:

- **An eval set** for the risk classifier against real (or realistic,
  anonymized) transcripts before trusting its tier boundaries - see the
  `claude-api` skill's `build-eval` flow.
- **Password reset / account recovery** for counselors - not built yet;
  today, a locked-out counselor needs someone with server access to run
  `scripts/create_counselor.py` again or reset the row directly.
- **Backups** for the Postgres database - it holds the counselor roster and
  escalation history. A managed provider (Aiven included) typically handles
  automated backups for you; confirm the retention window and that
  point-in-time recovery is actually enabled on your plan rather than
  assuming it.
- **A real notification transport beyond the dashboard** - `ConsoleNotifier`
  in `backend/escalation.py` currently only prints to the server log and
  populates `/counselor/alerts`; there's no push (email/SMS/paging) yet,
  so a counselor only finds out by checking the dashboard. Swap in a real
  transport via the same `Notifier` interface if you want a push instead
  of (or in addition to) the pull-based dashboard.

## Running it locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in ANTHROPIC_API_KEY and MOMZILLA_DATABASE_URL
python scripts/create_counselor.py   # create at least one counselor account
uvicorn backend.main:app --reload --port 8000
```

`MOMZILLA_DATABASE_URL` needs a real Postgres to point at - either a local
install/Docker container, or a free-tier Aiven/Render/Supabase instance
works fine for local dev too.

Then open `frontend/index.html` in a browser for the chat UI, and
`frontend/counselor.html` to sign in as the counselor account you just
created and see alerts.

## Deploying

### Database: Aiven for PostgreSQL

1. Create a PostgreSQL service in the Aiven console (the free/cheapest plan
   is plenty for a single school's traffic).
2. Copy the service's connection string from the Aiven console (it already
   includes `sslmode=require`) and set it as `MOMZILLA_DATABASE_URL`.
3. Run `python scripts/create_counselor.py` once, pointed at that URL
   (either from your own machine if Aiven's IP allow-list permits it, or
   from wherever you deploy the app), to create the first counselor
   account. `db.init_db()` creates the tables on first run - no separate
   migration step.

### Compute: anywhere that runs a Dockerfile

Since conversation content never touches disk and everything durable now
lives in Aiven, the app container itself is stateless - no persistent
volume needed, so pretty much any host works: Render, Railway, Google
Cloud Run, a plain VPS with Docker, etc. The `Dockerfile` in this repo
builds and runs as-is on all of them; the only per-platform work is
setting these as secrets/env vars and pointing the platform at the
Dockerfile:

- `ANTHROPIC_API_KEY`
- `MOMZILLA_DATABASE_URL` (the Aiven connection string)
- `MOMZILLA_JWT_SECRET` - **must be a real random value in production**
  (`openssl rand -hex 32`); the code falls back to an insecure default
  (`backend/auth.py`) so local dev works without setup, but that default
  would let anyone forge a counselor session if left in place.
- `MOMZILLA_CORS_ORIGINS` - your actual frontend domain, not `*` (the
  default) - see `backend/main.py`.

The frontend HTML files are static - host them anywhere (GitHub Pages,
Netlify, Cloudflare Pages, or the same server via a `StaticFiles` mount)
and point `window.MOMZILLA_API_BASE` at your deployed API URL.

Tell me which compute host you want to actually use and I'll write out the
exact steps/config for it - they're all a similar shape (build from the
Dockerfile, set the four env vars above, point it at a domain) but the
specifics (where secrets go, how the build gets triggered) differ enough
per platform that I'd rather get it right for the one you're using than
write generic instructions for all of them.

## Tests

```bash
pytest tests/
```

`tests/test_escalation.py` covers the tiering/notification logic and
`tests/test_auth.py` covers login and cross-counselor access control,
neither needing an Anthropic API key. They do need a real Postgres to run
against - `tests/conftest.py` points at `MOMZILLA_DATABASE_URL` (default
`postgresql://postgres@localhost:5432/momzilla_test`, override via
`MOMZILLA_TEST_DATABASE_URL`) and wipes/recreates its tables before every
test. A throwaway local one is one line:

```bash
docker run -d -p 5432:5432 -e POSTGRES_HOST_AUTH_METHOD=trust postgres:16
createdb -h localhost -U postgres momzilla_test
pytest tests/
```

There's no automated eval for the chat persona or risk classifier yet -
see "Before real deployment" above.
