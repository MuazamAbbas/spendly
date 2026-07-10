from database.queries import (
    get_user_by_id,
    get_summary_stats,
    get_recent_transactions,
    get_category_breakdown,
)

# Ground truth for the seeded demo user. The spec's own test table states
# 346.24, but seed_db()'s actual expenses sum to 374.99 and this step
# forbids changing seed data — 374.99 is treated as ground truth.
EXPECTED_SEED_TOTAL = 374.99
EXPECTED_SEED_COUNT = 8
EXPECTED_TOP_CATEGORY = "Bills"
EXPECTED_CATEGORY_COUNT = 7


# ---------------------------------------------------------------- #
# Unit tests                                                        #
# ---------------------------------------------------------------- #

def test_get_user_by_id_valid(seed_user_id):
    user = get_user_by_id(seed_user_id)
    assert user["name"] == "Demo User"
    assert user["email"] == "demo@spendly.com"
    assert user["member_since"]


def test_get_user_by_id_missing():
    assert get_user_by_id(999999) is None


def test_get_summary_stats_with_expenses(seed_user_id):
    stats = get_summary_stats(seed_user_id)
    assert stats["total_spent"] == EXPECTED_SEED_TOTAL
    assert stats["transaction_count"] == EXPECTED_SEED_COUNT
    assert stats["top_category"] == EXPECTED_TOP_CATEGORY


def test_get_summary_stats_no_expenses(fresh_user):
    user_id, _ = fresh_user
    stats = get_summary_stats(user_id)
    assert stats == {"total_spent": 0, "transaction_count": 0, "top_category": "—"}


def test_get_recent_transactions_ordering(seed_user_id):
    txs = get_recent_transactions(seed_user_id)
    dates = [t["date"] for t in txs]
    assert dates == sorted(dates, reverse=True)
    assert all({"date", "description", "category", "amount"} <= t.keys() for t in txs)


def test_get_recent_transactions_empty(fresh_user):
    user_id, _ = fresh_user
    assert get_recent_transactions(user_id) == []


def test_get_category_breakdown_sums_to_100(seed_user_id):
    breakdown = get_category_breakdown(seed_user_id)
    amounts = [c["amount"] for c in breakdown]
    assert amounts == sorted(amounts, reverse=True)
    assert sum(c["pct"] for c in breakdown) == 100
    assert all(isinstance(c["pct"], int) for c in breakdown)


def test_get_category_breakdown_empty(fresh_user):
    user_id, _ = fresh_user
    assert get_category_breakdown(user_id) == []


# ---------------------------------------------------------------- #
# Route tests                                                       #
# ---------------------------------------------------------------- #

def test_profile_requires_login(client):
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_profile_authenticated_seed_user(client, login, seed_user_id):
    login(seed_user_id)
    resp = client.get("/profile")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "Demo User" in body
    assert "demo@spendly.com" in body
    assert "₨" in body  # ₨
    assert f"{EXPECTED_SEED_TOTAL:.2f}" in body
    assert EXPECTED_TOP_CATEGORY in body

    stats = get_summary_stats(seed_user_id)
    assert stats["transaction_count"] == EXPECTED_SEED_COUNT

    breakdown = get_category_breakdown(seed_user_id)
    assert len(breakdown) == EXPECTED_CATEGORY_COUNT


def test_profile_new_user_empty_state(client, login, fresh_user):
    user_id, _ = fresh_user
    login(user_id)
    resp = client.get("/profile")
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "0.00" in body
    assert "₨" in body
