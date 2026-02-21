"""Pure-function loan calculator. No DB, no async."""

from dataclasses import dataclass, field
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

MAX_ITERATIONS = 2000
ZERO_THRESHOLD = 0.01


@dataclass
class ScheduleRow:
    number: int
    date: str
    opening_balance: float
    principal: float
    interest: float
    rate: float
    calculated_pmt: float
    additional: float
    extra: float
    closing_balance: float


@dataclass
class ScheduleResult:
    rows: list[ScheduleRow] = field(default_factory=list)
    total_interest: float = 0.0
    total_paid: float = 0.0
    total_repayments: int = 0
    payoff_date: str = ""
    warning: str | None = None


def pmt(rate_per_period: float, num_periods: int, present_value: float) -> float:
    """Calculate payment amount (like Excel PMT function).

    Returns a positive payment amount for a positive present_value (loan balance).
    """
    if num_periods <= 0:
        return present_value
    if abs(rate_per_period) < 1e-12:
        return round(present_value / num_periods, 2)
    if num_periods == 1:
        return round(present_value * (1 + rate_per_period), 2)
    r = rate_per_period
    n = num_periods
    pv = present_value
    payment = pv * r * (1 + r) ** n / ((1 + r) ** n - 1)
    return round(payment, 2)


def periods_per_year(frequency: str) -> int:
    if frequency == "weekly":
        return 52
    elif frequency == "fortnightly":
        return 26
    elif frequency == "monthly":
        return 12
    raise ValueError(f"Unknown frequency: {frequency}")


def add_period(start: date, frequency: str, periods: int) -> date:
    """Calculate payment date for a given period number."""
    if frequency == "weekly":
        return start + timedelta(days=7 * periods)
    elif frequency == "fortnightly":
        return start + timedelta(days=14 * periods)
    elif frequency == "monthly":
        return start + relativedelta(months=periods)
    raise ValueError(f"Unknown frequency: {frequency}")


def get_rate_at_date(
    payment_date: date,
    base_rate: float,
    rate_changes: list[dict] | None,
) -> float:
    """Look up the applicable annual rate at a given date."""
    if not rate_changes:
        return base_rate
    current_rate = base_rate
    for rc in sorted(rate_changes, key=lambda x: x["effective_date"]):
        eff = rc["effective_date"]
        if isinstance(eff, str):
            eff = date.fromisoformat(eff)
        if payment_date >= eff:
            current_rate = rc["annual_rate"]
        else:
            break
    return current_rate


def calculate_period_interest(
    balance: float,
    prev_date: date,
    payment_date: date,
    base_rate: float,
    rate_changes: list[dict] | None,
    frequency: str,
) -> tuple[float, float]:
    """Calculate interest for a period, pro-rating if a rate change falls mid-period.

    Returns (interest, end_of_period_rate).

    If no rate change boundary falls strictly within (prev_date, payment_date),
    uses the simple balance * rate / periods_per_year formula (matching Excel).

    If a rate change falls mid-period, splits into sub-intervals and uses
    daily interest: balance * annual_rate / 365 * days for each sub-interval.
    """
    ppy = periods_per_year(frequency)
    end_rate = get_rate_at_date(payment_date, base_rate, rate_changes)

    if not rate_changes:
        return round(balance * end_rate / ppy, 2), end_rate

    # Collect rate boundaries that fall strictly within (prev_date, payment_date)
    boundaries = []
    for rc in rate_changes:
        eff = rc["effective_date"]
        if isinstance(eff, str):
            eff = date.fromisoformat(eff)
        if prev_date < eff < payment_date:
            boundaries.append(eff)
    boundaries.sort()

    if not boundaries:
        # No mid-period rate change — use simple formula
        return round(balance * end_rate / ppy, 2), end_rate

    # Split the period into sub-intervals and sum daily interest
    total_interest = 0.0
    interval_start = prev_date
    for boundary in boundaries:
        days = (boundary - interval_start).days
        sub_rate = get_rate_at_date(interval_start, base_rate, rate_changes)
        total_interest += balance * sub_rate / 365 * days
        interval_start = boundary

    # Final sub-interval: boundary -> payment_date
    days = (payment_date - interval_start).days
    sub_rate = get_rate_at_date(interval_start, base_rate, rate_changes)
    total_interest += balance * sub_rate / 365 * days

    return round(total_interest, 2), end_rate


