"""Unit tests for calculator engine — validates against spreadsheet values."""

import pytest
from datetime import date
from src.calculator import pmt, calculate_schedule, find_repayment_for_target_date, calculate_period_interest


# --- PMT function tests ---

def test_pmt_matches_excel():
    """PMT(5.75%/26, 52, 30050) should equal 612.39."""
    rate = 0.0575 / 26
    result = pmt(rate, 52, 30050.00)
    assert result == 612.39


def test_pmt_rate_zero():
    """Zero rate: equal payments."""
    result = pmt(0.0, 10, 1000.0)
    assert result == 100.0


def test_pmt_one_period():
    """Single period: principal + one period of interest."""
    result = pmt(0.05, 1, 1000.0)
    assert result == 1050.0


# --- Spreadsheet row validation (acceptance tests) ---

@pytest.fixture
def base_schedule():
    return calculate_schedule(
        principal=30050.00,
        annual_rate=0.0575,
        frequency="fortnightly",
        start_date=date(2026, 2, 20),
        loan_term=52,
        fixed_repayment=612.39,
    )


def test_row_1(base_schedule):
    row = base_schedule.rows[0]
    assert row.number == 1
    assert row.opening_balance == 30050.00
    assert row.interest == 66.46
    assert row.calculated_pmt == 612.39
    assert row.closing_balance == pytest.approx(29504.07, abs=0.01)


def test_row_2(base_schedule):
    row = base_schedule.rows[1]
    assert row.number == 2
    assert row.opening_balance == pytest.approx(29504.07, abs=0.01)
    assert row.interest == pytest.approx(65.25, abs=0.01)
    assert row.closing_balance == pytest.approx(28956.93, abs=0.01)


def test_row_26(base_schedule):
    row = base_schedule.rows[25]
    assert row.number == 26
    assert row.opening_balance == pytest.approx(16033.25, abs=0.05)
    assert row.interest == pytest.approx(35.46, abs=0.05)
    assert row.closing_balance == pytest.approx(15456.32, abs=0.05)


def test_row_52_final(base_schedule):
    row = base_schedule.rows[-1]
    assert row.number == 52
    assert row.opening_balance == pytest.approx(610.92, abs=0.05)
    assert row.interest == pytest.approx(1.35, abs=0.05)
    assert row.calculated_pmt == pytest.approx(612.27, abs=0.05)
    assert row.closing_balance == 0.0


def test_total_repayments(base_schedule):
    assert base_schedule.total_repayments == 52


def test_total_interest(base_schedule):
    assert base_schedule.total_interest == pytest.approx(1794.16, abs=0.02)


def test_total_paid(base_schedule):
    assert base_schedule.total_paid == pytest.approx(31844.16, abs=0.05)


def test_payoff_date(base_schedule):
    assert base_schedule.payoff_date == "2028-02-18"


def test_no_warning(base_schedule):
    assert base_schedule.warning is None


# --- Edge case tests ---

def test_rate_zero():
    """Zero rate: equal payments, no interest."""
    sched = calculate_schedule(
        principal=1000.0,
        annual_rate=0.0,
        frequency="monthly",
        start_date=date(2026, 1, 1),
        loan_term=10,
    )
    assert sched.total_interest == 0.0
    assert sched.total_repayments == 10
    for row in sched.rows:
        assert row.interest == 0.0


def test_final_payment_capped():
    """Last payment should be reduced so closing balance = 0."""
    sched = calculate_schedule(
        principal=30050.00,
        annual_rate=0.0575,
        frequency="fortnightly",
        start_date=date(2026, 2, 20),
        loan_term=52,
        fixed_repayment=612.39,
    )
    last_row = sched.rows[-1]
    assert last_row.closing_balance == 0.0
    # The calculated PMT should be less than the fixed repayment
    assert last_row.calculated_pmt <= 612.39


def test_fixed_repayment_below_interest():
    """Fixed repayment less than interest: should warn."""
    sched = calculate_schedule(
        principal=30050.00,
        annual_rate=0.0575,
        frequency="fortnightly",
        start_date=date(2026, 2, 20),
        loan_term=52,
        fixed_repayment=50.0,  # Way below the ~$66 interest
    )
    assert sched.warning is not None
    assert "interest" in sched.warning.lower() or "exceeded" in sched.warning.lower()


def test_fixed_repayment_above_pmt():
    """Overpaying: should pay off early with fewer repayments."""
    sched = calculate_schedule(
        principal=30050.00,
        annual_rate=0.0575,
        frequency="fortnightly",
        start_date=date(2026, 2, 20),
        loan_term=52,
        fixed_repayment=1000.0,
    )
    assert sched.total_repayments < 52
    assert sched.rows[-1].closing_balance == 0.0


