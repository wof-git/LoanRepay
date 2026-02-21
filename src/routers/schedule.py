import json
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from src.database import get_db
from src.models import Loan, RateChange, ExtraRepayment, PaidRepayment, RepaymentChange
from src.schemas import (
    WhatIfRequest, ScheduleResponse, ScheduleRow, ScheduleSummary,
    PayoffTargetResponse, RateChangeCreate, RateChangeOption, RateChangePreviewResponse,
)
from src.calculator import calculate_schedule, find_repayment_for_target_date

router = APIRouter(prefix="/api/loans/{loan_id}", tags=["schedule"])


def _build_schedule(loan: Loan, db: Session, whatif: WhatIfRequest | None = None):
    """Build schedule from loan + DB data, optionally with what-if overrides."""
    # Get rate changes
    if whatif and whatif.rate_changes is not None:
        rate_changes = [{"effective_date": rc.effective_date, "annual_rate": rc.annual_rate} for rc in whatif.rate_changes]
    else:
        db_rates = db.query(RateChange).filter(RateChange.loan_id == loan.id).all()
        rate_changes = [{"effective_date": rc.effective_date, "annual_rate": rc.annual_rate, "adjusted_repayment": rc.adjusted_repayment} for rc in db_rates]

    # Get extra repayments
    if whatif and whatif.extra_repayments is not None:
        extras = [{"payment_date": er.payment_date, "amount": er.amount} for er in whatif.extra_repayments]
    else:
        db_extras = db.query(ExtraRepayment).filter(ExtraRepayment.loan_id == loan.id).all()
        extras = [{"payment_date": er.payment_date, "amount": er.amount} for er in db_extras]

    # Get repayment changes
    db_repayment_changes = db.query(RepaymentChange).filter(RepaymentChange.loan_id == loan.id).all()
    repayment_changes = [{"effective_date": rc.effective_date, "amount": rc.amount} for rc in db_repayment_changes]

    # Get paid repayments
    db_paid = db.query(PaidRepayment).filter(PaidRepayment.loan_id == loan.id).all()
    paid_set = {p.repayment_number for p in db_paid}

    fixed_repayment = loan.fixed_repayment
    if whatif and whatif.fixed_repayment is not None:
        fixed_repayment = whatif.fixed_repayment

    result = calculate_schedule(
        principal=loan.principal,
        annual_rate=loan.annual_rate,
        frequency=loan.frequency,
        start_date=loan.start_date,
        loan_term=loan.loan_term,
        fixed_repayment=fixed_repayment,
        rate_changes=rate_changes if rate_changes else None,
        extra_repayments=extras if extras else None,
        paid_set=paid_set,
        repayment_changes=repayment_changes if repayment_changes else None,
    )

    # Build response
    today = date.today()
    payments_made = len(paid_set)
    next_payment = None
    remaining_balance = 0.0

    rows = []
    for r in result.rows:
        is_paid = r.number in paid_set
        row = ScheduleRow(
            number=r.number,
            date=r.date,
            opening_balance=r.opening_balance,
            principal=r.principal,
            interest=r.interest,
            rate=r.rate,
            calculated_pmt=r.calculated_pmt,
            additional=r.additional,
            extra=r.extra,
            closing_balance=r.closing_balance,
            is_paid=is_paid,
        )
        rows.append(row)

        # Track next unpaid payment
        if not is_paid and next_payment is None:
            next_payment = {"number": r.number, "date": r.date, "amount": round(r.principal + r.interest + r.additional, 2)}
            remaining_balance = r.opening_balance

    if remaining_balance == 0.0 and rows:
        # All paid or no unpaid found
        remaining_balance = rows[-1].closing_balance

    progress_pct = round((payments_made / result.total_repayments * 100) if result.total_repayments > 0 else 0, 1)

    summary = ScheduleSummary(
        total_repayments=result.total_repayments,
        total_interest=result.total_interest,
        total_paid=result.total_paid,
        payoff_date=result.payoff_date,
        remaining_balance=remaining_balance,
        payments_made=payments_made,
        progress_pct=progress_pct,
        next_payment=next_payment,
        warning=result.warning,
    )

    return ScheduleResponse(summary=summary, rows=rows)


