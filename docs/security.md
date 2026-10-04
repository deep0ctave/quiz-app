# Security

What protects Schoolmela Quiz, and what is left to do. Requirement 4.3.3 asks for secure
authentication, role-based access and protection against common web attacks.

## Accounts and logins

- **PINs are never stored**, only Argon2 hashes. Existing BCrypt PIN hashes are accepted during
  migration and upgraded to Argon2 after a successful login. Unknown mobile numbers use a dummy
  Argon2 verification so lookup timing is less revealing.
- **Lockout**: 5 wrong PINs lock the account for 15 minutes. Simultaneous attempts are all counted.
- **No per-IP rate limiter yet**: account lockout limits guessing against one account, but a
  distributed IP-based limit is still needed to slow attempts spread across many accounts.
- **Sessions**:
  - Access tokens (signed JWTs) last 15 minutes.
  - Refresh tokens last 7 days. They are stored only as SHA-256 hashes, replaced on every use,
    and revoked on logout, PIN reset and account turn-off. Expired-token cleanup is not yet scheduled.
- **Turned-off accounts stop working at once**: every request checks that the account is active
  and takes its role from the database, not only from the token.
- **Where logins are kept**:
  - Website: `sessionStorage`, so the login is forgotten when the tab is closed (shared tablets).
  - Android app: Android's encrypted storage until **Log out**.

## Access control

- Two roles, STUDENT and ADMIN. `/admin/**` needs ADMIN; the student quiz endpoints need STUDENT.
- Students can only see quizzes given to them, and only their own attempts and results (tested).
- Correct answers are never sent to students while a quiz is running. Afterwards they are shown
  only if the quiz allows it.
- Quiz timing is enforced by the server, so students cannot gain time by changing their device clock.

## Web attacks (OWASP Top 10)

| Risk | Protection |
|---|---|
| Injection (SQL) | SQLAlchemy parameterized queries; no SQL built from user input in request handlers. |
| Cross-site scripting | React escapes all text. A Content Security Policy lets the page run only the site's own scripts and load nothing from other sites. |
| Clickjacking | `X-Frame-Options: DENY` and `frame-ancestors 'none'`. |
| CSV/formula injection | Exported cells beginning with formula characters are prefixed with an apostrophe and quoted by the CSV writer. |
| Cross-site request forgery | The API uses bearer tokens, not cookies, so other sites cannot make requests as a logged-in user. |
| Sensitive data exposure | PIN hashes are never returned; error messages are generic. |
| Security misconfiguration | Swagger can be switched off; nginx hides its version; request bodies are limited to 64 KB. |
| Vulnerable components | Dependabot opens weekly update PRs. CI fails on high-severity advisories in the web app's runtime dependencies. |

## Containers and deployment

- Both images run as non-root users (numeric UIDs). They were tested with a read-only filesystem
  and all Linux capabilities dropped, as the Helm chart configures.
- Secrets come from the environment or a Kubernetes Secret; the chart refuses to install without
  a 32-character `JWT_SECRET`.
- HTTPS and HSTS are provided by the entry point in front of nginx (see `deployment.md`). The
  Android app's release build refuses plain HTTP.

## Known limits and next steps

1. **Short PINs are guessable over time.** A 4-digit PIN has 10,000 possibilities. With the lockout,
   one account allows about 480 guesses a day. Longer PINs (6 digits) are much safer; consider
   requiring them.
2. **There is no per-IP rate limiter yet.** Account lockout applies per user; a shared limit is
  needed to slow guessing spread across many accounts.
3. **Registration is open**: anyone who can reach the site can create a student account. If that
   becomes a problem, add class join codes or admin approval.
4. **Not yet done**: an independent penetration test and automated scanning of Python dependencies
  and container images (e.g. Trivy) in CI.
5. **Development defaults** in `docker-compose.yml` (JWT secret, admin PIN, database password) must
   be replaced in `.env` for any real use.
6. **Live rooms use process-local state.** The Helm chart defaults to one backend replica; use a
    shared pub/sub broker before scaling that service.
