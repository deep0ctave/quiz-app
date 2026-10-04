# Deploying Schoolmela Quiz

The system is three parts:

- **backend**: FastAPI API, uv-managed, SQLAlchemy ORM with Alembic migrations.
- **web**: nginx serving the website and passing `/api/` to the backend. The Android app also
  talks to `https://<your host>/api`.
- **PostgreSQL 17**: the only place data is kept.

Two ways to run it in production:

| | Single server (Docker Compose) | Kubernetes (Helm) |
|---|---|---|
| Good for | One school or district, simplest to run | Any cloud |
| Database | The `db` container on the same server | A managed PostgreSQL (recommended) |
| Backups | The `backup` service (daily, 7 days kept) | The database provider's backups, or the chart's CronJob |
| HTTPS | A reverse proxy you add in front (e.g. Caddy) | The ingress controller and a TLS certificate |

## Settings

| Setting | Required | Purpose |
|---|---|---|
| `JWT_SECRET` | yes | Signs logins; at least 32 random characters (`openssl rand -base64 48`). Changing it logs everyone out. |
| `DB_URL`, `DB_USERNAME`, `DB_PASSWORD` | yes | SQLAlchemy PostgreSQL URL (`postgresql+psycopg://host:5432/quiz`) and credentials. |
| `BOOTSTRAP_ADMIN_MOBILE`, `BOOTSTRAP_ADMIN_PIN`, `BOOTSTRAP_ADMIN_NAME` | first start | Creates the first admin if that mobile number is not registered yet. Change the PIN from the default. |
| `SWAGGER_ENABLED` | no | API documentation at `/swagger-ui.html`. Set to `false` in production. |
| `TRUSTED_PROXY_CIDR` (web) | behind a proxy | Address range of the load balancer/ingress in front of nginx, whose `X-Forwarded-For` gives the real client address. Default trusts none. |
| `app.reports.time-zone` | no (Asia/Kolkata) | Time zone of dates in CSV exports. |

## Option A: single server with Docker Compose

1. Install Docker on a Linux server (2 CPUs and 2 GB of memory are plenty for 100 students at once).
2. Copy the repository, then create `.env` from `.env.example` and set **at least**
  `JWT_SECRET`, `DB_PASSWORD`, `BOOTSTRAP_ADMIN_MOBILE`, `BOOTSTRAP_ADMIN_PIN`, and
  `SWAGGER_ENABLED=false`.
3. In `docker-compose.yml`, remove the published ports of `db` (5432) and `backend` (8080). Only
   `web` needs to be reachable.
4. `docker compose up -d --build`
5. Put HTTPS in front of the web container. For example, with Caddy on the server:
   `quiz.example.org { reverse_proxy localhost:3000 }`.
   - Publish the web port on localhost only (`"127.0.0.1:3000:8080"`), so nobody can bypass the
     proxy.
   - Tell nginx to trust the proxy's `X-Forwarded-For`. Requests from a proxy on the host arrive
     from Docker's gateway, so set `TRUSTED_PROXY_CIDR=172.16.0.0/12` on the `web` service.
   - Have the proxy send `Strict-Transport-Security` (Caddy does this automatically).

### Backups and restoring (Compose)

The `backup` service writes a dump when it starts and every 24 hours to the `backups` volume,
deleting dumps older than `BACKUP_KEEP_DAYS` (7). **Copy them off the server regularly**: a
backup on the same disk does not survive the disk failing.

```sh
docker compose exec backup ls -lh /backups                 # list dumps
docker compose cp backup:/backups ./backups-copy            # copy them off the server
```

To restore (this **replaces** the current data):

```sh
docker compose stop backend
docker compose exec backup pg_restore --clean --if-exists --no-owner -d quiz /backups/quiz-<time>.dump
docker compose start backend
```

A restore was tested during development: a dump restored into a scratch database had the same
rows in every table as the original.

