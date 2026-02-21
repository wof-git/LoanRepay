"""Unit tests for calculator engine — validates against spreadsheet values."""

import pytest
from datetime import date
from src.calculator import pmt, calculate_schedule, find_repayment_for_target_date


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
