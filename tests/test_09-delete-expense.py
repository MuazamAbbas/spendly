"""
Tests for Step 9: Delete Expense.

Spec: .claude/specs/09-delete-expense.md

`POST /expenses/<id>/delete` permanently removes one of the logged-in
user's own expenses and redirects to `/profile`. The route is POST-only —
a bare `GET` must no longer work (405), so the delete can't be triggered
by a plain link, browser prefetch, or crawler. A logged-out request
redirects to `/login` and must not modify any row. If the expense does
not exist, or belongs to a different user, the route must return a 404
(not a 403, not a redirect) rather than revealing the expense exists —
every lookup/delete must be scoped to `session["user_id"]`, never a
client-supplied value. After a successful delete, the removed expense
must no longer appear in the transaction list, and `total_spent`/
`transaction_count`/category breakdown must reflect its removal.
Double-submitting a delete (e.g. a stale form resubmit) must return 404
on the second attempt, not a server error. The profile page's "Actions"
column must have a working per-row delete control (a form posting to
that row's own delete URL) with a confirmation prompt before submitting.

These tests are written from the spec only — assertions avoid depending
on exact implementation details beyond what the spec itself states
(POST-only route, 404-not-403/redirect on cross-user or missing access,
session-scoped ownership, `profile-delete-link`/`profile-col-actions`
class names and the `url_for('delete_expense', id=tx.id)` action pattern
named explicitly in the spec, confirm() guard on submit).
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

AMOUNT = 42.50
CATEGORY = "Food"
DATE = "2026-06-15"
DESCRIPTION = "Groceries"


def _make_expense(user_id, amount=AMOUNT, category=CATEGORY,
                   expense_date=DATE, description=DESCRIPTION):
    return create_expense(user_id, amount, category, expense_date, description)


def _delete_url(expense_id):
    return f"/expenses/{expense_id}/delete"


def _row_by_id(expense_id):
    """Fetch a raw row regardless of owner, to verify a row was/was not
    deleted without assuming which query helpers exist beyond the spec."""
    conn = get_db()
    row = conn.execute(
        "SELECT id, user_id, amount, category, date, description FROM expenses WHERE id = ?",
        (expense_id,),
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def _delete_form_action_pattern(expense_id):
    """Matches a <form ... action="/expenses/<id>/delete" ...> tag,
    regardless of attribute ordering, per the spec's
    `action="{{ url_for('delete_expense', id=tx.id) }}"` requirement."""
    escaped = re.escape(_delete_url(expense_id))
    return re.compile(rf'<form[^>]*action="{escaped}"')


# ---------------------------------------------------------------- #
# Route method: POST-only                                           #
# ---------------------------------------------------------------- #

def test_delete_expense_get_not_allowed(client, login, fresh_user):
    """The stub GET route is replaced by a POST-only route; a plain GET
    (link/prefetch/crawler) must not be able to trigger a delete."""
    user_id, _ = fresh_user
    expense_id = _make_expense(user_id)

    login(user_id)
    resp = client.get(_delete_url(expense_id))

    assert resp.status_code == 405
    assert _row_by_id(expense_id) is not None, "GET must never delete the row"


def test_delete_expense_get_while_logged_out_is_still_405(client, fresh_user):
    """Method not allowed takes precedence regardless of auth state — a GET
    is simply not a valid way to reach this route."""
    user_id, _ = fresh_user
    expense_id = _make_expense(user_id)

    resp = client.get(_delete_url(expense_id))

    assert resp.status_code == 405
    assert _row_by_id(expense_id) is not None


# ---------------------------------------------------------------- #
# Auth guard                                                        #
# ---------------------------------------------------------------- #

def test_delete_expense_post_requires_login(client, seed_user_id):
    expense_id = _make_expense(seed_user_id)

    resp = client.post(_delete_url(expense_id))

    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]
    assert _row_by_id(expense_id) is not None, "Logged-out POST must not delete the row"


# ---------------------------------------------------------------- #
# Ownership / 404                                                   #
# ---------------------------------------------------------------- #

def test_delete_expense_nonexistent_id_returns_404(client, login, seed_user_id):
    login(seed_user_id)
    resp = client.post(_delete_url(999999))
    assert resp.status_code == 404


def test_delete_expense_other_users_expense_returns_404(client, login, fresh_user, seed_user_id):
    """A logged-in user must not be able to delete another user's expense;
    the response must be a 404, not a redirect, and the row must survive."""
    other_user_id, _ = fresh_user
    victim_expense_id = _make_expense(seed_user_id)

    login(other_user_id)
    resp = client.post(_delete_url(victim_expense_id))

    assert resp.status_code == 404
    assert resp.status_code != 302, "Must not silently redirect for another user's expense"
    assert _row_by_id(victim_expense_id) is not None, "Row must survive a blocked cross-user delete"


def test_delete_expense_ownership_check_is_bidirectional(client, login, fresh_user, seed_user_id):
    """Confirm blocking works in both directions: the seed user cannot
    delete a fresh user's expense either, and vice versa is covered above."""
    other_user_id, _ = fresh_user
    fresh_expense_id = _make_expense(other_user_id)

    login(seed_user_id)
    resp = client.post(_delete_url(fresh_expense_id))

    assert resp.status_code == 404
    assert _row_by_id(fresh_expense_id) is not None


