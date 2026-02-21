from pydantic import BaseModel, Field
from typing import Optional


class LoanCreate(BaseModel):
    name: str
    principal: float = Field(gt=0)
    annual_rate: float = Field(ge=0)
    frequency: str = Field(pattern="^(weekly|fortnightly|monthly)$")
    start_date: str
    loan_term: int = Field(gt=0)
    fixed_repayment: Optional[float] = Field(default=None, gt=0)


class LoanUpdate(BaseModel):
    name: Optional[str] = None
    principal: Optional[float] = Field(default=None, gt=0)
    annual_rate: Optional[float] = Field(default=None, ge=0)
    frequency: Optional[str] = Field(default=None, pattern="^(weekly|fortnightly|monthly)$")
    start_date: Optional[str] = None
    loan_term: Optional[int] = Field(default=None, gt=0)
    fixed_repayment: Optional[float] = None


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
    annual_rate: float = Field(ge=0)
    adjusted_repayment: Optional[float] = Field(default=None, gt=0)
    note: Optional[str] = None


class RateChangeUpdate(BaseModel):
    effective_date: Optional[str] = None
    annual_rate: Optional[float] = Field(default=None, ge=0)
    adjusted_repayment: Optional[float] = None
    note: Optional[str] = None


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
    amount: float = Field(gt=0)
    note: Optional[str] = None


class ExtraRepaymentUpdate(BaseModel):
    payment_date: Optional[str] = None
    amount: Optional[float] = Field(default=None, gt=0)
    note: Optional[str] = None


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
    amount: float = Field(gt=0)
    note: Optional[str] = None


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
    name: str
    description: Optional[str] = None
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
    created_at: Optional[str]

    model_config = {"from_attributes": True}


class ScenarioDetailResponse(ScenarioResponse):
    config_json: str
    schedule_json: str

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
