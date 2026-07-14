# Spec: Delete Expense

## Overview
This step implements expense deletion for Spendly. The `expenses` table,
`GET /profile` (which lists transactions with an "Edit" action per row),
and `/expenses/<int:id>/edit` already exist, but
`/expenses/<int:id>/delete` is currently a stub route that returns the
placeholder text `"Delete expense — coming in Step 9"`. This step replaces
that stub with a real handler so logged-in users can permanently remove one
of their own expenses from their profile page's transaction list, with the
change immediately reflected in the transaction list, summary stats, and
category breakdown.

## Depends on
- Step 1: Database setup (`expenses` table, `get_db()`)
- Step 3: Login / Logout (`session["user_id"]` is set on login)
- Step 5: Backend routes profile page (`database/queries.py` reads from
  `expenses`)
- Step 8: Edit expense (`get_expense_by_id`, the ownership-check pattern,
  and the "Actions" column in `profile.html` this step adds a control to)

## Routes
- `POST /expenses/<int:id>/delete` — delete the expense, redirect to
  `/profile` — logged-in only, and only if the expense belongs to the
  current user

The existing stub is a bare `GET` route; it is replaced with a `POST`-only
route so the delete cannot be triggered by a plain link, browser prefetch,
or crawler. A logged-out user is redirected to `/login` (same pattern as
`GET /profile`). If the expense does not exist, or exists but belongs to a
different user, return a 404 rather than revealing the expense exists.

## Database changes
No database changes. The `expenses` table (`id`, `user_id`, `amount`,
`category`, `date`, `description`, `created_at`) from `database/db.py`
already supports this feature as-is.

## Templates
- **Create:** none.
- **Modify:** `templates/profile.html` — in the existing "Actions" column
  (`profile-col-actions`, around line 75-77), add a small delete form next
  to the "Edit" link: a `<form method="POST" action="{{ url_for('delete_expense', id=tx.id) }}">`
  containing a submit button styled as a text-style link
  (`profile-delete-link`, matching `profile-edit-link`), with an
  `onsubmit="return confirm(...)"` guard asking the user to confirm before
  deleting.

## Files to change
- `app.py` — replace the stub `delete_expense(id)` view (currently a bare
  `GET` route with no auth/ownership check) with a `POST`-only handler:
  auth check (redirect to `/login` if logged out), ownership check (404 if
  the expense isn't the current user's, reusing `get_expense_by_id`),
  delete, redirect to `/profile`.
- `database/queries.py` — add `delete_expense(expense_id, user_id)` —
  parameterised `DELETE FROM expenses WHERE id = ? AND user_id = ?`
  (scoping the `WHERE` by `user_id`, not just the app-level check, so the
  query itself can never touch another user's row).
- `templates/profile.html` — add the delete form/button to the "Actions"
  column.

## Files to create
No new files.

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
- Delete must be a `POST` request, never a `GET` — a link alone must not be
  able to trigger deletion
- Every lookup and delete must be scoped to `session["user_id"]` — never
  trust the `id` in the URL alone; a logged-in user must never be able to
  delete another user's expense (return 404, not 403, to avoid confirming
  the row exists)
- Ask for confirmation client-side (e.g. `confirm()`) before submitting the
  delete form, so a stray click can't silently remove an expense
- Deleting a non-existent or already-deleted expense (e.g. double submit)
  must return 404, not throw a server error
- On success, redirect to `/profile`
- Do not commit `spendly.db` with test expense data from manual testing

## Definition of done
- [ ] Visiting/POSTing `/expenses/<id>/delete` while logged out redirects to
      `/login`
- [ ] POSTing `/expenses/<id>/delete` for an expense that belongs to another
      user (or doesn't exist) returns a 404
- [ ] A `GET` request to `/expenses/<id>/delete` no longer works (405, since
      the route is `POST`-only)
- [ ] The profile page's transaction list has a working "Delete" control per
      row that prompts for confirmation before submitting
- [ ] Confirming delete removes the row from `expenses` and redirects to
      `/profile`
- [ ] After deletion, the removed expense no longer appears in the profile
      page's transaction list, and `total_spent`/`transaction_count`/
      category breakdown reflect its removal
- [ ] Deleting the same expense twice (e.g. via a stale form resubmit)
      returns a 404 on the second attempt instead of crashing
- [ ] App starts without errors and existing routes (`/`, `/login`,
      `/profile`, `/expenses/add`, `/expenses/<id>/edit`, `/analytics`) are
      unaffected