def test_rate_change_mid_schedule():
    """Rate change from period 10 affects remaining schedule."""
    sched_base = calculate_schedule(
        principal=30050.00,
        annual_rate=0.0575,
        frequency="fortnightly",
        start_date=date(2026, 2, 20),
        loan_term=52,
        fixed_repayment=612.39,
    )
    sched_changed = calculate_schedule(
        principal=30050.00,
        annual_rate=0.0575,
        frequency="fortnightly",
        start_date=date(2026, 2, 20),
        loan_term=52,
        fixed_repayment=612.39,
        rate_changes=[{"effective_date": "2026-07-01", "annual_rate": 0.06}],
    )
    # First few rows should be the same (before rate change)
    assert sched_base.rows[0].interest == sched_changed.rows[0].interest
    # Total interest should differ
    assert sched_changed.total_interest != sched_base.total_interest
    # Higher rate means more total interest
    assert sched_changed.total_interest > sched_base.total_interest


def test_extra_repayment():
    """Lump sum reduces balance and total repayments."""
    sched_base = calculate_schedule(
        principal=30050.00,
        annual_rate=0.0575,
        frequency="fortnightly",
        start_date=date(2026, 2, 20),
        loan_term=52,
        fixed_repayment=612.39,
    )
    sched_extra = calculate_schedule(
        principal=30050.00,
        annual_rate=0.0575,
        frequency="fortnightly",
        start_date=date(2026, 2, 20),
        loan_term=52,
        fixed_repayment=612.39,
        extra_repayments=[{"payment_date": "2026-06-01", "amount": 5000.0}],
    )
    assert sched_extra.total_repayments < sched_base.total_repayments
    assert sched_extra.total_interest < sched_base.total_interest


def test_extra_repayment_exceeds_balance():
    """Extra larger than balance: capped to remaining balance."""
    sched = calculate_schedule(
        principal=1000.0,
        annual_rate=0.05,
        frequency="monthly",
        start_date=date(2026, 1, 1),
        loan_term=12,
        extra_repayments=[{"payment_date": "2026-02-01", "amount": 50000.0}],
    )
    # Should pay off quickly (1-2 periods)
    assert sched.total_repayments <= 2
    assert sched.rows[-1].closing_balance == 0.0


def test_monthly_frequency():
    """Monthly payments: correct date arithmetic."""
    sched = calculate_schedule(
        principal=12000.0,
        annual_rate=0.06,
        frequency="monthly",
        start_date=date(2026, 1, 31),
        loan_term=12,
    )
    # Feb should be 28
    assert sched.rows[0].date == "2026-02-28"
    # Mar should be 31
    assert sched.rows[1].date == "2026-03-31"
    assert sched.total_repayments == 12


def test_weekly_frequency():
    """Weekly payments: 52 periods per year."""
    sched = calculate_schedule(
        principal=5200.0,
        annual_rate=0.05,
        frequency="weekly",
        start_date=date(2026, 1, 1),
        loan_term=52,
    )
    assert sched.total_repayments == 52
    # Check first payment is 7 days later
    assert sched.rows[0].date == "2026-01-08"


def test_early_payoff_target():
    """Binary search finds correct repayment for target payoff date."""
    result = find_repayment_for_target_date(
        principal=30050.00,
        annual_rate=0.0575,
        frequency="fortnightly",
        start_date=date(2026, 2, 20),
        loan_term=52,
        target_date=date(2027, 6, 1),
    )
    assert "error" not in result
    # Verify the found repayment actually pays off by the target
    sched = calculate_schedule(
        principal=30050.00,
        annual_rate=0.0575,
        frequency="fortnightly",
        start_date=date(2026, 2, 20),
        loan_term=52,
        fixed_repayment=result["required_repayment"],
    )
    assert date.fromisoformat(sched.payoff_date) <= date(2027, 6, 1)


def test_no_fixed_repayment_uses_calculated_pmt():
    """Without fixed_repayment, use calculated PMT each period."""
    sched = calculate_schedule(
        principal=10000.0,
        annual_rate=0.06,
        frequency="monthly",
        start_date=date(2026, 1, 1),
        loan_term=12,
    )
    assert sched.total_repayments == 12
    assert sched.rows[-1].closing_balance == 0.0
    # All additional should be 0
    for row in sched.rows:
        assert row.additional == 0.0


# --- Pro-rata interest tests ---

def test_interest_prorate_mid_period_rate_change():
    """When a rate change falls mid-period, interest should be pro-rated."""
    balance = 30000.0
    prev_date = date(2026, 3, 6)
    payment_date = date(2026, 3, 20)  # 14-day period
    base_rate = 0.0575
    # Rate changes on Mar 9 — 3 days at old rate, 11 days at new rate
    rate_changes = [{"effective_date": "2026-03-09", "annual_rate": 0.06}]

    interest, end_rate = calculate_period_interest(
        balance, prev_date, payment_date, base_rate, rate_changes, "fortnightly"
    )

    # Manual calculation:
    # 3 days at 5.75%: 30000 * 0.0575 / 365 * 3 = 14.178...
    # 11 days at 6.00%: 30000 * 0.06 / 365 * 11 = 54.247...
    # Total: ~68.42
    expected = round(30000 * 0.0575 / 365 * 3 + 30000 * 0.06 / 365 * 11, 2)
    assert interest == expected
    assert end_rate == 0.06


