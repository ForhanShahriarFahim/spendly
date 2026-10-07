"""Tests for Step 6: date filter on GET /profile (date_from / date_to).

Written from .claude/specs/06-date-filter-profile-page.md.
"""
import html
import re
from datetime import date, timedelta
from pathlib import Path

import pytest

import app as app_module

from database.db import (
    create_user,
    get_category_breakdown,
    get_db,
    get_expense_summary,
    get_recent_expenses,
)

ROOT = Path(__file__).resolve().parent.parent
TODAY = date.today()

# (offset in days before today, amount, category, unique description)
SEED = [
    (0, 1.11, "Food", "zz-today"),
    (40, 2.22, "Transport", "zz-40d"),
    (100, 4.44, "Bills", "zz-100d"),
    (200, 8.88, "Health", "zz-200d"),
    (400, 17.76, "Shopping", "zz-400d"),
]
ALL_DESCRIPTIONS = [s[3] for s in SEED]
ERROR_TEXT = "Start date must be before end date."


def iso(offset):
    return (TODAY - timedelta(days=offset)).isoformat()


def insert_expense(user_id, amount, category, day, description):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, day, description),
        )
        conn.commit()
    finally:
        conn.close()


def seed_user(email="filter@example.com", seed=SEED):
    user_id = create_user("Filter User", email, "password123")
    for offset, amount, category, description in seed:
        insert_expense(user_id, amount, category, iso(offset), description)
    return user_id


def login(client, email="filter@example.com"):
    return client.post("/login", data={"email": email, "password": "password123"})


@pytest.fixture
def user_id():
    return seed_user()


@pytest.fixture
def auth_client(client, user_id):
    login(client)
    return client


def get_page(client, **params):
    response = client.get("/profile", query_string=params)
    assert response.status_code == 200, "Expected /profile to render with 200"
    return response.data.decode()


def present(page, descriptions):
    return {d for d in descriptions if d in page}


def find_anchor(page, label):
    match = re.search(
        r"<a\b[^>]*>\s*" + re.escape(label) + r"\s*</a>", page, re.DOTALL
    )
    assert match, f"Expected a link labelled {label!r} in the filter bar"
    return match.group(0)


def anchor_href(anchor):
    match = re.search(r'href="([^"]*)"', anchor)
    assert match, "Expected the preset link to have an href"
    return html.unescape(match.group(1))


def follow_preset(client, label):
    page = client.get("/profile").data.decode()
    href = anchor_href(find_anchor(page, label))
    response = client.get(href)
    assert response.status_code == 200
    return response.data.decode()


def is_marked_active(anchor):
    return "active" in anchor.lower() or "aria-current" in anchor.lower()


# ------------------------------------------------------------ auth guard

class TestAuthGuard:
    @pytest.mark.parametrize(
        "params",
        [
            {},
            {"date_from": iso(10), "date_to": iso(0)},
            {"date_from": "not-a-date"},
        ],
    )
    def test_profile_with_filter_params_logged_out_redirects_to_login(
        self, client, params
    ):
        response = client.get("/profile", query_string=params)
        assert response.status_code == 302, "Logged-out user must be redirected"
        assert response.headers["Location"].endswith("/login")


# ------------------------------------------------------------ unfiltered

class TestUnfiltered:
    def test_no_params_shows_all_expenses_and_full_total(self, auth_client):
        page = get_page(auth_client)
        assert present(page, ALL_DESCRIPTIONS) == set(ALL_DESCRIPTIONS)
        assert "₹34.41" in page, "Expected unfiltered total of all expenses"

    def test_no_params_matches_helper_defaults(self, user_id):
        assert get_expense_summary(user_id) == get_expense_summary(
            user_id, date_from=None, date_to=None
        )
        assert get_expense_summary(user_id)["count"] == 5
        assert len(get_recent_expenses(user_id)) == 5
        assert len(get_category_breakdown(user_id)) == 5


# ------------------------------------------------------------ custom range

