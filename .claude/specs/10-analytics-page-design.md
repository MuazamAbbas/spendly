# Spec: Analytics Page Design

## Overview
This feature replaces the `/analytics` "Coming Soon" stub with a fully designed analytics page showing static, hardcoded data. The goal is to establish the complete UI layout — spending trend chart, category comparison, month-over-month summary, and top merchants/descriptions — before any real database queries are wired up in a future backend-connection step. This mirrors how Step 4 (Profile Page Design) preceded Step 5 (Backend Routes for Profile Page): design first, validate the layout, then wire up real data in a follow-up spec.

## Depends on
- Step 1: Database setup (schema must exist)
- Step 2: Registration (user accounts must be creatable)
- Step 3: Login + Logout (session must be set; `/analytics` must be a protected route)
- Step 4/5: Profile page design + backend (establishes the stat-card, category-badge, and category-bar CSS patterns this page reuses)

## Routes
- `GET /analytics` — replace the "Coming Soon" stub with the real analytics page — logged-in only (redirect to `/login` if not authenticated)

## Database changes
No database changes. The existing `users` and `expenses` tables are sufficient.

## Templates
- **Modify:** `templates/analytics.html` — replace the entire "Coming Soon" body with the real analytics layout, extending `base.html`, containing four sections:
  1. **Summary row** — three stat cards: total spent this month, average per transaction, number of transactions (hardcoded values, reusing the `profile-stat-card` visual pattern)
  2. **Monthly trend** — a simple bar-per-month view (six hardcoded months) showing relative spend, built with CSS bars (heights via modifier classes, no inline styles, no JS charting library)
  3. **Category comparison** — per-category totals with progress bars, reusing the existing `profile-cat-row` / `profile-cat-track` / `profile-cat-bar` pattern from `profile.html` (hardcoded rows)
  4. **Top descriptions table** — small table of the highest hardcoded individual expenses (date, description, category badge, amount), reusing the `category-badge` class

## Files to change
- `app.py` — replace the `/analytics` stub with a real view function that:
  - Redirects unauthenticated users to `/login` (same guard pattern as `profile()`)
  - Passes hardcoded context variables (summary stats, monthly trend points, category breakdown, top expenses) to `analytics.html`
- `templates/analytics.html` — replace "Coming Soon" markup with the real layout described above
- `static/css/analytics.css` — replace the "Coming Soon" styles with styles for the new sections (stat cards can reuse `profile.css` classes via shared markup; new rules only needed for the monthly trend bars and top-descriptions table if not already covered by `profile.css`)

## Files to create
No new files. `templates/analytics.html` and `static/css/analytics.css` already exist as stubs and will be modified in place.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — use raw sqlite3 via `get_db()` if any DB call is ever needed
- Parameterised queries only — never string-format SQL
- Passwords hashed with werkzeug (no changes to auth in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles — monthly trend bar heights must use CSS modifier classes (e.g. `analytics-bar-h-{{ n }}`), the same technique `profile.html` uses for category-bar widths (`profile-cat-w-{{ cat.percent }}`)
- Authentication guard: check `session.get("user_id")`; if absent, `redirect(url_for("login"))`
- All data passed to the template must be hardcoded Python dicts/lists in `app.py` — no DB queries in this step
- Category badges must reuse the existing `category-badge` CSS class, not new inline colour styles
- Reuse existing `profile-stat-card` / `profile-cat-*` classes where the layout matches, rather than duplicating near-identical CSS

## Definition of done
- [ ] Visiting `/analytics` without being logged in redirects to `/login`
- [ ] Visiting `/analytics` while logged in returns HTTP 200
- [ ] The page displays a summary row with at least three stat values (total spent, average transaction, transaction count)
- [ ] The page displays a monthly trend section with at least six hardcoded months rendered as bars
- [ ] The page displays a category comparison section with at least three hardcoded categories and progress bars
- [ ] The page displays a top-descriptions table with at least three hardcoded rows (date, description, category badge, amount)
- [ ] The navbar continues to show the logged-in state (username + logout link) and highlights "Analytics" as active
- [ ] No hex colour values appear in `analytics.css` — only CSS variables
- [ ] No inline `style="..."` attributes appear in `analytics.html`
