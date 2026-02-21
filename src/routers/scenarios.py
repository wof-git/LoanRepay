import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from src.database import get_db
from src.models import Loan, Scenario, RateChange, ExtraRepayment, RepaymentChange
from src.schemas import ScenarioCreate, ScenarioResponse
from src.routers.schedule import _build_schedule

router = APIRouter(prefix="/api/loans/{loan_id}/scenarios", tags=["scenarios"])


@router.get("", response_model=list[ScenarioResponse])
def list_scenarios(loan_id: int, db: Session = Depends(get_db)):
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    return db.query(Scenario).filter(Scenario.loan_id == loan_id).all()


@router.post("", response_model=ScenarioResponse, status_code=201)
def save_scenario(loan_id: int, body: ScenarioCreate, db: Session = Depends(get_db)):
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    whatif = None
    if body.whatif_fixed_repayment is not None or body.whatif_additional_rate_changes is not None or body.whatif_additional_extra_repayments is not None:
        from src.schemas import WhatIfRequest
        whatif = WhatIfRequest(
            fixed_repayment=body.whatif_fixed_repayment,
            additional_rate_changes=body.whatif_additional_rate_changes,
            additional_extra_repayments=body.whatif_additional_extra_repayments,
        )
    schedule = _build_schedule(loan, db, whatif=whatif)

    db_rates = db.query(RateChange).filter(RateChange.loan_id == loan.id).all()
    db_extras = db.query(ExtraRepayment).filter(ExtraRepayment.loan_id == loan.id).all()
    db_repayment_changes = db.query(RepaymentChange).filter(RepaymentChange.loan_id == loan.id).all()

    config = {
        "principal": loan.principal,
        "annual_rate": loan.annual_rate,
        "frequency": loan.frequency,
        "start_date": loan.start_date,
        "loan_term": loan.loan_term,
        "fixed_repayment": body.whatif_fixed_repayment if body.whatif_fixed_repayment is not None else loan.fixed_repayment,
        "rate_changes": [
            {"effective_date": rc.effective_date, "annual_rate": rc.annual_rate, "adjusted_repayment": rc.adjusted_repayment, "note": rc.note}
            for rc in db_rates
        ],
        "extra_repayments": [
            {"payment_date": er.payment_date, "amount": er.amount, "note": er.note}
            for er in db_extras
        ],
        "repayment_changes": [
            {"effective_date": rc.effective_date, "amount": rc.amount, "note": rc.note}
            for rc in db_repayment_changes
        ],
    }

    if body.whatif_fixed_repayment is not None or body.whatif_additional_rate_changes is not None or body.whatif_additional_extra_repayments is not None:
        config["whatif_overrides"] = {}
        if body.whatif_fixed_repayment is not None:
            config["whatif_overrides"]["fixed_repayment"] = body.whatif_fixed_repayment
        if body.whatif_additional_rate_changes is not None:
            config["whatif_overrides"]["additional_rate_changes"] = [
                {"effective_date": rc.effective_date, "annual_rate": rc.annual_rate} for rc in body.whatif_additional_rate_changes
            ]
        if body.whatif_additional_extra_repayments is not None:
            config["whatif_overrides"]["additional_extra_repayments"] = [
                {"payment_date": er.payment_date, "amount": er.amount} for er in body.whatif_additional_extra_repayments
            ]

    scenario = Scenario(
        loan_id=loan_id,
        name=body.name,
        description=body.description,
        total_interest=schedule.summary.total_interest,
        total_paid=schedule.summary.total_paid,
        payoff_date=schedule.summary.payoff_date,
        actual_num_repayments=schedule.summary.total_repayments,
        config_json=json.dumps(config),
        schedule_json=json.dumps([row.model_dump() for row in schedule.rows]),
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return scenario


@router.delete("/{scenario_id}")
def delete_scenario(loan_id: int, scenario_id: int, db: Session = Depends(get_db)):
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id, Scenario.loan_id == loan_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    db.delete(scenario)
    db.commit()
    return {"detail": "Scenario deleted"}


@router.get("/compare")
def compare_scenarios(loan_id: int, ids: str = Query(...), db: Session = Depends(get_db)):
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    try:
        id_list = [int(x.strip()) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid scenario IDs — must be comma-separated integers")
    scenarios = db.query(Scenario).filter(Scenario.id.in_(id_list), Scenario.loan_id == loan_id).all()

    if len(scenarios) < 2:
        raise HTTPException(status_code=422, detail="Need at least 2 scenarios to compare")

    return [
        {
            "id": s.id,
            "name": s.name,
            "total_interest": s.total_interest,
            "total_paid": s.total_paid,
            "payoff_date": s.payoff_date,
            "actual_num_repayments": s.actual_num_repayments,
            "schedule": json.loads(s.schedule_json),
        }
        for s in scenarios
    ]