## Option B: Kubernetes with Helm

Images are published by the **Release** workflow when you push a tag such as `v1.0.0`:
`ghcr.io/ravichandrae/schoolmela-quiz-backend:1.0.0` and `…-web:1.0.0`. Make the packages public
on GitHub, or give the cluster pull access.

```sh
kubectl create secret generic quiz-secrets \
  --from-literal=DB_PASSWORD='…' \
  --from-literal=JWT_SECRET="$(openssl rand -base64 48)" \
  --from-literal=BOOTSTRAP_ADMIN_NAME='Head Teacher' \
  --from-literal=BOOTSTRAP_ADMIN_MOBILE='9xxxxxxxxx' \
  --from-literal=BOOTSTRAP_ADMIN_PIN='…'

helm install quiz deploy/helm/schoolmela-quiz \
  --set image.tag=1.0.0 \
  --set secrets.existingSecret=quiz-secrets \
  --set database.url=postgresql+psycopg://<db host>:5432/quiz \
  --set database.host=<db host> \
  --set ingress.host=quiz.example.org \
  --set web.trustedProxyCidr=<pod/LB address range>
```

What the chart sets up:

- One backend pod and two web pods, with health checks.
- An Ingress with TLS.
- Locked-down containers: non-root, read-only filesystem, no Linux capabilities.

Enable HSTS on the ingress (for ingress-nginx this is on by default with TLS). Set
`backup.enabled=true` for a daily `pg_dump` CronJob if your database has no backups of its own.
See `values.yaml` for everything else.

Notes:

- **Database changes** run automatically when the backend starts (Alembic). The first Python
  migration copies existing Flyway data into `py_*` tables and does not copy refresh sessions.
- **Live-room state is kept in backend process memory.** Keep `backend.replicas=1`; add a shared
  broker such as Redis before scaling the backend horizontally.
- Five incorrect PINs lock that account for 15 minutes. There is not yet a distributed per-IP
  rate limiter.

## Health checks and monitoring

- `GET /api/actuator/health` — overall (`{"status":"UP"}`)
- `/api/actuator/health/liveness` and `/api/actuator/health/readiness` — for orchestrators
- Logs go to standard output for the platform to collect.

## Android app

Build it for your server's address and share the APK (or publish to Play):

```sh
cd mobile
flutter build apk --release --split-per-abi --dart-define=API_BASE_URL=https://quiz.example.org/api
```

Set up your own signing key first (see `mobile/README.md`). Release builds only connect over HTTPS.

## Load test

`deploy/loadtest/quiz-day.js` (k6) simulates a class. All students log in and start one quiz at
the same moment, answer 5 questions with 2–6 seconds' thinking time each, then open their
results. Run it against a throwaway stack, because it creates students and a quiz:

```sh
WEB_PORT=3100 BACKEND_PORT=8180 DB_PORT=5433 \
  docker compose -p quiz-loadtest up -d --build --wait
docker run --rm -i -e BASE_URL=http://host.docker.internal:3100/api -e STUDENTS=100 \
  grafana/k6 run - < deploy/loadtest/quiz-day.js
docker compose -p quiz-loadtest down -v
```

Historical results with **100 students at once** (October 2026; measured before the FastAPI
rewrite, so rerun this test before using it as a Python-backend performance claim):

| Measure (95th percentile) | Freshly started | Warmed up | Target |
|---|---|---|---|
| Submitting an answer | 14 ms | 11 ms | < 300 ms |
| All quiz requests (list, start, answer, results) | 356 ms | 119 ms | < 500 ms |
| Logging in (all 100 in the same second) | 741 ms | 649 ms | < 2 s |
| Failed requests | 0 of 1008 | 0 of 1008 | < 1% |

The Java-era backend used about 475 MB of memory. Its measurements and BCrypt login timings do
not describe the FastAPI implementation; repeat the load test before sizing a production rollout.