class TestCustomRange:
    def test_valid_range_shows_only_expenses_inside(self, auth_client):
        page = get_page(auth_client, date_from=iso(100), date_to=iso(40))
        assert present(page, ALL_DESCRIPTIONS) == {"zz-40d", "zz-100d"}

    def test_valid_range_summary_total_and_count(self, auth_client):
        page = get_page(auth_client, date_from=iso(100), date_to=iso(40))
        assert "₹6.66" in page, "Expected total 2.22 + 4.44 for the range"
        assert "₹34.41" not in page, "Unfiltered total must not appear"

    def test_valid_range_category_breakdown_only_in_range(self, auth_client):
        page = get_page(auth_client, date_from=iso(100), date_to=iso(40))
        assert "Transport" in page and "Bills" in page
        for outside in ("Food", "Health", "Shopping"):
            assert outside not in page, f"{outside} is outside the range"

    def test_bounds_are_inclusive_on_both_ends(self, auth_client):
        page = get_page(auth_client, date_from=iso(40), date_to=iso(40))
        assert present(page, ALL_DESCRIPTIONS) == {"zz-40d"}

    def test_range_just_excluding_boundary_dates(self, auth_client):
        page = get_page(auth_client, date_from=iso(99), date_to=iso(41))
        assert present(page, ALL_DESCRIPTIONS) == set()

    def test_other_users_expenses_never_included(self, client, user_id):
        other = create_user("Other", "other@example.com", "password123")
        insert_expense(other, 99.0, "Other", iso(40), "zz-other-user")
        login(client)
        page = get_page(client, date_from=iso(100), date_to=iso(0))
        assert "zz-other-user" not in page
        assert "₹99.00" not in page

    def test_filter_values_reflected_in_date_inputs(self, auth_client):
        page = get_page(auth_client, date_from=iso(100), date_to=iso(40))
        assert re.search(r'type="date"', page), "Expected date inputs"
        assert f'value="{iso(100)}"' in page, "date_from should be echoed back"
        assert f'value="{iso(40)}"' in page, "date_to should be echoed back"


# ------------------------------------------------------------ presets

class TestPresets:
    def test_filter_bar_has_four_presets_and_apply_button(self, auth_client):
        page = get_page(auth_client)
        for label in ("This Month", "Last 3 Months", "Last 6 Months", "All Time"):
            find_anchor(page, label)
        assert "Apply" in page
        assert len(re.findall(r'type="date"', page)) == 2

    def test_all_time_preset_is_clean_profile_url(self, auth_client):
        page = get_page(auth_client)
        href = anchor_href(find_anchor(page, "All Time"))
        assert "?" not in href, "All Time must not carry query params"
        assert href.rstrip("/").endswith("/profile")

    def test_this_month_preset_only_current_calendar_month(self, auth_client):
        page = follow_preset(auth_client, "This Month")
        shown = present(page, ALL_DESCRIPTIONS)
        assert "zz-today" in shown
        assert "zz-40d" not in shown, "40 days ago is never in this month"
        assert not shown & {"zz-100d", "zz-200d", "zz-400d"}

    def test_this_month_includes_first_day_excludes_previous_day(self, client):
        first = TODAY.replace(day=1)
        prev = first - timedelta(days=1)
        uid = seed_user("edge@example.com", seed=[])
        insert_expense(uid, 3.0, "Food", first.isoformat(), "zz-first")
        insert_expense(uid, 5.0, "Food", prev.isoformat(), "zz-prev")
        login(client, "edge@example.com")
        page = follow_preset(client, "This Month")
        assert "zz-first" in page
        assert "zz-prev" not in page

    def test_last_3_months_preset_window(self, auth_client):
        page = follow_preset(auth_client, "Last 3 Months")
        assert present(page, ALL_DESCRIPTIONS) == {"zz-today", "zz-40d"}

    def test_last_6_months_preset_window(self, auth_client):
        page = follow_preset(auth_client, "Last 6 Months")
        assert present(page, ALL_DESCRIPTIONS) == {"zz-today", "zz-40d", "zz-100d"}

    def test_all_time_preset_removes_active_filter(self, auth_client):
        filtered = get_page(auth_client, date_from=iso(1), date_to=iso(0))
        assert "zz-400d" not in filtered
        href = anchor_href(find_anchor(filtered, "All Time"))
        page = auth_client.get(href).data.decode()
        assert present(page, ALL_DESCRIPTIONS) == set(ALL_DESCRIPTIONS)

    def test_presets_filter_summary_totals(self, auth_client):
        assert "₹3.33" in follow_preset(auth_client, "Last 3 Months")
        assert "₹7.77" in follow_preset(auth_client, "Last 6 Months")

    def test_active_preset_is_highlighted_and_others_are_not(self, auth_client):
        page = follow_preset(auth_client, "Last 3 Months")
        assert is_marked_active(find_anchor(page, "Last 3 Months"))
        for label in ("This Month", "Last 6 Months", "All Time"):
            assert not is_marked_active(find_anchor(page, label)), (
                f"{label} must not look active"
            )

    def test_all_time_highlighted_when_unfiltered(self, auth_client):
        page = get_page(auth_client)
        assert is_marked_active(find_anchor(page, "All Time"))
        assert not is_marked_active(find_anchor(page, "This Month"))


# ------------------------------------------------------------ validation

