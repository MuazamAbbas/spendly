# Spec: Add Expense

## Overview
This step implements expense creation for Spendly. The `expenses` table and
`GET /profile` route (which reads and displays expenses) already exist, but
`/expenses/add` is currently a stub that returns the placeholder text
`"Add expense — coming in Step 7"`. This step replaces that stub with a real
form and handler so logged-in users can record a new expense (amount,
category, date, description), which then immediately shows up in their
profile page's transaction list, summary stats, and category breakdown.

## Depends on
- Step 1: Database setup (`expenses` table, `get_db()`)
- Step 3: Login / Logout (`session["user_id"]` is set on login)
- Step 5: Backend routes profile page (`database/queries.py` reads from
  `expenses`; this step adds the corresponding write)

## Routes
- `GET /expenses/add` — render the add-expense form — logged-in only
- `POST /expenses/add` — validate input, insert the expense, redirect to
  `/profile` — logged-in only

Both methods redirect a logged-out user to `/login` (same pattern as
`GET /profile`).

## Database changes
No database changes. The `expenses` table (`id`, `user_id`, `amount`,
`category`, `date`, `description`, `created_at`) from `database/db.py`
already supports this feature as-is.

## Templates
- **Create:** `templates/add_expense.html` — form with fields for amount,
  category (select), date, and description; extends `base.html`; posts to
  `/expenses/add`; renders a `{{ error }}` block above the form on
  validation failure, following the same pattern as `login.html` /
  `register.html`.
- **Modify:** `templates/profile.html` — add an "Add expense" link/button
  (e.g. near the profile header or above the transaction table) pointing to
  `{{ url_for('add_expense') }}` so users have a way to reach the new page.

## Files to change
- `app.py` — replace the stub `add_expense()` view with `GET`/`POST`
  handling: auth check, form validation, insert, redirect.
- `database/queries.py` — add a `create_expense(user_id, amount, category,
  date, description)` helper that performs a parameterised `INSERT` into
  `expenses` and returns the new row id, following the same connection
  pattern (`get_db()`, commit, close) as `create_user()` in `database/db.py`.
- `templates/profile.html` — add the "Add expense" link/button.

## Files to create
- `templates/add_expense.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs — raw `sqlite3` only via `get_db()`
- Parameterised queries only — never string-format values into SQL
- Passwords hashed with werkzeug (unaffected by this step, but do not
  regress existing auth)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- No inline styles
- `category` must be a fixed dropdown, not free text: `Food`, `Transport`,
  `Bills`, `Health`, `Entertainment`, `Shopping`, `Other` (matches the
  categories already used in `seed_db()`)
- `amount` must be validated server-side as a positive number (reject zero,
  negative, or non-numeric input) even though the form should also use
  `type="number"` client-side
- `date` must be validated server-side as a valid ISO date (`YYYY-MM-DD`,
  reuse the `date.fromisoformat` pattern already used in
  `_parse_date_filter` in `app.py`); reject invalid/missing dates
- `description` is optional; store `NULL`/empty rather than requiring text
- On validation failure, re-render `add_expense.html` with a friendly error
  via `{% if error %}` and preserve the user's submitted values in the form
  fields rather than clearing them
- On success, insert the expense for the currently logged-in user
  (`session["user_id"]`) and redirect to `/profile` — never trust a
  user-supplied `user_id` from the form
- Do not commit `spendly.db` with test expense data from manual testing

## Definition of done
- [ ] Visiting `/expenses/add` while logged out redirects to `/login`
- [ ] Visiting `/expenses/add` while logged in shows a form with amount,
      category, date, and description fields
- [ ] Submitting valid data creates a new row in `expenses` for the correct
      `user_id` and redirects to `/profile`
- [ ] The newly added expense appears in the profile page's transaction
      list, is included in `total_spent`/`transaction_count`, and is
      reflected in the category breakdown
- [ ] Submitting a negative, zero, or non-numeric amount shows an error and
      does not create a row
- [ ] Submitting an invalid or missing date shows an error and does not
      create a row
- [ ] Submitting with no description succeeds and the expense still displays
      correctly on `/profile`
- [ ] The profile page has a working link/button to `/expenses/add`
- [ ] App starts without errors and existing routes (`/`, `/login`,
      `/profile`, `/analytics`) are unaffected
