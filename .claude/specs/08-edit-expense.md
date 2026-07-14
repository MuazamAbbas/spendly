# Spec: Edit Expense

## Overview
This step implements expense editing for Spendly. The `expenses` table,
`GET /profile` (which lists transactions), and `/expenses/add` already exist,
but `/expenses/<int:id>/edit` is currently a stub that returns the
placeholder text `"Edit expense — coming in Step 8"`. This step replaces
that stub with a real form and handler so logged-in users can update an
existing expense's amount, category, date, and description, with the
change immediately reflected in their profile page's transaction list,
summary stats, and category breakdown.

## Depends on
- Step 1: Database setup (`expenses` table, `get_db()`)
- Step 3: Login / Logout (`session["user_id"]` is set on login)
- Step 5: Backend routes profile page (`database/queries.py` reads from
  `expenses`)
- Step 7: Add expense (`create_expense`, `add_expense.html`, and the
  add-expense form pattern this step reuses for editing)

## Routes
- `GET /expenses/<int:id>/edit` — render the edit-expense form pre-filled
  with the expense's current values — logged-in only, and only if the
  expense belongs to the current user
- `POST /expenses/<int:id>/edit` — validate input, update the expense,
  redirect to `/profile` — logged-in only, and only if the expense belongs
  to the current user

Both methods redirect a logged-out user to `/login` (same pattern as
`GET /profile`). If the expense does not exist, or exists but belongs to a
different user, return a 404 rather than revealing the expense exists.

## Database changes
No database changes. The `expenses` table (`id`, `user_id`, `amount`,
`category`, `date`, `description`, `created_at`) from `database/db.py`
already supports this feature as-is.

## Templates
- **Create:** `templates/edit_expense.html` — same form as
  `add_expense.html` (amount, category select, date, description) but
  pre-filled with the expense's current values, extends `base.html`, posts
  to `{{ url_for('edit_expense', id=expense.id) }}`, and renders a
  `{{ error }}` block above the form on validation failure, following the
  same pattern as `add_expense.html`.
- **Modify:** `templates/profile.html` — add an "Actions" column to the
  transaction table (`profile-table`, around line 58-77) with an "Edit"
  link per row pointing to
  `{{ url_for('edit_expense', id=tx.id) }}`.

## Files to change
- `app.py` — replace the stub `edit_expense(id)` view with `GET`/`POST`
  handling: auth check, ownership check (404 if the expense isn't the
  current user's), form validation (reuse the same amount/category/date
  rules as `add_expense`), update, redirect.
- `database/queries.py` — add:
  - `get_expense_by_id(expense_id, user_id)` — parameterised `SELECT`
    scoped to `user_id` so one user can never fetch another's expense;
    returns `None` if not found.
  - `update_expense(expense_id, user_id, amount, category, expense_date,
    description)` — parameterised `UPDATE ... WHERE id = ? AND user_id = ?`
    (scoping the `WHERE` by `user_id`, not just the app-level check, so the
    query itself can never touch another user's row).
  - `get_recent_transactions` — add `id` to the `SELECT` and the returned
    dict so `profile.html` has an id to link to for each row.
- `templates/profile.html` — add the "Actions"/"Edit" column.

## Files to create
- `templates/edit_expense.html`

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
  `Bills`, `Health`, `Entertainment`, `Shopping`, `Other` (same list as
  `EXPENSE_CATEGORIES` in `app.py`)
- `amount` must be validated server-side as a positive number (reject zero,
  negative, or non-numeric input), same as `add_expense`
- `date` must be validated server-side as a valid ISO date (`YYYY-MM-DD`,
  reuse `date.fromisoformat`); reject invalid/missing dates
- `description` is optional; store `NULL`/empty rather than requiring text
- On validation failure, re-render `edit_expense.html` with a friendly
  error via `{% if error %}` and preserve the user's submitted values in
  the form fields rather than clearing them
- Every lookup and update must be scoped to `session["user_id"]` — never
  trust the `id` in the URL alone; a logged-in user must never be able to
  view or modify another user's expense (return 404, not 403, to avoid
  confirming the row exists)
- On success, redirect to `/profile`
- Do not commit `spendly.db` with test expense data from manual testing

## Definition of done
- [ ] Visiting `/expenses/<id>/edit` while logged out redirects to `/login`
- [ ] Visiting `/expenses/<id>/edit` for an expense that belongs to another
      user (or doesn't exist) returns a 404
- [ ] Visiting `/expenses/<id>/edit` for your own expense shows a form
      pre-filled with its current amount, category, date, and description
- [ ] Submitting valid changes updates the row in `expenses` and redirects
      to `/profile`
- [ ] The updated expense's new values appear in the profile page's
      transaction list and are reflected in `total_spent`/
      `transaction_count`/category breakdown
- [ ] Submitting a negative, zero, or non-numeric amount shows an error and
      does not update the row
- [ ] Submitting an invalid or missing date shows an error and does not
      update the row
- [ ] The profile page's transaction list has a working "Edit" link per row
      that goes to the correct expense's edit page
- [ ] App starts without errors and existing routes (`/`, `/login`,
      `/profile`, `/expenses/add`, `/analytics`) are unaffected
