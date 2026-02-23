import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from src.database import get_db
from src.models import Loan, Scenario, RateChange, ExtraRepayment, RepaymentChange
from src.schemas import ScenarioCreate, ScenarioUpdate, ScenarioResponse
from src.routers.schedule import _build_schedule

router = APIRouter(prefix="/api/loans/{loan_id}/scenarios", tags=["scenarios"])


def _build_config(loan, db, whatif_overrides=None):
    """Build the config dict for a scenario snapshot.

    Args:
        loan: The Loan ORM object
        db: Database session
        whatif_overrides: dict with optional keys: fixed_repayment,
            additional_rate_changes, additional_extra_repayments
    Returns:
        config dict ready for JSON serialisation
    """
    db_rates = db.query(RateChange).filter(RateChange.loan_id == loan.id).all()
    db_extras = db.query(ExtraRepayment).filter(ExtraRepayment.loan_id == loan.id).all()
    db_repayment_changes = db.query(RepaymentChange).filter(RepaymentChange.loan_id == loan.id).all()

    overrides = whatif_overrides or {}

    config = {
        "principal": loan.principal,
        "annual_rate": loan.annual_rate,
        "frequency": loan.frequency,
        "start_date": loan.start_date,
        "loan_term": loan.loan_term,
        "fixed_repayment": overrides.get("fixed_repayment", loan.fixed_repayment),
        "rate_changes": [
            {"effective_date": rc.effective_date, "annual_rate": rc.annual_rate,
             "adjusted_repayment": rc.adjusted_repayment, "note": rc.note}
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

    if overrides:
        config["whatif_overrides"] = {}
        if "fixed_repayment" in overrides and overrides["fixed_repayment"] is not None:
            config["whatif_overrides"]["fixed_repayment"] = overrides["fixed_repayment"]
        if overrides.get("additional_rate_changes"):
            config["whatif_overrides"]["additional_rate_changes"] = [
                {"effective_date": rc.effective_date, "annual_rate": rc.annual_rate}
                for rc in overrides["additional_rate_changes"]
            ]
        if overrides.get("additional_extra_repayments"):
            config["whatif_overrides"]["additional_extra_repayments"] = [
                {"payment_date": er.payment_date, "amount": er.amount}
                for er in overrides["additional_extra_repayments"]
            ]

    return config


def _create_default_scenario(loan, db):
    """Create a Default scenario for a loan with no what-if overrides."""
    from src.schemas import WhatIfRequest
    schedule = _build_schedule(loan, db, whatif=None)
    config = _build_config(loan, db)
    scenario = Scenario(
        loan_id=loan.id,
        name="Default",
        description="Base scenario with no what-if adjustments",
        total_interest=schedule.summary.total_interest,
        total_paid=schedule.summary.total_paid,
        payoff_date=schedule.summary.payoff_date,
        actual_num_repayments=schedule.summary.total_repayments,
        config_json=json.dumps(config),
        schedule_json=json.dumps([row.model_dump() for row in schedule.rows]),
        is_default=1,
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    return scenario


@router.get("", response_model=list[ScenarioResponse])
def list_scenarios(loan_id: int, db: Session = Depends(get_db)):
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    scenarios = db.query(Scenario).filter(Scenario.loan_id == loan_id).all()

    # Ensure a Default scenario exists
    has_default = any(s.is_default for s in scenarios)
    if not has_default:
        default = _create_default_scenario(loan, db)
        scenarios.insert(0, default)

    # Sort: Default first, then by id
    scenarios.sort(key=lambda s: (0 if s.is_default else 1, s.id))
    return scenarios


@router.post("", response_model=ScenarioResponse, status_code=201)
def save_scenario(loan_id: int, body: ScenarioCreate, db: Session = Depends(get_db)):
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    whatif = None
    whatif_overrides = {}
    if body.whatif_fixed_repayment is not None or body.whatif_additional_rate_changes is not None or body.whatif_additional_extra_repayments is not None:
        from src.schemas import WhatIfRequest
        whatif = WhatIfRequest(
            fixed_repayment=body.whatif_fixed_repayment,
            additional_rate_changes=body.whatif_additional_rate_changes,
            additional_extra_repayments=body.whatif_additional_extra_repayments,
        )
        if body.whatif_fixed_repayment is not None:
            whatif_overrides["fixed_repayment"] = body.whatif_fixed_repayment
        if body.whatif_additional_rate_changes is not None:
            whatif_overrides["additional_rate_changes"] = body.whatif_additional_rate_changes
        if body.whatif_additional_extra_repayments is not None:
            whatif_overrides["additional_extra_repayments"] = body.whatif_additional_extra_repayments

    schedule = _build_schedule(loan, db, whatif=whatif)
    config = _build_config(loan, db, whatif_overrides=whatif_overrides if whatif_overrides else None)

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
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A scenario with this name already exists")
    db.refresh(scenario)
    return scenario


@router.put("/{scenario_id}", response_model=ScenarioResponse)
def update_scenario(loan_id: int, scenario_id: int, body: ScenarioUpdate, db: Session = Depends(get_db)):
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    scenario = db.query(Scenario).filter(Scenario.id == scenario_id, Scenario.loan_id == loan_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")

    # Update name/description if provided
    if body.name is not None:
        scenario.name = body.name
    if body.description is not None:
        scenario.description = body.description

    # Recompute schedule if any what-if overrides are provided
    has_whatif = (body.whatif_fixed_repayment is not None or
                 body.whatif_additional_rate_changes is not None or
                 body.whatif_additional_extra_repayments is not None)

    if has_whatif:
        from src.schemas import WhatIfRequest
        whatif = WhatIfRequest(
            fixed_repayment=body.whatif_fixed_repayment,
            additional_rate_changes=body.whatif_additional_rate_changes,
            additional_extra_repayments=body.whatif_additional_extra_repayments,
        )
        whatif_overrides = {}
        if body.whatif_fixed_repayment is not None:
            whatif_overrides["fixed_repayment"] = body.whatif_fixed_repayment
        if body.whatif_additional_rate_changes is not None:
            whatif_overrides["additional_rate_changes"] = body.whatif_additional_rate_changes
        if body.whatif_additional_extra_repayments is not None:
            whatif_overrides["additional_extra_repayments"] = body.whatif_additional_extra_repayments

        schedule = _build_schedule(loan, db, whatif=whatif)
        config = _build_config(loan, db, whatif_overrides=whatif_overrides)

        scenario.total_interest = schedule.summary.total_interest
        scenario.total_paid = schedule.summary.total_paid
        scenario.payoff_date = schedule.summary.payoff_date
        scenario.actual_num_repayments = schedule.summary.total_repayments
        scenario.config_json = json.dumps(config)
        scenario.schedule_json = json.dumps([row.model_dump() for row in schedule.rows])
    elif body.name is None and body.description is None:
        # Recompute with no overrides (e.g. refreshing Default)
        schedule = _build_schedule(loan, db, whatif=None)
        config = _build_config(loan, db)
        scenario.total_interest = schedule.summary.total_interest
        scenario.total_paid = schedule.summary.total_paid
        scenario.payoff_date = schedule.summary.payoff_date
        scenario.actual_num_repayments = schedule.summary.total_repayments
        scenario.config_json = json.dumps(config)
        scenario.schedule_json = json.dumps([row.model_dump() for row in schedule.rows])

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A scenario with this name already exists")
    db.refresh(scenario)
    return scenario


@router.delete("/{scenario_id}")
def delete_scenario(loan_id: int, scenario_id: int, db: Session = Depends(get_db)):
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id, Scenario.loan_id == loan_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    if scenario.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete the Default scenario")
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
    if len(id_list) > 10:
        raise HTTPException(status_code=400, detail="Compare at most 10 scenarios")
    scenarios = db.query(Scenario).filter(Scenario.id.in_(id_list), Scenario.loan_id == loan_id).all()

    if len(scenarios) < 2:
        raise HTTPException(status_code=422, detail="Need at least 2 scenarios to compare")

    MAX_SCHEDULE_JSON = 10_000_000  # 10 MB
    results = []
    for s in scenarios:
        if s.schedule_json and len(s.schedule_json) > MAX_SCHEDULE_JSON:
            raise HTTPException(status_code=422, detail=f"Scenario '{s.name}' schedule data too large")
        results.append({
            "id": s.id,
            "name": s.name,
            "total_interest": s.total_interest,
            "total_paid": s.total_paid,
            "payoff_date": s.payoff_date,
            "actual_num_repayments": s.actual_num_repayments,
            "schedule": json.loads(s.schedule_json) if s.schedule_json else [],
        })
    return results


@router.get("/{scenario_id}")
def get_scenario(loan_id: int, scenario_id: int, db: Session = Depends(get_db)):
    scenario = db.query(Scenario).filter(Scenario.id == scenario_id, Scenario.loan_id == loan_id).first()
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return {
        "id": scenario.id,
        "name": scenario.name,
        "description": scenario.description,
        "total_interest": scenario.total_interest,
        "total_paid": scenario.total_paid,
        "payoff_date": scenario.payoff_date,
        "actual_num_repayments": scenario.actual_num_repayments,
        "config": json.loads(scenario.config_json) if scenario.config_json else {},
        "schedule": json.loads(scenario.schedule_json) if scenario.schedule_json else [],
        "is_default": bool(scenario.is_default),
    }
