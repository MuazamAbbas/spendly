"""
Tests for Step 6: Date Filter for Profile Page.

Spec: .claude/specs/06-date-filter-profile-page.md

`GET /profile` gains optional `start_date` / `end_date` query-string params
that narrow the summary stats, transaction list, and category breakdown to
that range. With no params (or invalid/incomplete params), behaviour must be
identical to the Step 5 all-time view. `start_date` after `end_date` must be
swapped rather than erroring, and malformed dates must fall back to no
filter rather than raising an exception.

Ground truth (from database/db.py::seed_db, demo@spendly.com):
    2026-07-01  Food           45.50   Grocery shopping
    2026-07-03  Transport      12.00   Uber ride
    2026-07-05  Bills         120.00   Internet bill
    2026-07-08  Health         35.00   Pharmacy
    2026-07-10  Entertainment  25.00   Netflix subscription
    2026-07-12  Shopping       89.99   Clothing
    2026-07-15  Other          15.00   Miscellaneous
    2026-07-18  Food           32.50   Restaurant dinner

All-time totals (matches tests/test_backend_connection.py):
    8 expenses, total 374.99, top category "Bills", 7 distinct categories.

NOTE: The spec's own Definition-of-Done example claims that filtering
`start_date=2026-07-01&end_date=2026-07-10` yields "3 expenses, ₨177.50".
That is factually wrong against the actual seed data above. The inclusive
range 2026-07-01..2026-07-10 actually contains 5 rows summing to ₨237.50
(Food 45.50 + Transport 12.00 + Bills 120.00 + Health 35.00 +
Entertainment 25.00 = 237.50). These correct, derivable-from-seed-data
figures are used throughout this file instead of the spec's example.
"""

import pytest

from database.queries import (
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)

# ---------------------------------------------------------------- #
# Ground truth constants                                            #
# ---------------------------------------------------------------- #

# All-time (no filter) — must match Step 5 behaviour exactly.
ALLTIME_TOTAL = 374.99
ALLTIME_COUNT = 8
ALLTIME_TOP_CATEGORY = "Bills"
ALLTIME_CATEGORY_COUNT = 7

# Filtered range 2026-07-01..2026-07-10 (inclusive) — 5 matching expenses.
RANGE_START = "2026-07-01"
RANGE_END = "2026-07-10"
RANGE_TOTAL = 237.50
RANGE_COUNT = 5
RANGE_TOP_CATEGORY = "Bills"
RANGE_DESCRIPTIONS_IN = [
    "Grocery shopping",
    "Uber ride",
    "Internet bill",
    "Pharmacy",
    "Netflix subscription",
]
RANGE_DESCRIPTIONS_OUT = [
    "Clothing",
    "Miscellaneous",
    "Restaurant dinner",
]

# A range with zero matching expenses (before any seeded expense date).
EMPTY_RANGE_START = "2026-06-01"
EMPTY_RANGE_END = "2026-06-30"


# ---------------------------------------------------------------- #
# Happy path: no filter == Step 5 all-time behaviour                #
# ---------------------------------------------------------------- #

def test_profile_no_query_params_shows_alltime_data(client, login, seed_user_id):
    login(seed_user_id)
    resp = client.get("/profile")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert f"{ALLTIME_TOTAL:.2f}" in body, "Expected all-time total to appear with no filter"
    assert ALLTIME_TOP_CATEGORY in body

    stats = get_summary_stats(seed_user_id)
    assert stats["total_spent"] == ALLTIME_TOTAL
    assert stats["transaction_count"] == ALLTIME_COUNT

    breakdown = get_category_breakdown(seed_user_id)
    assert len(breakdown) == ALLTIME_CATEGORY_COUNT


# ---------------------------------------------------------------- #
# Happy path: filter narrows stats / transactions / breakdown       #
# ---------------------------------------------------------------- #

def test_profile_filtered_narrows_summary_stats(client, login, seed_user_id):
    login(seed_user_id)
    resp = client.get(f"/profile?start_date={RANGE_START}&end_date={RANGE_END}")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert f"{RANGE_TOTAL:.2f}" in body, "Expected filtered total ₨237.50 to appear"
    assert f"{ALLTIME_TOTAL:.2f}" not in body, "All-time total should not leak into filtered view"


def test_profile_filtered_narrows_transaction_list(client, login, seed_user_id):
    login(seed_user_id)
    resp = client.get(f"/profile?start_date={RANGE_START}&end_date={RANGE_END}")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    for desc in RANGE_DESCRIPTIONS_IN:
        assert desc in body, f"Expected in-range transaction '{desc}' to be shown"
    for desc in RANGE_DESCRIPTIONS_OUT:
        assert desc not in body, f"Out-of-range transaction '{desc}' should be filtered out"


def test_profile_filtered_narrows_category_breakdown(client, login, seed_user_id):
    login(seed_user_id)
    resp = client.get(f"/profile?start_date={RANGE_START}&end_date={RANGE_END}")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    for cat in ["Food", "Transport", "Bills", "Health", "Entertainment"]:
        assert cat in body, f"Expected in-range category '{cat}' in breakdown"
    for cat in ["Shopping", "Other"]:
        assert cat not in body, f"Out-of-range category '{cat}' should not appear"


def test_get_summary_stats_with_date_filter(seed_user_id):
    stats = get_summary_stats(seed_user_id, start_date=RANGE_START, end_date=RANGE_END)
    assert stats["total_spent"] == RANGE_TOTAL
    assert stats["transaction_count"] == RANGE_COUNT
    assert stats["top_category"] == RANGE_TOP_CATEGORY


