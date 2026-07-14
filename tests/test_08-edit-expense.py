"""
Tests for Step 8: Edit Expense.

Spec: .claude/specs/08-edit-expense.md

`GET /expenses/<id>/edit` renders a form (amount, category, date,
description) pre-filled with an existing expense's values, for logged-in
users, and only if the expense belongs to them. `POST /expenses/<id>/edit`
validates the input server-side (same rules as add-expense) and, on
success, updates the row in `expenses` and redirects to `/profile`, where
the change is immediately reflected in the transaction list, summary
stats, and category breakdown. Both methods must redirect a logged-out
user to `/login`. If the expense does not exist, or belongs to a
different user, the route must return a 404 rather than revealing the
expense exists. Validation failures (bad amount, bad category, bad date)
must re-render the form with an error and must NOT modify the row; the
user's submitted values must be preserved.

These tests are written from the spec only — assertions avoid depending on
exact implementation details (e.g. exact error wording) beyond what the
spec itself states (fixed category dropdown, ISO date validation, optional
description, session-trusted user_id, ownership scoped to session user,
404-not-403 on cross-user access, error-rendering pattern matching
add_expense.html/login.html/register.html).
"""

import re

import pytest

from database.db import get_db
from database.queries import (
    create_expense,
    get_expense_by_id,
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)

# ---------------------------------------------------------------- #
# Ground truth / fixed spec values                                  #
# ---------------------------------------------------------------- #

# Fixed category dropdown from the spec (must match seed_db() categories).
EXPENSE_CATEGORIES = [
    "Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other",
]

ORIGINAL_AMOUNT = 15.75
ORIGINAL_CATEGORY = "Transport"
ORIGINAL_DATE = "2026-06-01"
ORIGINAL_DESCRIPTION = "Bus fare"

NEW_AMOUNT = 88.20
NEW_CATEGORY = "Entertainment"
NEW_DATE = "2026-07-10"
NEW_DESCRIPTION = "Concert tickets"


def _valid_form(**overrides):
    data = {
        "amount": str(NEW_AMOUNT),
        "category": NEW_CATEGORY,
        "date": NEW_DATE,
        "description": NEW_DESCRIPTION,
    }
    data.update(overrides)
    return data


def _make_expense(user_id, amount=ORIGINAL_AMOUNT, category=ORIGINAL_CATEGORY,
                   expense_date=ORIGINAL_DATE, description=ORIGINAL_DESCRIPTION):
    return create_expense(user_id, amount, category, expense_date, description)


def _edit_url(expense_id):
    return f"/expenses/{expense_id}/edit"