@router.get("/schedule", response_model=ScheduleResponse)
def get_schedule(loan_id: int, db: Session = Depends(get_db)):
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    return _build_schedule(loan, db)


@router.post("/schedule/whatif", response_model=ScheduleResponse)
def whatif_schedule(loan_id: int, whatif: WhatIfRequest, db: Session = Depends(get_db)):
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    return _build_schedule(loan, db, whatif=whatif)


@router.post("/paid/{repayment_number}")
def mark_paid(loan_id: int, repayment_number: int, db: Session = Depends(get_db)):
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    try:
        paid = PaidRepayment(loan_id=loan_id, repayment_number=repayment_number)
        db.add(paid)
        db.commit()
    except IntegrityError:
        db.rollback()
        # Already marked — idempotent
    return {"detail": "Marked as paid"}


@router.delete("/paid/{repayment_number}")
def unmark_paid(loan_id: int, repayment_number: int, db: Session = Depends(get_db)):
    paid = db.query(PaidRepayment).filter(
        PaidRepayment.loan_id == loan_id,
        PaidRepayment.repayment_number == repayment_number,
    ).first()
    if paid:
        db.delete(paid)
        db.commit()
    return {"detail": "Unmarked as paid"}


@router.post("/rates/preview", response_model=RateChangePreviewResponse)
def preview_rate_change(loan_id: int, rc: RateChangeCreate, db: Session = Depends(get_db)):
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    # Build existing rate changes + extras + repayment changes from DB
    db_rates = db.query(RateChange).filter(RateChange.loan_id == loan.id).all()
    existing_rates = [{"effective_date": r.effective_date, "annual_rate": r.annual_rate, "adjusted_repayment": r.adjusted_repayment} for r in db_rates]
    db_extras = db.query(ExtraRepayment).filter(ExtraRepayment.loan_id == loan.id).all()
    extras = [{"payment_date": er.payment_date, "amount": er.amount} for er in db_extras]
    db_repayment_changes = db.query(RepaymentChange).filter(RepaymentChange.loan_id == loan.id).all()
    repayment_changes = [{"effective_date": rc.effective_date, "amount": rc.amount} for rc in db_repayment_changes]

    # Current schedule (before this rate change)
    current = calculate_schedule(
        principal=loan.principal,
        annual_rate=loan.annual_rate,
        frequency=loan.frequency,
        start_date=loan.start_date,
        loan_term=loan.loan_term,
        fixed_repayment=loan.fixed_repayment,
        rate_changes=existing_rates or None,
        extra_repayments=extras or None,
        repayment_changes=repayment_changes or None,
    )
    current_payoff = current.payoff_date
    current_interest = current.total_interest

    # Rate changes with the new one added (no adjusted_repayment yet)
    new_rc = {"effective_date": rc.effective_date, "annual_rate": rc.annual_rate}
    new_rates = existing_rates + [new_rc]
    new_rc_idx = len(new_rates) - 1  # index of the new rate change

    options = []

    if loan.fixed_repayment is not None:
        # Option A: Keep current repayment (term changes)
        sched_a = calculate_schedule(
            principal=loan.principal,
            annual_rate=loan.annual_rate,
            frequency=loan.frequency,
            start_date=loan.start_date,
            loan_term=loan.loan_term,
            fixed_repayment=loan.fixed_repayment,
            rate_changes=new_rates,
            extra_repayments=extras or None,
            repayment_changes=repayment_changes or None,
        )
        options.append(RateChangeOption(
            label=f"Keep repayment at ${loan.fixed_repayment:,.2f}",
            fixed_repayment=loan.fixed_repayment,
            payoff_date=sched_a.payoff_date,
            total_interest=sched_a.total_interest,
            num_repayments=sched_a.total_repayments,
            interest_delta=round(sched_a.total_interest - current_interest, 2),
            repayment_delta=sched_a.total_repayments - current.total_repayments,
        ))

        # Option B: Adjust repayment from this rate change's date to keep payoff date
        target_result = find_repayment_for_target_date(
            principal=loan.principal,
            annual_rate=loan.annual_rate,
            frequency=loan.frequency,
            start_date=loan.start_date,
            loan_term=loan.loan_term,
            target_date=current_payoff,
            rate_changes=new_rates,
            extra_repayments=extras or None,
            fixed_repayment=loan.fixed_repayment,
            adjust_rate_idx=new_rc_idx,
            repayment_changes=repayment_changes or None,
        )
        if "error" not in target_result:
            new_repayment = target_result["required_repayment"]
            options.append(RateChangeOption(
                label=f"Adjust repayment to ${new_repayment:,.2f}",
                fixed_repayment=new_repayment,
                payoff_date=target_result["payoff_date"],
                total_interest=target_result["total_interest"],
                num_repayments=target_result["num_repayments"],
                interest_delta=round(target_result["total_interest"] - current_interest, 2),
                repayment_delta=target_result["num_repayments"] - current.total_repayments,
            ))
    else:
        # No fixed repayment — PMT auto-adjusts, show single option
        sched = calculate_schedule(
            principal=loan.principal,
            annual_rate=loan.annual_rate,
            frequency=loan.frequency,
            start_date=loan.start_date,
            loan_term=loan.loan_term,
            fixed_repayment=None,
            rate_changes=new_rates,
            extra_repayments=extras or None,
            repayment_changes=repayment_changes or None,
        )
        options.append(RateChangeOption(
            label="PMT auto-adjusts (no fixed repayment)",
            fixed_repayment=0,
            payoff_date=sched.payoff_date,
            total_interest=sched.total_interest,
            num_repayments=sched.total_repayments,
            interest_delta=round(sched.total_interest - current_interest, 2),
            repayment_delta=sched.total_repayments - current.total_repayments,
        ))

    return RateChangePreviewResponse(
        has_fixed_repayment=loan.fixed_repayment is not None,
        current_payoff_date=current_payoff,
        current_repayment=loan.fixed_repayment,
        options=options,
    )


