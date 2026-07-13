"""
Tests for Step 7: Add Expense.

Spec: .claude/specs/07-add-expense.md

`GET /expenses/add` renders a form (amount, category, date, description) for
logged-in users. `POST /expenses/add` validates the input server-side and,
on success, inserts a new row into `expenses` for the *session's* user_id
and redirects to `/profile`, where the new expense immediately shows up in
the transaction list, summary stats, and category breakdown. Both methods
must redirect a logged-out user to `/login`. Validation failures (bad
amount, bad category, bad date) must re-render the form with an error and
must NOT create a row; the user's submitted values must be preserved.

These tests are written from the spec only — assertions avoid depending on
exact implementation details (e.g. exact error wording) beyond what the
spec itself states (fixed category dropdown, ISO date validation, optional
description, session-trusted user_id, error-rendering pattern matching
login.html/register.html).
"""

import pytest

from database.db import get_db
from database.queries import (
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

# Seeded demo user baseline (matches tests/test_backend_connection.py).
SEED_ALLTIME_TOTAL = 374.99
SEED_ALLTIME_COUNT = 8

HAPPY_AMOUNT = 42.50
HAPPY_CATEGORY = "Food"
HAPPY_DATE = "2026-07-20"
HAPPY_DESCRIPTION = "Team lunch"


def _valid_form(**overrides):
    data = {
        "amount": str(HAPPY_AMOUNT),
        "category": HAPPY_CATEGORY,
        "date": HAPPY_DATE,
        "description": HAPPY_DESCRIPTION,
    }
    data.update(overrides)
    return data


def _expense_count():
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
    conn.close()
    return count


# ---------------------------------------------------------------- #
# Auth guard                                                        #
# ---------------------------------------------------------------- #

def test_add_expense_get_requires_login(client):
    resp = client.get("/expenses/add")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_add_expense_post_requires_login(client):
    before = _expense_count()
    resp = client.post("/expenses/add", data=_valid_form())

    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
    assert _expense_count() == before, "Logged-out POST must not create a row"


# ---------------------------------------------------------------- #
# GET happy path — form is shown to a logged-in user                 #
# ---------------------------------------------------------------- #

def test_add_expense_get_authenticated_shows_form(client, login, seed_user_id):
    login(seed_user_id)
    resp = client.get("/expenses/add")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "add expense" in body.lower()
    assert 'name="amount"' in body
    assert 'name="category"' in body
    assert 'name="date"' in body
    assert 'name="description"' in body
    assert 'action="/expenses/add"' in body

    for category in EXPENSE_CATEGORIES:
        assert category in body, f"Expected fixed category '{category}' in dropdown"


# ---------------------------------------------------------------- #
# POST happy path — valid data creates a row and redirects           #
# ---------------------------------------------------------------- #

def test_add_expense_valid_data_redirects_to_profile(client, login, fresh_user):
    user_id, _ = fresh_user
    login(user_id)

    resp = client.post("/expenses/add", data=_valid_form())

    assert resp.status_code == 302
    assert "/profile" in resp.headers["Location"]


def test_add_expense_valid_data_creates_row_for_correct_user(client, login, fresh_user):
    user_id, _ = fresh_user
    login(user_id)

    before = _expense_count()
    client.post("/expenses/add", data=_valid_form())
    assert _expense_count() == before + 1

    stats = get_summary_stats(user_id)
    assert stats["total_spent"] == HAPPY_AMOUNT
    assert stats["transaction_count"] == 1
    assert stats["top_category"] == HAPPY_CATEGORY

    txs = get_recent_transactions(user_id)
    assert len(txs) == 1
    assert txs[0]["amount"] == HAPPY_AMOUNT
    assert txs[0]["category"] == HAPPY_CATEGORY
    assert txs[0]["date"] == HAPPY_DATE
    assert txs[0]["description"] == HAPPY_DESCRIPTION

    breakdown = get_category_breakdown(user_id)
    assert len(breakdown) == 1
    assert breakdown[0]["name"] == HAPPY_CATEGORY
    assert breakdown[0]["pct"] == 100


def test_add_expense_appears_on_profile_page(client, login, fresh_user):
    user_id, _ = fresh_user
    login(user_id)

    client.post("/expenses/add", data=_valid_form())
    resp = client.get("/profile")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert HAPPY_DESCRIPTION in body, "New expense description should show in transaction list"
    assert HAPPY_CATEGORY in body, "New expense category should show in breakdown/list"
    assert f"{HAPPY_AMOUNT:.2f}" in body, "New expense amount should be reflected in totals/list"


def test_add_expense_added_on_top_of_existing_seed_data(client, login, seed_user_id):
    """Adding an expense to a user who already has expenses should extend,
    not replace, their existing stats."""
    login(seed_user_id)

    client.post("/expenses/add", data=_valid_form())

    stats = get_summary_stats(seed_user_id)
    assert stats["transaction_count"] == SEED_ALLTIME_COUNT + 1
    assert round(stats["total_spent"], 2) == round(SEED_ALLTIME_TOTAL + HAPPY_AMOUNT, 2)


# ---------------------------------------------------------------- #
# Optional description                                              #
# ---------------------------------------------------------------- #

def test_add_expense_without_description_succeeds(client, login, fresh_user):
    user_id, _ = fresh_user
    login(user_id)

    data = _valid_form()
    del data["description"]

    resp = client.post("/expenses/add", data=data)
    assert resp.status_code == 302
    assert "/profile" in resp.headers["Location"]

    txs = get_recent_transactions(user_id)
    assert len(txs) == 1
    assert not txs[0]["description"], "Missing description should store NULL/empty, not raise"


def test_add_expense_without_description_displays_on_profile(client, login, fresh_user):
    user_id, _ = fresh_user
    login(user_id)

    data = _valid_form()
    data["description"] = ""

    resp = client.post("/expenses/add", data=data, follow_redirects=True)
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert HAPPY_CATEGORY in body
    assert f"{HAPPY_AMOUNT:.2f}" in body


# ---------------------------------------------------------------- #
# Validation: amount                                                #
# ---------------------------------------------------------------- #

@pytest.mark.parametrize(
    "bad_amount",
    ["not-a-number", "abc", "0", "0.0", "-5", "-0.01", ""],
    ids=["non-numeric", "letters", "zero", "zero-float", "negative", "small-negative", "empty"],
)
def test_add_expense_invalid_amount_shows_error_and_no_row(client, login, fresh_user, bad_amount):
    user_id, _ = fresh_user
    login(user_id)

    before = _expense_count()
    resp = client.post("/expenses/add", data=_valid_form(amount=bad_amount))
    body = resp.get_data(as_text=True)

    assert resp.status_code == 400, f"Invalid amount {bad_amount!r} should not succeed"
    assert "auth-error" in body, "Expected an error message rendered (same pattern as login/register)"
    assert _expense_count() == before, "No expense row should be created for an invalid amount"


def test_add_expense_missing_amount_field_shows_error_and_no_row(client, login, fresh_user):
    user_id, _ = fresh_user
    login(user_id)

    data = _valid_form()
    del data["amount"]

    before = _expense_count()
    resp = client.post("/expenses/add", data=data)

    assert resp.status_code == 400
    assert _expense_count() == before


# ---------------------------------------------------------------- #
# Validation: category                                              #
# ---------------------------------------------------------------- #

@pytest.mark.parametrize(
    "bad_category",
    ["", "food", "Groceries", "NotACategory", "<script>alert(1)</script>"],
    ids=["empty", "wrong-case", "not-in-list", "unknown", "injection-like"],
)
def test_add_expense_invalid_category_shows_error_and_no_row(client, login, fresh_user, bad_category):
    user_id, _ = fresh_user
    login(user_id)

    before = _expense_count()
    resp = client.post("/expenses/add", data=_valid_form(category=bad_category))
    body = resp.get_data(as_text=True)

    assert resp.status_code == 400, f"Invalid category {bad_category!r} should not succeed"
    assert "auth-error" in body
    assert _expense_count() == before


def test_add_expense_missing_category_field_shows_error_and_no_row(client, login, fresh_user):
    user_id, _ = fresh_user
    login(user_id)

    data = _valid_form()
    del data["category"]

    before = _expense_count()
    resp = client.post("/expenses/add", data=data)

    assert resp.status_code == 400
    assert _expense_count() == before


# ---------------------------------------------------------------- #
# Validation: date                                                  #
# ---------------------------------------------------------------- #

@pytest.mark.parametrize(
    "bad_date",
    ["notadate", "2026-13-40", "07-20-2026", "2026/07/20", ""],
    ids=["non-date-text", "invalid-month-day", "wrong-format", "slashes", "empty"],
)
def test_add_expense_invalid_date_shows_error_and_no_row(client, login, fresh_user, bad_date):
    user_id, _ = fresh_user
    login(user_id)

    before = _expense_count()
    resp = client.post("/expenses/add", data=_valid_form(date=bad_date))
    body = resp.get_data(as_text=True)

    assert resp.status_code == 400, f"Invalid date {bad_date!r} should not succeed"
    assert "auth-error" in body
    assert _expense_count() == before


def test_add_expense_missing_date_field_shows_error_and_no_row(client, login, fresh_user):
    user_id, _ = fresh_user
    login(user_id)

    data = _valid_form()
    del data["date"]

    before = _expense_count()
    resp = client.post("/expenses/add", data=data)

    assert resp.status_code == 400
    assert _expense_count() == before


# ---------------------------------------------------------------- #
# Validation failure preserves submitted values                     #
# ---------------------------------------------------------------- #

def test_add_expense_validation_failure_preserves_submitted_values(client, login, fresh_user):
    user_id, _ = fresh_user
    login(user_id)

    resp = client.post(
        "/expenses/add",
        data=_valid_form(amount="not-a-number", description="Preserve me please"),
    )
    body = resp.get_data(as_text=True)

    assert resp.status_code == 400
    assert "Preserve me please" in body, "Description should be preserved, not cleared, on error"
    assert HAPPY_DATE in body, "Date should be preserved, not cleared, on error"
    assert HAPPY_CATEGORY in body, "Category selection should be preserved, not cleared, on error"


# ---------------------------------------------------------------- #
# DB side effect: session user_id is trusted, never a client value   #
# ---------------------------------------------------------------- #

def test_add_expense_ignores_client_supplied_user_id(client, login, fresh_user, seed_user_id):
    """A malicious/incorrect user_id in the POST body must be ignored; the
    expense must be attributed to whoever is logged in via session."""
    user_id, _ = fresh_user
    login(user_id)

    seed_stats_before = get_summary_stats(seed_user_id)

    resp = client.post("/expenses/add", data=_valid_form(user_id=str(seed_user_id)))
    assert resp.status_code == 302

    own_stats = get_summary_stats(user_id)
    assert own_stats["transaction_count"] == 1, "Expense must be attributed to the logged-in user"
    assert own_stats["total_spent"] == HAPPY_AMOUNT

    seed_stats_after = get_summary_stats(seed_user_id)
    assert seed_stats_after == seed_stats_before, "Other user's stats must be unaffected by a spoofed user_id"


def test_add_expense_does_not_leak_into_other_users_transaction_list(client, login, fresh_user, seed_user_id):
    user_id, _ = fresh_user
    login(user_id)

    client.post("/expenses/add", data=_valid_form())

    seed_txs = get_recent_transactions(seed_user_id)
    descriptions = {t["description"] for t in seed_txs}
    assert HAPPY_DESCRIPTION not in descriptions, "New expense must not appear under another user's transactions"


# ---------------------------------------------------------------- #
# Profile page has a link/button to the add-expense form             #
# ---------------------------------------------------------------- #

def test_profile_page_has_add_expense_link(client, login, seed_user_id):
    login(seed_user_id)
    resp = client.get("/profile")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert 'href="/expenses/add"' in body, "Profile page should link to the add-expense form"
