# Spec: Login and Logout

## Overview
This step implements user login and logout for Spendly. The `login.html` template and `users` table already exist, and Step 2 (Registration) established the pattern of hashing passwords with werkzeug and starting a session via `session["user_id"]`. Currently `GET /login` only renders the static form with no backend logic, and `/logout` is a placeholder that returns plain text. This step wires up `POST /login` to verify credentials against the stored password hash and start a session, and wires up `/logout` to end that session. This is the second authentication capability in the app and is a prerequisite for any user-scoped feature that needs to check "is someone logged in" (profile in Step 4, expenses in Steps 7–9).

## Depends on
- Step 1 — Database setup (`users` table, `get_db()`, `init_db()`, `seed_db()`)
- Step 2 — Registration (`app.secret_key`, password hashing convention, `session["user_id"]` pattern, `get_user_by_email()`)

## Routes
- `GET /login` — render the login form — public (already exists, unchanged)
- `POST /login` — validate credentials, start session, redirect to landing — public
- `GET /logout` — clear the session, redirect to landing — logged-in (safe no-op if called while logged out)

## Database changes
No new tables, columns, or constraints. The `users` table already has everything needed (`email`, `password_hash`). However, `get_user_by_email()` in `database/db.py` currently only `SELECT`s `id`, which is not enough to verify a password or greet the user by name — it must be widened to also return `password_hash` and `name`. This is a function change, not a schema change.

## Templates
- **Create:** None
- **Modify:**
  - `templates/login.html` — no structural changes required; the existing form already posts `email`, `password` to `/login` and renders `{{ error }}` when present.
  - `templates/base.html` — nav currently always shows "Sign in" / "Get started" regardless of session state. Update to conditionally show a "Logout" link (pointing to `{{ url_for('logout') }}`) when `session.get('user_id')` is set, and the existing "Sign in" / "Get started" links otherwise.

## Files to change
- `app.py` — replace the stub `GET /login` route with `GET`/`POST` handling: on POST, validate form input is present, fetch the user by email, verify the password with `check_password_hash`, set `session["user_id"]` on success and redirect to `landing`, or re-render the form with a generic error on failure. Replace the `/logout` stub to clear the session (`session.clear()`) and redirect to `landing`.
- `database/db.py` — widen `get_user_by_email(email)` to `SELECT id, name, email, password_hash FROM users WHERE email = ?` so callers can verify a password and access the user's name/id. Confirm the existing call in `register()`'s duplicate-email check (`app.py`) still works as a truthy check against the returned row.

## Files to create
None.

## New dependencies
No new dependencies. `werkzeug.security.check_password_hash` is available alongside the already-used `generate_password_hash`.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (verify with `check_password_hash`, never compare plaintext)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Use one generic error message (e.g. "Invalid email or password.") for both "email not found" and "wrong password" cases — do not reveal which one failed, to avoid user enumeration
- Reuse the existing `{% if error %}` block in `login.html` for the generic error, matching the pattern already used in `register.html`
- `/logout` must clear the full session (not just delete a single key) so no stale state carries over
- On successful login, redirect away from `/login` — do not leave the user on the form
- Do not commit `spendly.db` with test login data from manual testing

## Definition of done
- [ ] Visiting `/login` still renders the existing form unchanged
- [ ] Submitting valid demo credentials (`demo@spendly.com` / `demo123`) logs the user in and redirects away from `/login`
- [ ] Submitting a correct email with a wrong password shows a generic "Invalid email or password" error and does not start a session
- [ ] Submitting an email that doesn't exist shows the same generic error (no different wording that reveals the email is unregistered)
- [ ] After login, the navbar shows a "Logout" link instead of "Sign in" / "Get started"
- [ ] Visiting `/logout` while logged in clears the session and redirects to the landing page, after which the navbar reverts to showing "Sign in" / "Get started"
- [ ] Visiting `/logout` while already logged out does not error, and simply redirects to the landing page
- [ ] App starts without errors and existing routes (`/`, `/register`, `/terms`, `/privacy`) are unaffected
