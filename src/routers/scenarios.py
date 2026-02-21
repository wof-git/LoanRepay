import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from src.database import get_db
from src.models import Loan, Scenario
from src.schemas import ScenarioCreate, ScenarioResponse, ScenarioDetailResponse
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

    schedule = _build_schedule(loan, db)

    config = {
        "principal": loan.principal,
        "annual_rate": loan.annual_rate,
        "frequency": loan.frequency,
        "start_date": loan.start_date,
        "loan_term": loan.loan_term,
        "fixed_repayment": loan.fixed_repayment,
    }

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

    id_list = [int(x.strip()) for x in ids.split(",") if x.strip()]
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