# ---------------------------------------------------------------- #
# POST happy path — deletes the row and redirects                   #
# ---------------------------------------------------------------- #

def test_delete_expense_own_expense_redirects_to_profile(client, login, fresh_user):
    user_id, _ = fresh_user
    expense_id = _make_expense(user_id)

    login(user_id)
    resp = client.post(_delete_url(expense_id))

    assert resp.status_code == 302
    assert "/profile" in resp.headers["Location"]


def test_delete_expense_own_expense_removes_row(client, login, fresh_user):
    user_id, _ = fresh_user
    expense_id = _make_expense(user_id)

    login(user_id)
    client.post(_delete_url(expense_id))

    assert _row_by_id(expense_id) is None, "Row should be permanently removed from expenses"
    assert get_expense_by_id(expense_id, user_id) is None


def test_delete_expense_reflected_in_recent_transactions(client, login, fresh_user):
    user_id, _ = fresh_user
    keep_id = _make_expense(user_id, description="Keep me", expense_date="2026-06-01")
    remove_id = _make_expense(user_id, description="Remove me", expense_date="2026-06-02")

    login(user_id)
    client.post(_delete_url(remove_id))

    txs = get_recent_transactions(user_id, limit=100)
    ids = [t["id"] for t in txs]
    assert remove_id not in ids, "Deleted expense must no longer appear in recent transactions"
    assert keep_id in ids, "Other expenses must remain untouched"


def test_delete_expense_reflected_in_summary_stats(client, login, fresh_user):
    user_id, _ = fresh_user
    _make_expense(user_id, amount=10.00, description="A", expense_date="2026-06-01")
    remove_id = _make_expense(user_id, amount=25.00, description="B", expense_date="2026-06-02")

    stats_before = get_summary_stats(user_id)
    assert stats_before["total_spent"] == pytest.approx(35.00)
    assert stats_before["transaction_count"] == 2

    login(user_id)
    client.post(_delete_url(remove_id))

    stats_after = get_summary_stats(user_id)
    assert stats_after["total_spent"] == pytest.approx(10.00), \
        "total_spent should decrease by the deleted expense's amount"
    assert stats_after["transaction_count"] == 1, \
        "transaction_count should decrease by one after deletion"


def test_delete_expense_reflected_in_category_breakdown(client, login, fresh_user):
    user_id, _ = fresh_user
    _make_expense(user_id, amount=10.00, category="Food", description="A", expense_date="2026-06-01")
    remove_id = _make_expense(user_id, amount=10.00, category="Transport", description="B", expense_date="2026-06-02")

    login(user_id)
    client.post(_delete_url(remove_id))

    breakdown = get_category_breakdown(user_id)
    names = [b["name"] for b in breakdown]
    assert "Transport" not in names, "Deleted category's contribution should no longer appear once its only expense is gone"
    assert "Food" in names


def test_delete_expense_removed_expense_not_on_profile_page(client, login, fresh_user):
    user_id, _ = fresh_user
    remove_id = _make_expense(user_id, description="Vanishing Expense")

    login(user_id)
    client.post(_delete_url(remove_id))
    resp = client.get("/profile")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "Vanishing Expense" not in body, "Deleted expense's description should no longer render on /profile"


def test_delete_expense_does_not_change_transaction_count_of_others(client, login, seed_user_id):
    """Deleting one of several existing (seeded) expenses should remove
    exactly that row, not more or fewer."""
    login(seed_user_id)
    txs_before = get_recent_transactions(seed_user_id, limit=100)
    stats_before = get_summary_stats(seed_user_id)
    target_id = txs_before[0]["id"]

    client.post(_delete_url(target_id))

    stats_after = get_summary_stats(seed_user_id)
    assert stats_after["transaction_count"] == stats_before["transaction_count"] - 1


# ---------------------------------------------------------------- #
# Double submit / already-deleted                                   #
# ---------------------------------------------------------------- #

def test_delete_expense_double_submit_returns_404_on_second_attempt(client, login, fresh_user):
    user_id, _ = fresh_user
    expense_id = _make_expense(user_id)

    login(user_id)
    first = client.post(_delete_url(expense_id))
    second = client.post(_delete_url(expense_id))

    assert first.status_code == 302
    assert second.status_code == 404, "Deleting an already-deleted expense must 404, not crash"


