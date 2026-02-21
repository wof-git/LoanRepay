from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from src.database import get_db
from src.models import Loan, RateChange, ExtraRepayment, RepaymentChange
from src.schemas import (
    LoanCreate, LoanUpdate, LoanResponse, LoanDetailResponse,
    RateChangeCreate, RateChangeUpdate, RateChangeResponse,
    ExtraRepaymentCreate, ExtraRepaymentUpdate, ExtraRepaymentResponse,
    RepaymentChangeCreate, RepaymentChangeResponse,
)

router = APIRouter(prefix="/api/loans", tags=["loans"])


# --- Loan CRUD ---

@router.get("", response_model=list[LoanResponse])
def list_loans(db: Session = Depends(get_db)):
    return db.query(Loan).all()


@router.post("", response_model=LoanResponse, status_code=201)
def create_loan(loan: LoanCreate, db: Session = Depends(get_db)):
    db_loan = Loan(**loan.model_dump())
    db.add(db_loan)
    db.commit()
    db.refresh(db_loan)
    return db_loan


@router.get("/{loan_id}", response_model=LoanDetailResponse)
def get_loan(loan_id: int, db: Session = Depends(get_db)):
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    return loan


@router.put("/{loan_id}", response_model=LoanResponse)
def update_loan(loan_id: int, updates: LoanUpdate, db: Session = Depends(get_db)):
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    update_data = updates.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(loan, key, value)
    loan.updated_at = datetime.now().isoformat()
    db.commit()
    db.refresh(loan)
    return loan


@router.delete("/{loan_id}")
def delete_loan(loan_id: int, db: Session = Depends(get_db)):
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    db.delete(loan)
    db.commit()
    return {"detail": "Loan deleted"}


# --- Rate Changes ---

@router.post("/{loan_id}/rates", response_model=RateChangeResponse, status_code=201)
def add_rate_change(loan_id: int, rc: RateChangeCreate, db: Session = Depends(get_db)):
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    if rc.effective_date < loan.start_date:
        raise HTTPException(status_code=422, detail="Rate change cannot be before loan start date")
    db_rc = RateChange(loan_id=loan_id, **rc.model_dump())
    db.add(db_rc)
    db.commit()
    db.refresh(db_rc)
    return db_rc


@router.put("/{loan_id}/rates/{rate_id}", response_model=RateChangeResponse)
def update_rate_change(loan_id: int, rate_id: int, updates: RateChangeUpdate, db: Session = Depends(get_db)):
    rc = db.query(RateChange).filter(RateChange.id == rate_id, RateChange.loan_id == loan_id).first()
    if not rc:
        raise HTTPException(status_code=404, detail="Rate change not found")
    update_data = updates.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(rc, key, value)
    db.commit()
    db.refresh(rc)
    return rc


@router.delete("/{loan_id}/rates/{rate_id}")
def delete_rate_change(loan_id: int, rate_id: int, db: Session = Depends(get_db)):
    rc = db.query(RateChange).filter(RateChange.id == rate_id, RateChange.loan_id == loan_id).first()
    if not rc:
        raise HTTPException(status_code=404, detail="Rate change not found")
    db.delete(rc)
    db.commit()
    return {"detail": "Rate change deleted"}


# --- Extra Repayments ---

@router.post("/{loan_id}/extras", response_model=ExtraRepaymentResponse, status_code=201)
def add_extra_repayment(loan_id: int, er: ExtraRepaymentCreate, db: Session = Depends(get_db)):
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    db_er = ExtraRepayment(loan_id=loan_id, **er.model_dump())
    db.add(db_er)
    db.commit()
    db.refresh(db_er)
    return db_er


@router.put("/{loan_id}/extras/{extra_id}", response_model=ExtraRepaymentResponse)
def update_extra_repayment(loan_id: int, extra_id: int, updates: ExtraRepaymentUpdate, db: Session = Depends(get_db)):
    er = db.query(ExtraRepayment).filter(ExtraRepayment.id == extra_id, ExtraRepayment.loan_id == loan_id).first()
    if not er:
        raise HTTPException(status_code=404, detail="Extra repayment not found")
    update_data = updates.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(er, key, value)
    db.commit()
    db.refresh(er)
    return er


@router.delete("/{loan_id}/extras/{extra_id}")
def delete_extra_repayment(loan_id: int, extra_id: int, db: Session = Depends(get_db)):
    er = db.query(ExtraRepayment).filter(ExtraRepayment.id == extra_id, ExtraRepayment.loan_id == loan_id).first()
    if not er:
        raise HTTPException(status_code=404, detail="Extra repayment not found")
    db.delete(er)
    db.commit()
    return {"detail": "Extra repayment deleted"}


# --- Repayment Changes ---

@router.post("/{loan_id}/repayment-changes", response_model=RepaymentChangeResponse, status_code=201)
def add_repayment_change(loan_id: int, rc: RepaymentChangeCreate, db: Session = Depends(get_db)):
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")
    if rc.effective_date < loan.start_date:
        raise HTTPException(status_code=422, detail="Repayment change cannot be before loan start date")
    db_rc = RepaymentChange(loan_id=loan_id, **rc.model_dump())
    db.add(db_rc)
    db.commit()
    db.refresh(db_rc)
    return db_rc


@router.delete("/{loan_id}/repayment-changes/{change_id}")
def delete_repayment_change(loan_id: int, change_id: int, db: Session = Depends(get_db)):
    rc = db.query(RepaymentChange).filter(RepaymentChange.id == change_id, RepaymentChange.loan_id == loan_id).first()
    if not rc:
        raise HTTPException(status_code=404, detail="Repayment change not found")
    db.delete(rc)
    db.commit()
    return {"detail": "Repayment change deleted"}