class TestInvalidInput:
    def test_reversed_range_shows_inline_error(self, auth_client):
        page = get_page(auth_client, date_from=iso(0), date_to=iso(40))
        assert ERROR_TEXT in page, "Expected inline error for reversed range"

    def test_reversed_range_falls_back_to_unfiltered(self, auth_client):
        page = get_page(auth_client, date_from=iso(0), date_to=iso(40))
        assert present(page, ALL_DESCRIPTIONS) == set(ALL_DESCRIPTIONS)
        assert "₹34.41" in page

    def test_reversed_range_error_not_deferred_to_flash(self, auth_client):
        first = auth_client.get(
            "/profile", query_string={"date_from": iso(0), "date_to": iso(40)}
        )
        assert ERROR_TEXT in first.data.decode()
        second = auth_client.get("/profile")
        assert ERROR_TEXT not in second.data.decode(), (
            "Error must not persist to the next request"
        )

    def test_same_day_range_is_not_an_error(self, auth_client):
        page = get_page(auth_client, date_from=iso(40), date_to=iso(40))
        assert ERROR_TEXT not in page

    def test_valid_range_shows_no_error(self, auth_client):
        page = get_page(auth_client, date_from=iso(100), date_to=iso(0))
        assert ERROR_TEXT not in page

    @pytest.mark.parametrize(
        "params",
        [
            {"date_from": "not-a-date"},
            {"date_to": "not-a-date"},
            {"date_from": "not-a-date", "date_to": "also-bad"},
            {"date_from": "2024-13-45", "date_to": "2024-99-99"},
            {"date_from": "31/12/2024", "date_to": "01/01/2025"},
            {"date_from": "", "date_to": ""},
            {"date_from": "' OR 1=1; DROP TABLE expenses;--"},
            {"date_to": "2024-01-01'; DROP TABLE expenses;--"},
            {"date_from": "x" * 5000},
        ],
    )
    def test_malformed_dates_fall_back_to_unfiltered_without_crash(
        self, auth_client, params
    ):
        response = auth_client.get("/profile", query_string=params)
        assert response.status_code == 200, "Malformed dates must not crash"
        page = response.data.decode()
        assert present(page, ALL_DESCRIPTIONS) == set(ALL_DESCRIPTIONS)

    def test_sql_injection_attempt_leaves_table_intact(self, auth_client, user_id):
        auth_client.get(
            "/profile", query_string={"date_from": "1'; DROP TABLE expenses;--"}
        )
        assert get_expense_summary(user_id)["count"] == 5

    def test_unrelated_query_params_are_ignored(self, auth_client):
        page = get_page(auth_client, foo="bar")
        assert present(page, ALL_DESCRIPTIONS) == set(ALL_DESCRIPTIONS)


# ------------------------------------------------------------ empty states

class TestEmptyRange:
    def test_no_matches_shows_range_empty_message(self, auth_client):
        page = get_page(auth_client, date_from=iso(300), date_to=iso(250))
        assert "No expenses in this date range" in page

    def test_no_matches_shows_zero_total_and_no_rows(self, auth_client):
        page = get_page(auth_client, date_from=iso(300), date_to=iso(250))
        assert "₹0.00" in page
        assert present(page, ALL_DESCRIPTIONS) == set()
        assert "No expenses yet" not in page

    def test_future_range_has_no_matches(self, auth_client):
        page = get_page(
            auth_client,
            date_from=(TODAY + timedelta(days=10)).isoformat(),
            date_to=(TODAY + timedelta(days=20)).isoformat(),
        )
        assert "No expenses in this date range" in page

    def test_brand_new_user_still_sees_no_expenses_yet(self, client):
        create_user("Fresh", "fresh@example.com", "password123")
        login(client, "fresh@example.com")
        page = get_page(client)
        assert "No expenses yet" in page

    def test_brand_new_user_with_filter_renders_without_error(self, client):
        create_user("Fresh", "fresh2@example.com", "password123")
        login(client, "fresh2@example.com")
        page = get_page(client, date_from=iso(30), date_to=iso(0))
        assert "₹0.00" in page


# ------------------------------------------------------------ rupee symbol

class TestCurrencySymbol:
    @pytest.mark.parametrize(
        "params",
        [
            {},
            {"date_from": iso(100), "date_to": iso(40)},
            {"date_from": iso(300), "date_to": iso(250)},
            {"date_from": iso(0), "date_to": iso(40)},
            {"date_from": "garbage"},
        ],
    )
    def test_rupee_symbol_shown_regardless_of_filter(self, auth_client, params):
        page = get_page(auth_client, **params)
        assert "₹" in page


# ------------------------------------------------------------ db helpers

