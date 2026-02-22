from datetime import date
from pydantic import BaseModel, Field, field_validator
from typing import Optional


def _validate_date(v: str) -> str:
    """Validate date string is a real date, not just matching a regex."""
    try:
        date.fromisoformat(v)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid date: {v!r} — expected YYYY-MM-DD")
    return v


class LoanCreate(BaseModel):
    name: str = Field(max_length=255)
    principal: float = Field(gt=0, le=100_000_000)
    annual_rate: float = Field(ge=0, le=100)
    frequency: str = Field(pattern="^(weekly|fortnightly|monthly)$")
    start_date: str
    loan_term: int = Field(gt=0, le=1200)
    fixed_repayment: Optional[float] = Field(default=None, gt=0, le=100_000_000)

    @field_validator("start_date")
    @classmethod
    def validate_start_date(cls, v):
        return _validate_date(v)


class LoanUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
    principal: Optional[float] = Field(default=None, gt=0, le=100_000_000)
    annual_rate: Optional[float] = Field(default=None, ge=0, le=100)
    frequency: Optional[str] = Field(default=None, pattern="^(weekly|fortnightly|monthly)$")
    start_date: Optional[str] = None
    loan_term: Optional[int] = Field(default=None, gt=0, le=1200)
    fixed_repayment: Optional[float] = Field(default=None, gt=0, le=100_000_000)

    @field_validator("start_date")
    @classmethod
    def validate_start_date(cls, v):
        if v is None:
            return v
        return _validate_date(v)


class LoanResponse(BaseModel):
    id: int
    name: str
    principal: float
    annual_rate: float
    frequency: str
    start_date: str
    loan_term: int
    fixed_repayment: Optional[float]
    created_at: Optional[str]
    updated_at: Optional[str]

    model_config = {"from_attributes": True}


class LoanDetailResponse(LoanResponse):
    rate_changes: list["RateChangeResponse"]
    extra_repayments: list["ExtraRepaymentResponse"]
    repayment_changes: list["RepaymentChangeResponse"]

    model_config = {"from_attributes": True}


class RateChangeCreate(BaseModel):
    effective_date: str
    annual_rate: float = Field(ge=0, le=100)
    adjusted_repayment: Optional[float] = Field(default=None, gt=0, le=100_000_000)
    note: Optional[str] = Field(default=None, max_length=500)

    @field_validator("effective_date")
    @classmethod
    def validate_effective_date(cls, v):
        return _validate_date(v)


class RateChangeResponse(BaseModel):
    id: int
    loan_id: int
    effective_date: str
    annual_rate: float
    adjusted_repayment: Optional[float]
    note: Optional[str]
    created_at: Optional[str]

    model_config = {"from_attributes": True}


class ExtraRepaymentCreate(BaseModel):
    payment_date: str
    amount: float = Field(gt=0, le=100_000_000)
    note: Optional[str] = Field(default=None, max_length=500)

    @field_validator("payment_date")
    @classmethod
    def validate_payment_date(cls, v):
        return _validate_date(v)


class ExtraRepaymentResponse(BaseModel):
    id: int
    loan_id: int
    payment_date: str
    amount: float
    note: Optional[str]
    created_at: Optional[str]

    model_config = {"from_attributes": True}


class RepaymentChangeCreate(BaseModel):
    effective_date: str
    amount: float = Field(gt=0, le=100_000_000)
    note: Optional[str] = Field(default=None, max_length=500)

    @field_validator("effective_date")
    @classmethod
    def validate_effective_date(cls, v):
        return _validate_date(v)


class RepaymentChangeResponse(BaseModel):
    id: int
    loan_id: int
    effective_date: str
    amount: float
    note: Optional[str]
    created_at: Optional[str]

    model_config = {"from_attributes": True}


class WhatIfRequest(BaseModel):
    fixed_repayment: Optional[float] = None
    rate_changes: Optional[list[RateChangeCreate]] = None        # replaces DB (existing)
    extra_repayments: Optional[list[ExtraRepaymentCreate]] = None # replaces DB (existing)
    additional_rate_changes: Optional[list[RateChangeCreate]] = None        # merges with DB
    additional_extra_repayments: Optional[list[ExtraRepaymentCreate]] = None # merges with DB


class ScheduleRow(BaseModel):
    number: int
    date: str
    opening_balance: float
    principal: float
    interest: float
    rate: float
    rate_start: float
    calculated_pmt: float
    additional: float
    extra: float
    closing_balance: float
    is_paid: bool


class ScheduleSummary(BaseModel):
    total_repayments: int
    total_interest: float
    total_paid: float
    payoff_date: str
    remaining_balance: float
    payments_made: int
    progress_pct: float
    next_payment: Optional[dict]
    warning: Optional[str]


class ScheduleResponse(BaseModel):
    summary: ScheduleSummary
    rows: list[ScheduleRow]


class ScenarioCreate(BaseModel):
    name: str = Field(max_length=255)
    description: Optional[str] = Field(default=None, max_length=1000)
    whatif_fixed_repayment: Optional[float] = None
    whatif_additional_rate_changes: Optional[list[RateChangeCreate]] = None
    whatif_additional_extra_repayments: Optional[list[ExtraRepaymentCreate]] = None


class ScenarioUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1000)
    whatif_fixed_repayment: Optional[float] = None
    whatif_additional_rate_changes: Optional[list[RateChangeCreate]] = None
    whatif_additional_extra_repayments: Optional[list[ExtraRepaymentCreate]] = None


class ScenarioResponse(BaseModel):
    id: int
    loan_id: int
    name: str
    description: Optional[str]
    total_interest: float
    total_paid: float
    payoff_date: str
    actual_num_repayments: int
    is_default: bool = False
    created_at: Optional[str]

    model_config = {"from_attributes": True}


class PayoffTargetResponse(BaseModel):
    target_date: str
    required_repayment: float
    total_interest: float
    total_paid: float
    num_repayments: int


class RateChangeOption(BaseModel):
    label: str
    fixed_repayment: float
    payoff_date: str
    total_interest: float
    num_repayments: int
    interest_delta: float
    repayment_delta: int


class RateChangePreviewResponse(BaseModel):
    has_fixed_repayment: bool
    current_payoff_date: str
    current_repayment: Optional[float]
    options: list[RateChangeOption]


class RepaymentChangePreviewResponse(BaseModel):
    current_payoff_date: str
    current_total_interest: float
    current_num_repayments: int
    new_payoff_date: str
    new_total_interest: float
    new_num_repayments: int
    interest_delta: float
    repayment_delta: int