@router.get("/payoff-target", response_model=PayoffTargetResponse)
def payoff_target(loan_id: int, target_date: str = Query(..., alias="date"), db: Session = Depends(get_db)):
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    db_rates = db.query(RateChange).filter(RateChange.loan_id == loan.id).all()
    rate_changes = [{"effective_date": rc.effective_date, "annual_rate": rc.annual_rate} for rc in db_rates]

    db_extras = db.query(ExtraRepayment).filter(ExtraRepayment.loan_id == loan.id).all()
    extras = [{"payment_date": er.payment_date, "amount": er.amount} for er in db_extras]

    db_repayment_changes = db.query(RepaymentChange).filter(RepaymentChange.loan_id == loan.id).all()
    rpc = [{"effective_date": rc.effective_date, "amount": rc.amount} for rc in db_repayment_changes]

    result = find_repayment_for_target_date(
        principal=loan.principal,
        annual_rate=loan.annual_rate,
        frequency=loan.frequency,
        start_date=loan.start_date,
        loan_term=loan.loan_term,
        target_date=target_date,
        rate_changes=rate_changes if rate_changes else None,
        extra_repayments=extras if extras else None,
        repayment_changes=rpc if rpc else None,
    )

    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])

    return PayoffTargetResponse(
        target_date=target_date,
        required_repayment=result["required_repayment"],
        total_interest=result["total_interest"],
        total_paid=result["total_paid"],
        num_repayments=result["num_repayments"],
    )