class TestDbHelpers:
    def test_summary_inclusive_bounds(self, user_id):
        result = get_expense_summary(user_id, iso(100), iso(40))
        assert result["count"] == 2
        assert result["total"] == pytest.approx(6.66)

    def test_summary_only_lower_bound_open_upper(self, user_id):
        result = get_expense_summary(user_id, date_from=iso(100))
        assert result["count"] == 3
        assert result["total"] == pytest.approx(7.77)

    def test_summary_only_upper_bound_open_lower(self, user_id):
        result = get_expense_summary(user_id, date_to=iso(100))
        assert result["count"] == 3
        assert result["total"] == pytest.approx(31.08)

    def test_summary_empty_range_is_zero(self, user_id):
        assert get_expense_summary(user_id, iso(300), iso(250)) == {
            "total": 0,
            "count": 0,
        }

    def test_recent_expenses_filtered_and_ordered_newest_first(self, user_id):
        rows = get_recent_expenses(user_id, date_from=iso(200), date_to=iso(40))
        assert [r["description"] for r in rows] == ["zz-40d", "zz-100d", "zz-200d"]

    def test_recent_expenses_limit_still_applies_with_filter(self, user_id):
        rows = get_recent_expenses(user_id, 2, iso(400), iso(0))
        assert [r["description"] for r in rows] == ["zz-today", "zz-40d"]

    def test_recent_expenses_empty_range(self, user_id):
        assert list(get_recent_expenses(user_id, 10, iso(300), iso(250))) == []

    def test_category_breakdown_filtered(self, user_id):
        rows = get_category_breakdown(user_id, iso(100), iso(40))
        assert {r["category"] for r in rows} == {"Transport", "Bills"}
        assert sum(r["pct"] for r in rows) == 100
        assert rows[0]["category"] == "Bills", "Highest total first"

    def test_category_breakdown_empty_range(self, user_id):
        assert get_category_breakdown(user_id, iso(300), iso(250)) == []

    def test_helpers_are_scoped_to_user_under_filter(self, user_id):
        other = create_user("Other", "other2@example.com", "password123")
        insert_expense(other, 50.0, "Food", iso(40), "zz-other")
        assert get_expense_summary(user_id, iso(100), iso(40))["count"] == 2
        descs = [r["description"] for r in get_recent_expenses(user_id, 10, iso(100), iso(40))]
        assert "zz-other" not in descs

    def test_helpers_do_not_modify_data(self, user_id):
        get_expense_summary(user_id, iso(100), iso(40))
        get_recent_expenses(user_id, 10, iso(100), iso(40))
        get_category_breakdown(user_id, iso(100), iso(40))
        assert get_expense_summary(user_id)["count"] == 5

    def test_injection_string_as_date_is_bound_not_executed(self, user_id):
        get_expense_summary(user_id, "1'; DROP TABLE expenses;--", None)
        assert get_expense_summary(user_id)["count"] == 5


class TestHelpersAndMarkup:
    def test_one_bad_one_good_applies_good_bound(self, auth_client):
        page = get_page(auth_client, date_from="junk", date_to=iso(50))
        assert present(page, ALL_DESCRIPTIONS) == {
            "zz-100d", "zz-200d", "zz-400d"}

    def test_lone_valid_date_from_filters_at_route_level(self, auth_client):
        page = get_page(auth_client, date_from=iso(50))
        assert present(page, ALL_DESCRIPTIONS) == {"zz-today", "zz-40d"}

    def test_lone_valid_date_to_filters_at_route_level(self, auth_client):
        page = get_page(auth_client, date_to=iso(50))
        assert present(page, ALL_DESCRIPTIONS) == {
            "zz-100d", "zz-200d", "zz-400d"}

    def test_shift_months_clamps_and_rolls_over(self):
        shift = app_module._shift_months
        assert shift(date(2026, 3, 31), -1) == date(2026, 2, 28)
        assert shift(date(2024, 3, 31), -1) == date(2024, 2, 29)
        assert shift(date(2026, 2, 10), -3) == date(2025, 11, 10)
        assert shift(date(2026, 1, 15), -6) == date(2025, 7, 15)

    def test_filter_bar_markup_rules(self, auth_client):
        page = get_page(auth_client)
        bar = page[page.index('class="filter-bar"'):page.index('class="profile-stats"')]
        assert "style=" not in page
        assert 'action="/profile"' in bar
        for forbidden in ("Recent expenses", "<table", "<progress"):
            assert forbidden not in bar

    def test_profile_css_uses_variables_only(self):
        css = (ROOT / "static" / "css" / "profile.css").read_text(encoding="utf-8")
        assert not re.search(r"#[0-9a-fA-F]{3,8}", css)
        assert ".filter-preset.is-active" in css
