# Spec: Date Filter for Profile Page

## Overview
Step 6 adds a date-range filter to the `/profile` page so users can narrow the
transaction history, summary stats, and category breakdown to a specific
period (e.g. "This month", "Last 30 days", or a custom start/end date) instead
of always seeing all-time data. This builds directly on the live queries
wired up in Step 5, extending each query helper to accept optional date
bounds while preserving their existing no-filter behaviour.

## Depends on
- Step 1: Database setup (`expenses.date` column exists)
- Step 2: Registration (users exist)
- Step 3: Login / Logout (`session["user_id"]` is set)
- Step 4: Profile page static UI (template sections already exist)
- Step 5: Backend connection (`database/queries.py` helpers already query live data)

## Routes
- `GET /profile` — modified — accepts optional `start_date` and `end_date`
  query-string parameters (e.g. `/profile?start_date=2026-07-01&end_date=2026-07-31`)
  — logged-in only (existing auth guard unchanged)

No new routes.

## Database changes
No database changes. The existing `expenses.date` column (stored as
`YYYY-MM-DD` text) is sufficient for range filtering with SQL `BETWEEN` /
comparison operators.

## Templates
- **Modify:** `templates/profile.html`
  - Add a filter form (two `<input type="date">` fields + submit button, and
    a "Clear filter" link) above the summary stats section.
  - Form uses `method="GET"` so the filter state lives in the URL and survives
    a page refresh or share.
  - When a filter is active, the transaction table and category breakdown
    reflect only expenses in that range; when absent, behaviour is identical
    to Step 5 (all-time data).

## Files to change
- `app.py` — read `start_date` / `end_date` from `request.args` in the
  `profile()` view, validate them, and pass them through to the query helpers
  and back to the template (so the form can repopulate with the active filter)
- `database/queries.py` — add optional `start_date=None, end_date=None`
  parameters to `get_summary_stats`, `get_recent_transactions`, and
  `get_category_breakdown`; when provided, append a parameterised
  `AND date BETWEEN ? AND ?` clause
- `templates/profile.html` — add the filter form and wire it to the current
  filter values

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format dates into SQL
- Passwords hashed with werkzeug (unchanged in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles
- Currency must always display as ₨ — never £ or $
- Date inputs must be validated server-side: reject malformed dates and swap
  `start_date`/`end_date` if `start_date` is after `end_date`, rather than
  raising an exception
- If `start_date` or `end_date` is missing or invalid, fall back to no filter
  (all-time data) instead of erroring
- `get_recent_transactions`, `get_summary_stats`, and `get_category_breakdown`
  must remain callable with no date arguments (Step 5 call sites/tests must
  keep working unchanged)
- Category breakdown `pct` values must still sum to 100 for the filtered set

## Definition of done
- [ ] Visiting `/profile` with no query parameters shows all-time data, identical to Step 5 behaviour
- [ ] Visiting `/profile?start_date=2026-07-01&end_date=2026-07-10` as the seed user shows only the 3 expenses in that range (Grocery shopping, Uber ride, Internet bill) with a total spent of ₨ 177.50
- [ ] The date filter form is pre-filled with the active `start_date`/`end_date` from the URL
- [ ] A "Clear filter" link/button returns to `/profile` with no query parameters and restores all-time data
- [ ] Submitting a `start_date` after `end_date` does not error — results still display sensibly (swapped range)
- [ ] Submitting a malformed date (e.g. `start_date=notadate`) does not raise an exception — falls back to all-time data
- [ ] Category breakdown percentages still sum to 100% when a filter is applied
- [ ] No hex colour values appear in the modified `profile.html`