def _row_by_id(expense_id):
    """Fetch a raw row regardless of owner, to verify a row was/was not
    modified without assuming which query helpers exist beyond the spec."""
    conn = get_db()
    row = conn.execute(
        "SELECT id, user_id, amount, category, date, description FROM expenses WHERE id = ?",
        (expense_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def _selected_option_pattern(category):
    """Matches an <option> tag for `category` carrying a `selected` marker,
    regardless of attribute ordering."""
    escaped = re.escape(category)
    return re.compile(
        rf'<option[^>]*value="{escaped}"[^>]*selected|<option[^>]*selected[^>]*value="{escaped}"'
    )


# ---------------------------------------------------------------- #
# Auth guard                                                        #
# ---------------------------------------------------------------- #

def test_edit_expense_get_requires_login(client, seed_user_id):
    expense_id = _make_expense(seed_user_id)
    resp = client.get(_edit_url(expense_id))

    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_edit_expense_post_requires_login(client, seed_user_id):
    expense_id = _make_expense(seed_user_id)
    before = _row_by_id(expense_id)

    resp = client.post(_edit_url(expense_id), data=_valid_form())

    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
    assert _row_by_id(expense_id) == before, "Logged-out POST must not modify the row"


# ---------------------------------------------------------------- #
# Ownership / 404                                                   #
# ---------------------------------------------------------------- #

def test_edit_expense_get_nonexistent_id_returns_404(client, login, seed_user_id):
    login(seed_user_id)
    resp = client.get(_edit_url(999999))
    assert resp.status_code == 404


def test_edit_expense_post_nonexistent_id_returns_404(client, login, seed_user_id):
    login(seed_user_id)
    resp = client.post(_edit_url(999999), data=_valid_form())
    assert resp.status_code == 404


def test_edit_expense_get_other_users_expense_returns_404(client, login, fresh_user, seed_user_id):
    """A logged-in user must not be able to view another user's expense
    edit form; the response must be a 404, not a redirect or 200."""
    other_user_id, _ = fresh_user
    victim_expense_id = _make_expense(seed_user_id)

    login(other_user_id)
    resp = client.get(_edit_url(victim_expense_id))

    assert resp.status_code == 404
    assert resp.status_code != 302, "Must not silently redirect for another user's expense"


def test_edit_expense_post_other_users_expense_returns_404(client, login, fresh_user, seed_user_id):
    other_user_id, _ = fresh_user
    victim_expense_id = _make_expense(seed_user_id)
    before = _row_by_id(victim_expense_id)

    login(other_user_id)
    resp = client.post(_edit_url(victim_expense_id), data=_valid_form())

    assert resp.status_code == 404
    assert _row_by_id(victim_expense_id) == before, "Row must be unchanged after a blocked cross-user edit"


def test_edit_expense_ownership_check_is_bidirectional(client, login, fresh_user, seed_user_id):
    """Confirm blocking works in both directions: seed user cannot edit a
    fresh user's expense either."""
    other_user_id, _ = fresh_user
    fresh_expense_id = _make_expense(other_user_id)
    before = _row_by_id(fresh_expense_id)

    login(seed_user_id)
    get_resp = client.get(_edit_url(fresh_expense_id))
    post_resp = client.post(_edit_url(fresh_expense_id), data=_valid_form())

    assert get_resp.status_code == 404
    assert post_resp.status_code == 404
    assert _row_by_id(fresh_expense_id) == before


# ---------------------------------------------------------------- #
# GET happy path — form is pre-filled for the owning user            #
# ---------------------------------------------------------------- #

def test_edit_expense_get_own_expense_shows_prefilled_form(client, login, fresh_user):
    user_id, _ = fresh_user
    expense_id = _make_expense(user_id)

    login(user_id)
    resp = client.get(_edit_url(expense_id))
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "edit" in body.lower()
    assert 'name="amount"' in body
    assert 'name="category"' in body
    assert 'name="date"' in body
    assert 'name="description"' in body
    assert f'action="{_edit_url(expense_id)}"' in body

    # Amount pre-filled (substring match tolerates "15.75" vs "15.750" style formatting).
    assert str(ORIGINAL_AMOUNT) in body, "Amount field should be pre-filled with the current value"

    # Category pre-selected in the dropdown.
    assert _selected_option_pattern(ORIGINAL_CATEGORY).search(body), \
        "Current category should be marked selected in the dropdown"

    # Date and description pre-filled.
    assert ORIGINAL_DATE in body, "Date field should be pre-filled with the current value"
    assert ORIGINAL_DESCRIPTION in body, "Description field should be pre-filled with the current value"

    # All fixed categories still present in the dropdown.
    for category in EXPENSE_CATEGORIES:
        assert category in body, f"Expected fixed category '{category}' in dropdown"


# ---------------------------------------------------------------- #
# POST happy path — valid data updates the row and redirects         #
# ---------------------------------------------------------------- #

def test_edit_expense_valid_data_redirects_to_profile(client, login, fresh_user):
    user_id, _ = fresh_user
    expense_id = _make_expense(user_id)

    login(user_id)
    resp = client.post(_edit_url(expense_id), data=_valid_form())

    assert resp.status_code == 302
    assert "/profile" in resp.headers["Location"]


def test_edit_expense_valid_data_updates_row_and_reflects_in_queries(client, login, fresh_user):
    user_id, _ = fresh_user
    expense_id = _make_expense(user_id)

    login(user_id)
    client.post(_edit_url(expense_id), data=_valid_form())

    updated = get_expense_by_id(expense_id, user_id)
    assert updated is not None
    assert updated["amount"] == NEW_AMOUNT
    assert updated["category"] == NEW_CATEGORY
    assert updated["date"] == NEW_DATE
    assert updated["description"] == NEW_DESCRIPTION

    stats = get_summary_stats(user_id)
    assert stats["total_spent"] == NEW_AMOUNT
    assert stats["transaction_count"] == 1, "Editing must not change the number of rows"
    assert stats["top_category"] == NEW_CATEGORY

    txs = get_recent_transactions(user_id)
    assert len(txs) == 1
    assert txs[0]["amount"] == NEW_AMOUNT
    assert txs[0]["category"] == NEW_CATEGORY
    assert txs[0]["date"] == NEW_DATE
    assert txs[0]["description"] == NEW_DESCRIPTION

    breakdown = get_category_breakdown(user_id)
    assert len(breakdown) == 1
    assert breakdown[0]["name"] == NEW_CATEGORY
    assert breakdown[0]["pct"] == 100


def test_edit_expense_updated_values_appear_on_profile_page(client, login, fresh_user):
    user_id, _ = fresh_user
    expense_id = _make_expense(user_id)

    login(user_id)
    client.post(_edit_url(expense_id), data=_valid_form())
    resp = client.get("/profile")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert NEW_DESCRIPTION in body, "Updated description should show in the transaction list"
    assert NEW_CATEGORY in body, "Updated category should show in the breakdown/list"
    assert f"{NEW_AMOUNT:.2f}" in body, "Updated amount should be reflected in totals/list"
    assert ORIGINAL_DESCRIPTION not in body, "Stale description should no longer appear"


def test_edit_expense_does_not_change_transaction_count_for_existing_seed_data(client, login, seed_user_id):
    """Editing one of several existing expenses should update that row only,
    not add or remove rows."""
    login(seed_user_id)
    stats_before = get_summary_stats(seed_user_id)
    txs_before = get_recent_transactions(seed_user_id, limit=100)
    target_id = txs_before[0]["id"]

    client.post(_edit_url(target_id), data=_valid_form())

    stats_after = get_summary_stats(seed_user_id)
    assert stats_after["transaction_count"] == stats_before["transaction_count"]


# ---------------------------------------------------------------- #
# Optional description                                              #
# ---------------------------------------------------------------- #

def test_edit_expense_without_description_succeeds(client, login, fresh_user):
    user_id, _ = fresh_user
    expense_id = _make_expense(user_id)

    login(user_id)
    data = _valid_form()
    data["description"] = ""

    resp = client.post(_edit_url(expense_id), data=data)
    assert resp.status_code == 302
    assert "/profile" in resp.headers["Location"]

    updated = get_expense_by_id(expense_id, user_id)
    assert not updated["description"], "Empty description should store NULL/empty, not raise"


def test_edit_expense_missing_description_field_succeeds(client, login, fresh_user):
    user_id, _ = fresh_user
    expense_id = _make_expense(user_id)

    login(user_id)
    data = _valid_form()
    del data["description"]

    resp = client.post(_edit_url(expense_id), data=data)
    assert resp.status_code == 302

    updated = get_expense_by_id(expense_id, user_id)
    assert not updated["description"]


# ---------------------------------------------------------------- #
# Validation: amount                                                #
# ---------------------------------------------------------------- #

@pytest.mark.parametrize(
    "bad_amount",
    ["not-a-number", "abc", "0", "0.0", "-5", "-0.01", ""],
    ids=["non-numeric", "letters", "zero", "zero-float", "negative", "small-negative", "empty"],
)
def test_edit_expense_invalid_amount_shows_error_and_leaves_row_unchanged(client, login, fresh_user, bad_amount):
    user_id, _ = fresh_user
    expense_id = _make_expense(user_id)
    before = _row_by_id(expense_id)

    login(user_id)
    resp = client.post(_edit_url(expense_id), data=_valid_form(amount=bad_amount))
    body = resp.get_data(as_text=True)

    assert resp.status_code == 400, f"Invalid amount {bad_amount!r} should not succeed"
    assert "auth-error" in body, "Expected an error message rendered (same pattern as add_expense/login/register)"
    assert _row_by_id(expense_id) == before, "No changes should be persisted for an invalid amount"


def test_edit_expense_missing_amount_field_shows_error_and_leaves_row_unchanged(client, login, fresh_user):
    user_id, _ = fresh_user
    expense_id = _make_expense(user_id)
    before = _row_by_id(expense_id)

    login(user_id)
    data = _valid_form()
    del data["amount"]

    resp = client.post(_edit_url(expense_id), data=data)

    assert resp.status_code == 400
    assert _row_by_id(expense_id) == before


# ---------------------------------------------------------------- #
# Validation: category                                              #
# ---------------------------------------------------------------- #

@pytest.mark.parametrize(
    "bad_category",
    ["", "food", "Groceries", "NotACategory", "<script>alert(1)</script>"],
    ids=["empty", "wrong-case", "not-in-list", "unknown", "injection-like"],
)
def test_edit_expense_invalid_category_shows_error_and_leaves_row_unchanged(client, login, fresh_user, bad_category):
    user_id, _ = fresh_user
    expense_id = _make_expense(user_id)
    before = _row_by_id(expense_id)

    login(user_id)
    resp = client.post(_edit_url(expense_id), data=_valid_form(category=bad_category))
    body = resp.get_data(as_text=True)

    assert resp.status_code == 400, f"Invalid category {bad_category!r} should not succeed"
    assert "auth-error" in body
    assert _row_by_id(expense_id) == before


def test_edit_expense_missing_category_field_shows_error_and_leaves_row_unchanged(client, login, fresh_user):
    user_id, _ = fresh_user
    expense_id = _make_expense(user_id)
    before = _row_by_id(expense_id)

    login(user_id)
    data = _valid_form()
    del data["category"]

    resp = client.post(_edit_url(expense_id), data=data)

    assert resp.status_code == 400
    assert _row_by_id(expense_id) == before


# ---------------------------------------------------------------- #
# Validation: date                                                  #
# ---------------------------------------------------------------- #

@pytest.mark.parametrize(
    "bad_date",
    ["notadate", "2026-13-40", "07-20-2026", "2026/07/20", ""],
    ids=["non-date-text", "invalid-month-day", "wrong-format", "slashes", "empty"],
)
def test_edit_expense_invalid_date_shows_error_and_leaves_row_unchanged(client, login, fresh_user, bad_date):
    user_id, _ = fresh_user
    expense_id = _make_expense(user_id)
    before = _row_by_id(expense_id)

    login(user_id)
    resp = client.post(_edit_url(expense_id), data=_valid_form(date=bad_date))
    body = resp.get_data(as_text=True)

    assert resp.status_code == 400, f"Invalid date {bad_date!r} should not succeed"
    assert "auth-error" in body
    assert _row_by_id(expense_id) == before


def test_edit_expense_missing_date_field_shows_error_and_leaves_row_unchanged(client, login, fresh_user):
    user_id, _ = fresh_user
    expense_id = _make_expense(user_id)
    before = _row_by_id(expense_id)

    login(user_id)
    data = _valid_form()
    del data["date"]

    resp = client.post(_edit_url(expense_id), data=data)

    assert resp.status_code == 400
    assert _row_by_id(expense_id) == before


# ---------------------------------------------------------------- #
# Validation failure preserves submitted values                     #
# ---------------------------------------------------------------- #

def test_edit_expense_validation_failure_preserves_submitted_values(client, login, fresh_user):
    user_id, _ = fresh_user
    expense_id = _make_expense(user_id)

    login(user_id)
    resp = client.post(
        _edit_url(expense_id),
        data=_valid_form(amount="not-a-number", description="Preserve me please"),
    )
    body = resp.get_data(as_text=True)

    assert resp.status_code == 400
    assert "Preserve me please" in body, "Description should be preserved, not cleared, on error"
    assert NEW_DATE in body, "Date should be preserved, not cleared, on error"
    assert NEW_CATEGORY in body, "Category selection should be preserved, not cleared, on error"


# ---------------------------------------------------------------- #
# DB side effect: session user_id is trusted, never a client value   #
# ---------------------------------------------------------------- #

def test_edit_expense_ignores_client_supplied_user_id(client, login, fresh_user, seed_user_id):
    """A malicious/incorrect user_id in the POST body must be ignored; the
    update must apply to the session's user and must never move the row to
    (or otherwise affect) another user's account."""
    user_id, _ = fresh_user
    expense_id = _make_expense(user_id)
    seed_stats_before = get_summary_stats(seed_user_id)

    login(user_id)
    resp = client.post(_edit_url(expense_id), data=_valid_form(user_id=str(seed_user_id)))
    assert resp.status_code == 302

    # The expense must still belong to (and be updated for) the logged-in user.
    own_view = get_expense_by_id(expense_id, user_id)
    assert own_view is not None
    assert own_view["amount"] == NEW_AMOUNT
    assert own_view["category"] == NEW_CATEGORY

    # It must never become visible/attributed under the spoofed user_id.
    seed_stats_after = get_summary_stats(seed_user_id)
    assert seed_stats_after == seed_stats_before, "Spoofed user_id must not affect another user's stats"

    row = _row_by_id(expense_id)
    assert row["user_id"] == user_id, "Row ownership must remain the session user, never the spoofed id"


def test_edit_expense_update_does_not_leak_into_other_users_data(client, login, fresh_user, seed_user_id):
    user_id, _ = fresh_user
    expense_id = _make_expense(user_id)
    seed_stats_before = get_summary_stats(seed_user_id)
    seed_txs_before = get_recent_transactions(seed_user_id, limit=100)

    login(user_id)
    client.post(_edit_url(expense_id), data=_valid_form())

    seed_stats_after = get_summary_stats(seed_user_id)
    seed_txs_after = get_recent_transactions(seed_user_id, limit=100)

    assert seed_stats_after == seed_stats_before, "Editing one user's expense must not affect another user's stats"
    assert seed_txs_after == seed_txs_before, "Editing one user's expense must not affect another user's transactions"


# ---------------------------------------------------------------- #
# Profile page has a working Edit link per row                      #
# ---------------------------------------------------------------- #

def test_profile_page_has_edit_link_for_expense(client, login, fresh_user):
    user_id, _ = fresh_user
    expense_id = _make_expense(user_id)

    login(user_id)
    resp = client.get("/profile")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert f'href="{_edit_url(expense_id)}"' in body, \
        "Profile page's transaction row should link to that expense's edit page"


def test_profile_page_edit_links_point_to_correct_expense_ids(client, login, fresh_user):
    """With multiple expenses, each row's Edit link must reference its own
    expense id, not just any/the first one."""
    user_id, _ = fresh_user
    id_a = _make_expense(user_id, description="Expense A", expense_date="2026-06-01")
    id_b = _make_expense(user_id, description="Expense B", expense_date="2026-06-02")

    login(user_id)
    resp = client.get("/profile")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert f'href="{_edit_url(id_a)}"' in body
    assert f'href="{_edit_url(id_b)}"' in body