def get_repayment_at_date(
    payment_date: date,
    base_repayment: float | None,
    rate_changes: list[dict] | None,
    repayment_changes: list[dict] | None = None,
) -> float | None:
    """Look up the applicable repayment at a given date.

    Merges two sources of repayment overrides chronologically:
    - rate_changes with adjusted_repayment
    - standalone repayment_changes (effective_date + amount)

    The most recent override at or before payment_date wins.
    If none apply, returns base_repayment.
    """
    if base_repayment is None:
        return base_repayment

    # Build unified list of (effective_date, amount) overrides
    overrides = []
    if rate_changes:
        for rc in rate_changes:
            adj = rc.get("adjusted_repayment")
            if adj is not None:
                overrides.append((rc["effective_date"], adj))
    if repayment_changes:
        for rpc in repayment_changes:
            overrides.append((rpc["effective_date"], rpc["amount"]))

    if not overrides:
        return base_repayment

    current = base_repayment
    for eff_raw, amount in sorted(overrides, key=lambda x: x[0]):
        eff = eff_raw
        if isinstance(eff, str):
            eff = date.fromisoformat(eff)
        if payment_date >= eff:
            current = amount
        else:
            break
    return current


def get_extras_for_period(
    period_start: date,
    period_end: date,
    extra_repayments: list[dict] | None,
) -> float:
    """Sum extra repayments that fall within a period window.

    period_start is exclusive (previous payment date), period_end is inclusive (this payment date).
    For the first period, period_start is the loan start date (inclusive).
    """
    if not extra_repayments:
        return 0.0
    total = 0.0
    for er in extra_repayments:
        pd = er["payment_date"]
        if isinstance(pd, str):
            pd = date.fromisoformat(pd)
        if period_start < pd <= period_end:
            total += er["amount"]
    return round(total, 2)


def calculate_schedule(
    principal: float,
    annual_rate: float,
    frequency: str,
    start_date: date | str,
    loan_term: int,
    fixed_repayment: float | None = None,
    rate_changes: list[dict] | None = None,
    extra_repayments: list[dict] | None = None,
    paid_set: set[int] | None = None,
    repayment_changes: list[dict] | None = None,
) -> ScheduleResult:
    """Generate a full amortization schedule.

    Args:
        principal: Loan amount (positive).
        annual_rate: Starting annual rate as decimal (e.g., 0.0575).
        frequency: 'weekly', 'fortnightly', or 'monthly'.
        start_date: Loan start date.
        loan_term: Number of periods for PMT calculation.
        fixed_repayment: Base payment amount (None = use calculated PMT).
            Rate changes with adjusted_repayment and repayment_changes
            override this from their effective date.
        rate_changes: List of {"effective_date": ..., "annual_rate": ...,
            "adjusted_repayment": ... (optional)}.
        extra_repayments: List of {"payment_date": ..., "amount": ...}.
        paid_set: Set of repayment numbers that have been marked as paid.
        repayment_changes: List of {"effective_date": ..., "amount": ...}.
    """
    if isinstance(start_date, str):
        start_date = date.fromisoformat(start_date)
    if paid_set is None:
        paid_set = set()

    ppy = periods_per_year(frequency)
    balance = round(principal, 2)
    result = ScheduleResult()
    total_interest = 0.0
    total_paid = 0.0

    for i in range(1, MAX_ITERATIONS + 1):
        if balance < ZERO_THRESHOLD:
            break

        payment_date = add_period(start_date, frequency, i)
        prev_payment_date = add_period(start_date, frequency, i - 1) if i > 1 else start_date

        interest, current_rate = calculate_period_interest(
            balance, prev_payment_date, payment_date, annual_rate, rate_changes, frequency
        )
        rate_per_period = current_rate / ppy
        remaining_term = max(loan_term - (i - 1), 1)

        calculated_payment = pmt(rate_per_period, remaining_term, balance)

        # Determine repayment for this period — rate/repayment changes may override
        period_repayment = get_repayment_at_date(payment_date, fixed_repayment, rate_changes, repayment_changes)

        if period_repayment is not None:
            actual_payment = period_repayment
            additional = round(actual_payment - calculated_payment, 2)
            # Suppress tiny rounding artifacts (< 10c) from cumulative drift
            if abs(additional) < 0.10:
                additional = 0.0
                calculated_payment = actual_payment
        else:
            actual_payment = calculated_payment
            additional = 0.0

        extra_start = prev_payment_date if i > 1 else prev_payment_date - timedelta(days=1)
        extra = get_extras_for_period(extra_start, payment_date, extra_repayments)

        principal_from_payment = round(actual_payment - interest, 2)
        total_principal = principal_from_payment + extra

        # Cap: don't overpay
        if total_principal > balance:
            overshoot = total_principal - balance
            # Reduce actual payment first
            if extra > 0 and extra >= overshoot:
                extra = round(extra - overshoot, 2)
            else:
                actual_payment = round(interest + balance - extra, 2)
                principal_from_payment = round(actual_payment - interest, 2)
                additional = round(actual_payment - calculated_payment, 2) if period_repayment is not None else 0.0
            total_principal = balance

        # Also cap calculated_payment if it's the final period
        if principal_from_payment + extra >= balance:
            if period_repayment is not None:
                calculated_payment = round(interest + (balance - extra), 2)
                additional = round(actual_payment - calculated_payment, 2)

        new_balance = round(balance - total_principal, 2)
        if new_balance < ZERO_THRESHOLD:
            new_balance = 0.0

        row = ScheduleRow(
            number=i,
            date=payment_date.isoformat(),
            opening_balance=balance,
            principal=principal_from_payment,
            interest=interest,
            rate=current_rate,
            calculated_pmt=calculated_payment,
            additional=additional,
            extra=extra,
            closing_balance=new_balance,
        )
        result.rows.append(row)

        total_interest += interest
        total_paid += actual_payment + extra
        balance = new_balance

        if balance <= 0:
            break
    else:
        # Hit MAX_ITERATIONS
        if fixed_repayment is not None:
            rate_per_period_check = annual_rate / ppy
            min_interest = principal * rate_per_period_check
            if fixed_repayment <= min_interest:
                result.warning = "Repayment does not cover interest. Loan will not be paid off."
            else:
                result.warning = f"Schedule exceeded {MAX_ITERATIONS} periods."

    result.total_interest = round(total_interest, 2)
    result.total_paid = round(total_paid, 2)
    result.total_repayments = len(result.rows)
    if result.rows:
        result.payoff_date = result.rows[-1].date

    return result


