"""
Tests for Step 10: Analytics Page Design.

Spec: .claude/specs/10-analytics-page-design.md

`GET /analytics` replaces the old "Coming Soon" stub with a fully designed
analytics page built from hardcoded (not DB-backed) data. It is a
protected route: a logged-out request must redirect to `/login`, same
guard pattern as `profile()`. A logged-in request must return HTTP 200
and render four sections:

  1. A summary row of three stat cards — total spent, average per
     transaction, and transaction count — reusing the `profile-stat-card`
     pattern from the Profile Page Design step.
  2. A monthly trend section with at least six hardcoded months rendered
     as CSS bars (heights via modifier classes, e.g. `analytics-bar-h-{n}`
     — never inline styles).
  3. A category comparison section with at least three hardcoded
     categories, reusing the `profile-cat-row` / `profile-cat-track` /
     `profile-cat-bar` pattern from `profile.html`.
  4. A top-expenses table with at least three hardcoded rows (date,
     description, category badge via the `category-badge` class, amount).

Since this step wires no real database queries (all context is hardcoded
Python dicts/lists in `app.py`), these tests are pure route-level
HTTP/HTML assertions — there is no `database/queries.py` analytics
function to unit test. Per the spec's Definition of Done, the rendered
page must also contain zero inline `style="..."` attributes, and the
navbar must keep showing the logged-in state (username/logout link) with
"Analytics" highlighted as the active nav item.
"""

import re

import pytest

ANALYTICS_URL = "/analytics"

# Per spec: minimum counts the DoD requires the page to render.
MIN_MONTHS = 6
MIN_CATEGORIES = 3
MIN_TOP_EXPENSE_ROWS = 3

INLINE_STYLE_RE = re.compile(r'style\s*=\s*"')


# ---------------------------------------------------------------- #
# Auth guard                                                        #
# ---------------------------------------------------------------- #

def test_analytics_requires_login_redirects_to_login(client):
    resp = client.get(ANALYTICS_URL)

    assert resp.status_code == 302, "Logged-out request must redirect, not render the page"
    assert "/login" in resp.headers["Location"], "Redirect target must be the login page"


def test_analytics_requires_login_does_not_leak_content(client):
    """A logged-out request must not leak any analytics markup in the
    redirect response body."""
    resp = client.get(ANALYTICS_URL)
    body = resp.get_data(as_text=True)

    assert resp.status_code == 302
    assert "profile-stat-card" not in body
    assert "Monthly trend" not in body


# ---------------------------------------------------------------- #
# Happy path: logged-in request returns 200                         #
# ---------------------------------------------------------------- #

def test_analytics_logged_in_returns_200(client, login, seed_user_id):
    login(seed_user_id)
    resp = client.get(ANALYTICS_URL)

    assert resp.status_code == 200


def test_analytics_logged_in_renders_analytics_template_landmarks(client, login, seed_user_id):
    """Sanity check that the real analytics page rendered, not some other
    template or an error page."""
    login(seed_user_id)
    resp = client.get(ANALYTICS_URL)
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "Monthly trend" in body
    assert "Category comparison" in body
    assert "Top expenses" in body


# ---------------------------------------------------------------- #
# Summary row: three stat cards                                     #
# ---------------------------------------------------------------- #

def test_analytics_summary_row_has_three_stat_cards(client, login, seed_user_id):
    login(seed_user_id)
    resp = client.get(ANALYTICS_URL)
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert body.count("profile-stat-card") >= 3, \
        "Expected at least three stat cards reusing the profile-stat-card pattern"


def test_analytics_summary_row_has_expected_labels(client, login, seed_user_id):
    login(seed_user_id)
    resp = client.get(ANALYTICS_URL)
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "Total spent" in body, "Expected a 'total spent' stat label"
    assert "Avg. per transaction" in body or "Average per transaction" in body, \
        "Expected an 'average per transaction' stat label"
    assert "Transactions" in body, "Expected a 'transaction count' stat label"


def test_analytics_summary_row_has_currency_and_count_values(client, login, seed_user_id):
    """Stat values should be rendered as currency amounts (₨) and a plain
    transaction count, consistent with the profile page's stat pattern."""
    login(seed_user_id)
    resp = client.get(ANALYTICS_URL)
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert body.count("₨") >= 2, "Expected at least two currency-formatted stat values (total, average)"
    assert re.search(r'profile-stat-value">[^<]*\d', body), \
        "Expected at least one numeric stat value rendered in a profile-stat-value element"


# ---------------------------------------------------------------- #
# Monthly trend section: >= 6 months as CSS bars                    #
# ---------------------------------------------------------------- #

def test_analytics_monthly_trend_has_at_least_six_months(client, login, seed_user_id):
    login(seed_user_id)
    resp = client.get(ANALYTICS_URL)
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    bar_labels = re.findall(r'analytics-bar-label">([^<]+)<', body)
    assert len(bar_labels) >= MIN_MONTHS, \
        f"Expected at least {MIN_MONTHS} month labels in the monthly trend section, found {len(bar_labels)}"