def test_interest_no_split_matches_original():
    """When no rate change falls within a period, use simple formula (Excel match)."""
    balance = 30050.0
    prev_date = date(2026, 2, 20)
    payment_date = date(2026, 3, 6)
    base_rate = 0.0575

    interest, end_rate = calculate_period_interest(
        balance, prev_date, payment_date, base_rate, None, "fortnightly"
    )

    # Simple formula: balance * rate / 26
    expected = round(30050.0 * 0.0575 / 26, 2)
    assert interest == expected
    assert end_rate == 0.0575


def test_prorate_schedule_differs_from_simple():
    """A mid-period rate change should produce different interest than full-period."""
    # Schedule with rate change exactly on a payment boundary
    sched_boundary = calculate_schedule(
        principal=30050.00,
        annual_rate=0.0575,
        frequency="fortnightly",
        start_date=date(2026, 2, 20),
        loan_term=52,
        fixed_repayment=612.39,
        rate_changes=[{"effective_date": "2026-07-10", "annual_rate": 0.06}],
    )
    # Schedule with rate change mid-period (3 days after a payment date)
    sched_mid = calculate_schedule(
        principal=30050.00,
        annual_rate=0.0575,
        frequency="fortnightly",
        start_date=date(2026, 2, 20),
        loan_term=52,
        fixed_repayment=612.39,
        rate_changes=[{"effective_date": "2026-07-13", "annual_rate": 0.06}],
    )
    # The total interest should differ because of pro-rating
    assert sched_boundary.total_interest != sched_mid.total_interest


def test_adjusted_repayment_on_rate_change():
    """Rate change with adjusted_repayment changes payment from that date forward."""
    # Schedule with rate change but no adjusted_repayment
    sched_no_adj = calculate_schedule(
        principal=30050.00,
        annual_rate=0.0575,
        frequency="fortnightly",
        start_date=date(2026, 2, 20),
        loan_term=52,
        fixed_repayment=612.39,
        rate_changes=[{"effective_date": "2026-09-01", "annual_rate": 0.06}],
    )

    # Schedule with rate change carrying adjusted_repayment
    sched_adj = calculate_schedule(
        principal=30050.00,
        annual_rate=0.0575,
        frequency="fortnightly",
        start_date=date(2026, 2, 20),
        loan_term=52,
        fixed_repayment=612.39,
        rate_changes=[{"effective_date": "2026-09-01", "annual_rate": 0.06, "adjusted_repayment": 620.00}],
    )

    # Early periods (before rate change) should be identical
    assert sched_no_adj.rows[0].closing_balance == sched_adj.rows[0].closing_balance

    # Total interest should differ — higher repayment from rate change date
    assert sched_adj.total_interest < sched_no_adj.total_interest
    # Fewer total payments with higher repayment
    assert sched_adj.total_repayments <= sched_no_adj.total_repayments

    # Both should pay off
    assert sched_no_adj.rows[-1].closing_balance == 0.0
    assert sched_adj.rows[-1].closing_balance == 0.0


def test_adjusted_repayment_reverts_on_removal():
    """Removing a rate change with adjusted_repayment reverts to original schedule."""
    base_sched = calculate_schedule(
        principal=30050.00,
        annual_rate=0.0575,
        frequency="fortnightly",
        start_date=date(2026, 2, 20),
        loan_term=52,
        fixed_repayment=612.39,
    )

    # Same params but with a rate change + adjusted_repayment
    sched_with = calculate_schedule(
        principal=30050.00,
        annual_rate=0.0575,
        frequency="fortnightly",
        start_date=date(2026, 2, 20),
        loan_term=52,
        fixed_repayment=612.39,
        rate_changes=[{"effective_date": "2026-09-01", "annual_rate": 0.06, "adjusted_repayment": 620.00}],
    )

    # They should differ
    assert sched_with.total_interest != base_sched.total_interest

    # "Remove" the rate change (pass no rate_changes) — should match base
    sched_after_remove = calculate_schedule(
        principal=30050.00,
        annual_rate=0.0575,
        frequency="fortnightly",
        start_date=date(2026, 2, 20),
        loan_term=52,
        fixed_repayment=612.39,
    )
    assert sched_after_remove.total_interest == base_sched.total_interest
    assert sched_after_remove.total_repayments == base_sched.total_repayments