def find_repayment_for_target_date(
    principal: float,
    annual_rate: float,
    frequency: str,
    start_date: date | str,
    loan_term: int,
    target_date: date | str,
    rate_changes: list[dict] | None = None,
    extra_repayments: list[dict] | None = None,
    fixed_repayment: float | None = None,
    adjust_rate_idx: int | None = None,
    repayment_changes: list[dict] | None = None,
) -> dict:
    """Binary search for the repayment amount that pays off by target_date.

    If adjust_rate_idx is set, the search varies rate_changes[idx]["adjusted_repayment"]
    while keeping fixed_repayment as the base for earlier periods.

    If adjust_rate_idx is None, the search varies fixed_repayment directly (original behavior).
    """
    if isinstance(target_date, str):
        target_date = date.fromisoformat(target_date)
    if isinstance(start_date, str):
        start_date = date.fromisoformat(start_date)

    ppy = periods_per_year(frequency)
    rate_per_period = annual_rate / ppy
    interest_floor = principal * rate_per_period

    low = interest_floor + 0.01
    high = principal * 2

    best = None
    for _ in range(100):
        mid = round((low + high) / 2, 2)

        if adjust_rate_idx is not None and rate_changes:
            # Vary only the adjusted_repayment on the target rate change
            trial_rates = [dict(rc) for rc in rate_changes]
            trial_rates[adjust_rate_idx]["adjusted_repayment"] = mid
            sched = calculate_schedule(
                principal=principal,
                annual_rate=annual_rate,
                frequency=frequency,
                start_date=start_date,
                loan_term=loan_term,
                fixed_repayment=fixed_repayment,
                rate_changes=trial_rates,
                extra_repayments=extra_repayments,
                repayment_changes=repayment_changes,
            )
        else:
            sched = calculate_schedule(
                principal=principal,
                annual_rate=annual_rate,
                frequency=frequency,
                start_date=start_date,
                loan_term=loan_term,
                fixed_repayment=mid,
                rate_changes=rate_changes,
                extra_repayments=extra_repayments,
                repayment_changes=repayment_changes,
            )

        if not sched.rows:
            break
        payoff = date.fromisoformat(sched.payoff_date)
        if payoff <= target_date:
            best = {
                "required_repayment": mid,
                "total_interest": sched.total_interest,
                "total_paid": sched.total_paid,
                "num_repayments": sched.total_repayments,
                "payoff_date": sched.payoff_date,
            }
            high = mid - 0.01
        else:
            low = mid + 0.01
        if high < low:
            break

    if best is None:
        return {"error": "Cannot pay off by target date. Target may be too soon."}
    return best
