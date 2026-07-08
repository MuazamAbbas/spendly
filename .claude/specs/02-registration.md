# Spec: Registration

## Overview
This step implements user registration for Spendly. The landing page, `register.html` template, and `users` table already exist (built in Step 1), but `/register` currently only renders the static form with no backend logic. This step wires up the `POST /register` handler so new users can create an account: validating input, hashing the password, inserting into the `users` table, and starting a logged-in session. This is the first authentication capability in the app and is a prerequisite for login (Step 3) and any user-scoped feature (profile, expenses).

## Depends on
- Step 1 — Database setup (`users` table, `get_db()`, `init_db()`, `seed_db()`)

## Routes
- `GET /register` — render the registration form — public (already exists, unchanged)
- `POST /register` — validate input, create user, log them in, redirect to dashboard/home — public

## Database changes
No database changes. The `users` table (`id`, `name`, `email`, `password_hash`, `created_at`) from `database/db.py` already supports registration as-is. The `email UNIQUE NOT NULL` constraint already prevents duplicate accounts.

## Templates
- **Create:** None
- **Modify:** `templates/register.html` — no structural changes required; the existing form already posts `name`, `email`, `password` to `/register` and renders `{{ error }}` when present. Only touch this file if server-side validation needs a field-specific error shown.

## Files to change
- `app.py` — replace the stub `/register` route with `GET`/`POST` handling: form validation, duplicate-email check, password hashing, insert into `users`, set session, redirect. Add `app.secret_key` (required for Flask sessions — currently unset).
- `database/db.py` — add a `create_user(name, email, password)` helper (or equivalent) that performs the parameterized INSERT and returns the new user id, following the same connection pattern as `seed_db()`.

## Files to create
None.

## New dependencies
No new dependencies. `werkzeug.security.generate_password_hash` is already used in `database/db.py`.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (`generate_password_hash`)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Validate on the server even though the form has `required`/`type="email"` client-side constraints (name non-empty, valid email format, password minimum 8 characters)
- Check for existing email before inserting and show a friendly error via the existing `{% if error %}` block in `register.html` rather than a raw SQLite `IntegrityError`
- On success, store the new user's id in `session` (e.g. `session["user_id"]`) and redirect — do not leave the user on the form after a successful registration
- Do not commit `spendly.db` with test registration data from manual testing

## Definition of done
- [ ] Visiting `/register` still renders the existing form unchanged
- [ ] Submitting the form with valid name/email/password creates a row in `users` with a hashed (not plaintext) password
- [ ] Submitting with an email that already exists shows an error on the page and does not create a duplicate row
- [ ] Submitting with a missing name, invalid email format, or password under 8 characters shows an error and does not create a row
- [ ] After successful registration, the user is redirected away from `/register` and a session is established (verify via a subsequent request that would require login, once login/session-checking exists)
- [ ] App starts without errors and existing routes (`/`, `/login`, `/terms`, `/privacy`) are unaffected