# ---------------------------------------------------------------- #
# Cross-user isolation                                              #
# ---------------------------------------------------------------- #

def test_delete_expense_does_not_leak_into_other_users_data(client, login, fresh_user, seed_user_id):
    user_id, _ = fresh_user
    expense_id = _make_expense(user_id)
    seed_stats_before = get_summary_stats(seed_user_id)
    seed_txs_before = get_recent_transactions(seed_user_id, limit=100)

    login(user_id)
    client.post(_delete_url(expense_id))

    seed_stats_after = get_summary_stats(seed_user_id)
    seed_txs_after = get_recent_transactions(seed_user_id, limit=100)

    assert seed_stats_after == seed_stats_before, "Deleting one user's expense must not affect another user's stats"
    assert seed_txs_after == seed_txs_before, "Deleting one user's expense must not affect another user's transactions"


# ---------------------------------------------------------------- #
# Session user_id is trusted, never a client-supplied value          #
# ---------------------------------------------------------------- #

def test_delete_expense_ignores_client_supplied_user_id_for_own_expense(client, login, fresh_user, seed_user_id):
    """A user_id field spoofed into the POST body must have no effect;
    deletion of the session user's own expense must still succeed, and
    must never be attributed to (or affect) the spoofed user."""
    user_id, _ = fresh_user
    expense_id = _make_expense(user_id)
    seed_stats_before = get_summary_stats(seed_user_id)

    login(user_id)
    resp = client.post(_delete_url(expense_id), data={"user_id": str(seed_user_id)})

    assert resp.status_code == 302
    assert _row_by_id(expense_id) is None, "Own expense should still be deleted despite spoofed user_id in body"

    seed_stats_after = get_summary_stats(seed_user_id)
    assert seed_stats_after == seed_stats_before, "Spoofed user_id must not affect another user's stats"


def test_delete_expense_spoofed_user_id_cannot_bypass_ownership_check(client, login, fresh_user, seed_user_id):
    """A malicious user cannot delete another user's expense by supplying
    their own user_id in the POST body; the URL id + session user_id are
    the only things that matter, and the check must still fail with 404."""
    attacker_id, _ = fresh_user
    victim_expense_id = _make_expense(seed_user_id)

    login(attacker_id)
    resp = client.post(_delete_url(victim_expense_id), data={"user_id": str(attacker_id)})

    assert resp.status_code == 404
    assert _row_by_id(victim_expense_id) is not None, "Victim's row must survive a spoofed cross-user delete attempt"


# ---------------------------------------------------------------- #
# Profile page has a working Delete control per row                 #
# ---------------------------------------------------------------- #

def test_profile_page_has_delete_control_for_expense(client, login, fresh_user):
    user_id, _ = fresh_user
    expense_id = _make_expense(user_id)

    login(user_id)
    resp = client.get("/profile")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert _delete_form_action_pattern(expense_id).search(body), \
        "Profile page's transaction row should contain a form posting to that expense's delete URL"
    assert "profile-delete-link" in body, "Delete control should use the profile-delete-link class per spec"
    assert "confirm(" in body, "Delete form should prompt for confirmation before submitting"


def test_profile_page_delete_controls_point_to_correct_expense_ids(client, login, fresh_user):
    """With multiple expenses, each row's delete form must target its own
    expense id, not just the first/any expense."""
    user_id, _ = fresh_user
    id_a = _make_expense(user_id, description="Expense A", expense_date="2026-06-01")
    id_b = _make_expense(user_id, description="Expense B", expense_date="2026-06-02")
    id_c = _make_expense(user_id, description="Expense C", expense_date="2026-06-03")

    login(user_id)
    resp = client.get("/profile")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    for expense_id in (id_a, id_b, id_c):
        assert _delete_form_action_pattern(expense_id).search(body), \
            f"Expected a delete form targeting {_delete_url(expense_id)} for expense {expense_id}"


def test_profile_page_delete_control_removed_after_deletion(client, login, fresh_user):
    """After deleting one expense among several, only that row's delete
    control should disappear; the others should remain."""
    user_id, _ = fresh_user
    id_a = _make_expense(user_id, description="Expense A", expense_date="2026-06-01")
    id_b = _make_expense(user_id, description="Expense B", expense_date="2026-06-02")

    login(user_id)
    client.post(_delete_url(id_a))
    resp = client.get("/profile")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert not _delete_form_action_pattern(id_a).search(body), \
        "Deleted expense's row/delete form should no longer render"
    assert _delete_form_action_pattern(id_b).search(body), \
        "Remaining expense's delete form should still render"
