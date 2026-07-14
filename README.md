# Spendly

Track every rupee. Own your finances.

Spendly is a personal expense tracker built with Flask and vanilla SQL — no ORM, no frontend framework, just server-rendered templates and a raw `sqlite3` data layer. It was built incrementally, one spec-driven feature at a time (see [Roadmap](#roadmap) below).

**Live demo:** https://expense-tracker-production-0df7.up.railway.app

Demo login: `demo@spendly.com` / `demo123`

## Features

- **Auth** — registration and login/logout with `werkzeug`-hashed passwords and server-side session auth
- **Profile dashboard** — total spent, transaction count, and top category at a glance
- **Date-filtered history** — filter transactions, stats, and category breakdown by a date range
- **Add / edit / delete expenses** — full CRUD on expenses, each scoped to the logged-in user (404, not 403, on any cross-user access attempt)
- **Category breakdown** — spending grouped by category with percentage bars
- **Analytics** — coming soon page (not yet implemented)

## Tech stack

- **Backend:** Flask 3, raw `sqlite3` (no SQLAlchemy/ORM), `werkzeug` for password hashing
- **Frontend:** Jinja2 templates, hand-written CSS (CSS variables for theming, no framework), a little vanilla JS
- **Testing:** `pytest` + `pytest-flask`
- **Deployment:** Railway (Gunicorn as the production WSGI server)

## Project structure

```
app.py                   Flask app, routes, request handling
database/
  db.py                  Connection helper, schema, seeding
  queries.py              Parameterised SQL query functions
templates/                Jinja2 templates (all extend base.html)
static/
  css/                    Per-page stylesheets, CSS variables
  js/                     Vanilla JS
tests/                    pytest test suite, one file per feature step
.claude/specs/             Spec doc for every feature step (01-09)
Procfile                  Railway/production start command
requirements.txt
```

## Getting started

### Prerequisites
- Python 3.10+

### Setup
```bash
git clone https://github.com/MuazamAbbas/spendly.git
cd spendly
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Run locally
```bash
python app.py
```
The app starts on `http://127.0.0.1:5001`. On first run it creates `spendly.db` (SQLite) and seeds a demo user (`demo@spendly.com` / `demo123`) with sample expenses.

### Run tests
```bash
pytest
```
Tests use an isolated SQLite database (via `SPENDLY_DB_PATH`, see `tests/conftest.py`) so they never touch your local `spendly.db`.

## Database schema

Two tables, defined in `database/db.py`:

```sql
users (id, name, email UNIQUE, password_hash, created_at)
expenses (id, user_id -> users.id, amount, category, date, description, created_at)
```

## Routes

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/` | public | Landing page |
| GET/POST | `/register` | public | Create an account |
| GET/POST | `/login` | public | Sign in |
| GET | `/logout` | logged-in | End session |
| GET | `/profile` | logged-in | Dashboard: stats, transactions, category breakdown, date filter |
| GET/POST | `/expenses/add` | logged-in | Add an expense |
| GET/POST | `/expenses/<id>/edit` | logged-in, owner-only | Edit an expense |
| POST | `/expenses/<id>/delete` | logged-in, owner-only | Delete an expense |
| GET | `/analytics` | logged-in | Coming soon page |
| GET | `/terms`, `/privacy` | public | Static pages |

Every expense route is scoped to `session["user_id"]` at the query level (`WHERE ... AND user_id = ?`), not just in application logic, and returns a 404 rather than a 403 for another user's expense so ownership is never leaked.

## Deployment

Deployed on [Railway](https://railway.com) using Gunicorn as the production server:

```
web: gunicorn app:app --bind 0.0.0.0:$PORT
```

Railway builds from `requirements.txt` and runs the `Procfile`'s `web` process. Note: the app's SQLite database is stored on the container's local filesystem, which is not persisted across redeploys/restarts — fine for a demo, but a Railway volume or a Postgres database would be needed for durable data in production.

## Roadmap

Built as a sequence of specs in `.claude/specs/`, each shipped through its own feature branch and PR:

1. Database setup
2. Registration
3. Login / logout
4. Profile page design
5. Backend routes for the profile page
6. Date filter on the profile page
7. Add expense
8. Edit expense
9. Delete expense

## Security notes (teaching project — see inline comments)

- `app.secret_key` is hardcoded in `app.py` for demo purposes — use an environment variable in production.
- Routes do not currently implement CSRF protection (a known gap across all mutating routes, not specific to any one feature).