def test_get_recent_transactions_with_date_filter(seed_user_id):
    txs = get_recent_transactions(seed_user_id, start_date=RANGE_START, end_date=RANGE_END)
    assert len(txs) == RANGE_COUNT
    descriptions = {t["description"] for t in txs}
    assert descriptions == set(RANGE_DESCRIPTIONS_IN)


def test_get_summary_stats_no_args_still_works(seed_user_id):
    """Step 5 call sites (no date args) must keep working unchanged."""
    stats = get_summary_stats(seed_user_id)
    assert stats["total_spent"] == ALLTIME_TOTAL
    assert stats["transaction_count"] == ALLTIME_COUNT


# ---------------------------------------------------------------- #
# Auth guard                                                        #
# ---------------------------------------------------------------- #

def test_profile_requires_login_no_filter(client):
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_profile_requires_login_with_filter_params(client):
    resp = client.get(f"/profile?start_date={RANGE_START}&end_date={RANGE_END}")
    assert resp.status_code == 302, "Auth guard must apply even with filter query params present"
    assert "/login" in resp.headers["Location"]


# ---------------------------------------------------------------- #
# Validation: malformed dates fall back to no filter                #
# ---------------------------------------------------------------- #

@pytest.mark.parametrize(
    "start_date,end_date",
    [
        ("notadate", RANGE_END),
        (RANGE_START, "notadate"),
        ("2026-13-40", "2026-07-10"),
        ("07-01-2026", "07-10-2026"),
        ("", ""),
    ],
)
def test_profile_malformed_date_falls_back_to_alltime(client, login, seed_user_id, start_date, end_date):
    login(seed_user_id)
    resp = client.get(f"/profile?start_date={start_date}&end_date={end_date}")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200, "Malformed date must not raise a 500 error"
    assert f"{ALLTIME_TOTAL:.2f}" in body, "Malformed date should fall back to all-time data"


# ---------------------------------------------------------------- #
# Validation: start_date after end_date gets swapped                #
# ---------------------------------------------------------------- #

def test_profile_start_after_end_gets_swapped(client, login, seed_user_id):
    login(seed_user_id)
    # Reversed order: start is after end.
    resp = client.get(f"/profile?start_date={RANGE_END}&end_date={RANGE_START}")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200, "Reversed date range must not error"
    assert f"{RANGE_TOTAL:.2f}" in body, "Reversed range should be swapped and yield the same filtered total"
    for desc in RANGE_DESCRIPTIONS_IN:
        assert desc in body


# ---------------------------------------------------------------- #
# Validation: missing one of the two params falls back to no filter #
# ---------------------------------------------------------------- #

def test_profile_missing_end_date_falls_back_to_alltime(client, login, seed_user_id):
    login(seed_user_id)
    resp = client.get(f"/profile?start_date={RANGE_START}")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert f"{ALLTIME_TOTAL:.2f}" in body, "Only start_date present should fall back to all-time data"


def test_profile_missing_start_date_falls_back_to_alltime(client, login, seed_user_id):
    login(seed_user_id)
    resp = client.get(f"/profile?end_date={RANGE_END}")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert f"{ALLTIME_TOTAL:.2f}" in body, "Only end_date present should fall back to all-time data"


# ---------------------------------------------------------------- #
# Category breakdown pct still sums to 100 when filtered             #
# ---------------------------------------------------------------- #

def test_get_category_breakdown_filtered_sums_to_100(seed_user_id):
    breakdown = get_category_breakdown(seed_user_id, start_date=RANGE_START, end_date=RANGE_END)
    assert len(breakdown) > 0
    assert sum(c["pct"] for c in breakdown) == 100
    assert all(isinstance(c["pct"], int) for c in breakdown)


# ---------------------------------------------------------------- #
# Zero matching expenses in range: sensible empty/zero state         #
# ---------------------------------------------------------------- #

def test_profile_filter_zero_matches_shows_empty_state(client, login, seed_user_id):
    login(seed_user_id)
    resp = client.get(f"/profile?start_date={EMPTY_RANGE_START}&end_date={EMPTY_RANGE_END}")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200, "Empty-result date range must not crash"
    assert "0.00" in body
    assert "₨" in body


def test_get_summary_stats_zero_matches_in_range(seed_user_id):
    stats = get_summary_stats(seed_user_id, start_date=EMPTY_RANGE_START, end_date=EMPTY_RANGE_END)
    assert stats["total_spent"] == 0
    assert stats["transaction_count"] == 0


def test_get_category_breakdown_zero_matches_in_range(seed_user_id):
    breakdown = get_category_breakdown(seed_user_id, start_date=EMPTY_RANGE_START, end_date=EMPTY_RANGE_END)
    assert breakdown == []


def test_get_recent_transactions_zero_matches_in_range(seed_user_id):
    txs = get_recent_transactions(seed_user_id, start_date=EMPTY_RANGE_START, end_date=EMPTY_RANGE_END)
    assert txs == []


# ---------------------------------------------------------------- #
# Filter form reflects the active filter values                     #
# ---------------------------------------------------------------- #

def test_profile_filter_form_prefilled_with_active_dates(client, login, seed_user_id):
    login(seed_user_id)
    resp = client.get(f"/profile?start_date={RANGE_START}&end_date={RANGE_END}")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert f'value="{RANGE_START}"' in body, "start_date input should be prefilled with the active filter value"
    assert f'value="{RANGE_END}"' in body, "end_date input should be prefilled with the active filter value"
