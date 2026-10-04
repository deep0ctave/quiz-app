# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Schoolmela Quiz: timed multiple-choice quizzes for rural school students (ages 12–15) plus an admin console for teachers. Product requirements live in `Schoolmela Quiz App Requirements.md`; user-facing docs, deployment, and security notes are in `docs/`.

Three clients of one API:

- `backend/`: FastAPI (Python 3.12+), uv, PostgreSQL 17, SQLAlchemy, Alembic
- `web/`: React 19 + TypeScript (Vite), served by nginx in Docker. Used by both students and admins.
- `mobile/`: Flutter Android app, **students only** (a teacher who logs in is told to use the website)
- `deploy/`: Helm chart (`deploy/helm/schoolmela-quiz`), Postgres backup script, k6 load test (`deploy/loadtest/quiz-day.js`)

## Commands

Full stack: `docker compose up --build` (web on :3000, API on :8080, Swagger at `/swagger-ui.html`). The local admin is mobile `9999999999`, PIN `123456`.

Backend (from `backend/`; needs Python 3.12+ and uv):

```sh
uv sync --group dev
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8080
uv run pytest
```

Web (from `web/`, Node 22):

```sh
npm run dev          # :5173, proxies /api -> localhost:8080 (strips the /api prefix)
npm test             # vitest run
npx vitest run src/pages/LoginPage.test.tsx   # one file
npm run lint         # oxlint
npm run build        # tsc -b && vite build
```

Mobile (from `mobile/`): `flutter analyze`, `flutter test`, `flutter run` (emulator reaches `http://10.0.2.2:3000/api`; override with `--dart-define=API_BASE_URL=...`). Release builds only allow HTTPS.

CI (`.github/workflows/ci.yml`) runs backend `uv sync`/pytest, web `npm audit`/lint/test/build, mobile analyze/test, `helm lint` + kubeconform, and `docker compose build`. Pushing a `v*` tag publishes images to GHCR (`release.yml`).

## Backend architecture

FastAPI routes, Pydantic request models, SQLAlchemy 2 ORM models, and JWT helpers live under `backend/app/`. Alembic revisions are under `backend/migrations/versions/`. The API preserves the existing `/auth`, `/admin`, and `/me` JSON contract for the web and mobile clients.

- **Authorization**: `/admin/**` requires ADMIN and `/me/**` quiz/result routes require STUDENT. The backend has no `/api` prefix; nginx strips it. WebSocket rooms authenticate with the short-lived access token.
- **Auth**: HS256 access JWTs last 15 minutes; opaque refresh tokens rotate and are stored as SHA-256 hashes for 7 days. PINs are Argon2-hashed; imported Java BCrypt hashes are verified and upgraded at next login. Five failed PINs lock the account for 15 minutes.
- **Quiz timing**: attempt questions are snapshotted at start and timed on the server. Live rooms push questions without answer keys, accept one answer per student, then advance on all answers or timeout. Room fan-out is in process memory, so keep one backend replica until a shared broker is implemented.
- **Schema**: define tables in `backend/app/models.py`, add a new Alembic revision under `backend/migrations/versions/`, and never edit an applied revision. `0004_import_java_data.py` transfers prior Flyway data and resets refresh sessions.
- `JWT_SECRET` must be at least 32 characters outside local development. FastAPI docs use `/swagger-ui.html` and can be disabled with `SWAGGER_ENABLED=false`.

### Backend tests

Python tests use pytest and an isolated in-memory SQLite database for API/auth/WebSocket integration tests. Run `uv run pytest` from `backend/`.

## Web architecture

- `src/api/client.ts` is the only place that talks to `fetch`. It stores the session in **sessionStorage** on purpose (students share tablets, so closing the tab logs out), refreshes an expired access token once on 401 (concurrent callers share a single refresh because refresh tokens rotate), and converts problem details to `ApiError`, whose `message` can be shown as-is. `apiDownload` handles authenticated file downloads such as CSV.
- One module per API area in `src/api/`. Pages are in `src/pages/`, and role gating uses `auth/RequireRole`.
- Tests are vitest + Testing Library (jsdom). Shared helpers are in `src/test-utils.tsx`, and tests are colocated as `*.test.tsx`.
- `web/nginx.conf.template` proxies `/api/*` and forwards WebSocket upgrades to the API.

## Mobile architecture

`lib/api/` (HTTP client and models, same API and error format as the web app), `lib/auth/` (session kept in Android encrypted storage until logout), `lib/screens/`. Widget tests use a fake API and a fake clock (`test/support.dart`). The integration test in `integration_test/` needs a real server and a student with an untaken quiz (see `mobile/README.md`).