def test_analytics_monthly_trend_bars_use_css_modifier_classes(client, login, seed_user_id):
    """Bar heights must be expressed via CSS modifier classes
    (analytics-bar-h-{n}), never inline styles, per the spec."""
    login(seed_user_id)
    resp = client.get(ANALYTICS_URL)
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    bar_classes = re.findall(r'analytics-bar-h-\d+', body)
    assert len(bar_classes) >= MIN_MONTHS, \
        "Expected at least one analytics-bar-h-{n} modifier class per rendered month"


def test_analytics_monthly_trend_section_present(client, login, seed_user_id):
    login(seed_user_id)
    resp = client.get(ANALYTICS_URL)
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "analytics-trend-bars" in body
    assert "analytics-bar-track" in body


# ---------------------------------------------------------------- #
# Category comparison section: >= 3 categories with progress bars    #
# ---------------------------------------------------------------- #

def test_analytics_category_comparison_has_at_least_three_categories(client, login, seed_user_id):
    login(seed_user_id)
    resp = client.get(ANALYTICS_URL)
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    cat_rows = body.count("profile-cat-row")
    assert cat_rows >= MIN_CATEGORIES, \
        f"Expected at least {MIN_CATEGORIES} category rows, found {cat_rows}"


def test_analytics_category_comparison_reuses_profile_bar_pattern(client, login, seed_user_id):
    login(seed_user_id)
    resp = client.get(ANALYTICS_URL)
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "profile-cat-track" in body
    assert "profile-cat-bar" in body
    assert re.search(r'profile-cat-w-\d+', body), \
        "Expected category bar widths via a profile-cat-w-{percent} modifier class, not inline styles"


def test_analytics_category_comparison_shows_category_names_and_totals(client, login, seed_user_id):
    login(seed_user_id)
    resp = client.get(ANALYTICS_URL)
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "profile-cat-name" in body
    assert "profile-cat-amount" in body


# ---------------------------------------------------------------- #
# Top expenses table: >= 3 rows with category badges                #
# ---------------------------------------------------------------- #

def test_analytics_top_expenses_table_has_at_least_three_rows(client, login, seed_user_id):
    login(seed_user_id)
    resp = client.get(ANALYTICS_URL)
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "profile-table" in body, "Expected a table reusing the profile-table styling"
    row_count = len(re.findall(r"<tr>\s*<td>", body))
    assert row_count >= MIN_TOP_EXPENSE_ROWS, \
        f"Expected at least {MIN_TOP_EXPENSE_ROWS} data rows in the top expenses table, found {row_count}"


def test_analytics_top_expenses_table_has_column_headers(client, login, seed_user_id):
    login(seed_user_id)
    resp = client.get(ANALYTICS_URL)
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "<th>Date</th>" in body
    assert "<th>Description</th>" in body
    assert "<th>Category</th>" in body
    assert "Amount</th>" in body


def test_analytics_top_expenses_rows_include_category_badges(client, login, seed_user_id):
    login(seed_user_id)
    resp = client.get(ANALYTICS_URL)
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    badge_count = len(re.findall(r'category-badge">[^<]+<', body))
    assert badge_count >= MIN_TOP_EXPENSE_ROWS, \
        f"Expected at least {MIN_TOP_EXPENSE_ROWS} category-badge elements, found {badge_count}"


def test_analytics_top_expenses_rows_show_currency_amounts(client, login, seed_user_id):
    login(seed_user_id)
    resp = client.get(ANALYTICS_URL)
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert body.count("₨") >= 2 + MIN_TOP_EXPENSE_ROWS, \
        "Expected currency-formatted amounts for the summary stats plus each top-expense row"


# ---------------------------------------------------------------- #
# No inline styles (Definition of Done)                             #
# ---------------------------------------------------------------- #

def test_analytics_page_has_no_inline_style_attributes(client, login, seed_user_id):
    login(seed_user_id)
    resp = client.get(ANALYTICS_URL)
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert not INLINE_STYLE_RE.search(body), \
        "Analytics page must not contain inline style=\"...\" attributes; use CSS modifier classes instead"


# ---------------------------------------------------------------- #
# Navbar reflects logged-in state and active nav item                #
# ---------------------------------------------------------------- #

def test_analytics_navbar_shows_logout_link_when_authenticated(client, login, seed_user_id):
    login(seed_user_id)
    resp = client.get(ANALYTICS_URL)
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert "Logout" in body, "Navbar should show a Logout link for an authenticated user"
    assert "Sign in" not in body, "Logged-in navbar should not show the signed-out 'Sign in' link"


def test_analytics_navbar_highlights_analytics_as_active(client, login, seed_user_id):
    login(seed_user_id)
    resp = client.get(ANALYTICS_URL)
    body = resp.get_data(as_text=True)

    assert resp.status_code == 200
    assert re.search(r'class="active"[^>]*>Analytics<', body) or \
        re.search(r'<a[^>]*class="active"[^>]*>\s*Analytics\s*<', body), \
        "Expected the Analytics nav link to carry the 'active' class on the analytics page"
