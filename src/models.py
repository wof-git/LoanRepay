from sqlalchemy import Column, Integer, Text, Float, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import relationship
from src.database import Base


class Loan(Base):
    __tablename__ = "loans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    principal = Column(Float, nullable=False)
    annual_rate = Column(Float, nullable=False)
    frequency = Column(Text, nullable=False)
    start_date = Column(Text, nullable=False)
    loan_term = Column(Integer, nullable=False)
    fixed_repayment = Column(Float, nullable=True)
    created_at = Column(Text, server_default="(datetime('now'))")
    updated_at = Column(Text, server_default="(datetime('now'))")

    __table_args__ = (
        CheckConstraint("frequency IN ('weekly', 'fortnightly', 'monthly')"),
    )

    rate_changes = relationship("RateChange", back_populates="loan", cascade="all, delete-orphan")
    extra_repayments = relationship("ExtraRepayment", back_populates="loan", cascade="all, delete-orphan")
    repayment_changes = relationship("RepaymentChange", back_populates="loan", cascade="all, delete-orphan")
    paid_repayments = relationship("PaidRepayment", back_populates="loan", cascade="all, delete-orphan")
    scenarios = relationship("Scenario", back_populates="loan", cascade="all, delete-orphan")


class RateChange(Base):
    __tablename__ = "rate_changes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    loan_id = Column(Integer, ForeignKey("loans.id", ondelete="CASCADE"), nullable=False)
    effective_date = Column(Text, nullable=False)
    annual_rate = Column(Float, nullable=False)
    adjusted_repayment = Column(Float, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(Text, server_default="(datetime('now'))")

    loan = relationship("Loan", back_populates="rate_changes")


class ExtraRepayment(Base):
    __tablename__ = "extra_repayments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    loan_id = Column(Integer, ForeignKey("loans.id", ondelete="CASCADE"), nullable=False)
    payment_date = Column(Text, nullable=False)
    amount = Column(Float, nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(Text, server_default="(datetime('now'))")

    loan = relationship("Loan", back_populates="extra_repayments")


class RepaymentChange(Base):
    __tablename__ = "repayment_changes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    loan_id = Column(Integer, ForeignKey("loans.id", ondelete="CASCADE"), nullable=False)
    effective_date = Column(Text, nullable=False)
    amount = Column(Float, nullable=False)
    note = Column(Text, nullable=True)
    created_at = Column(Text, server_default="(datetime('now'))")

    loan = relationship("Loan", back_populates="repayment_changes")


class PaidRepayment(Base):
    __tablename__ = "paid_repayments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    loan_id = Column(Integer, ForeignKey("loans.id", ondelete="CASCADE"), nullable=False)
    repayment_number = Column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("loan_id", "repayment_number"),
    )

    loan = relationship("Loan", back_populates="paid_repayments")


class Scenario(Base):
    __tablename__ = "scenarios"

    id = Column(Integer, primary_key=True, autoincrement=True)
    loan_id = Column(Integer, ForeignKey("loans.id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    total_interest = Column(Float, nullable=False)
    total_paid = Column(Float, nullable=False)
    payoff_date = Column(Text, nullable=False)
    actual_num_repayments = Column(Integer, nullable=False)
    config_json = Column(Text, nullable=False)
    schedule_json = Column(Text, nullable=False)
    is_default = Column(Integer, server_default="0", nullable=False)
    created_at = Column(Text, server_default="(datetime('now'))")

    __table_args__ = (
        UniqueConstraint("loan_id", "name"),
    )

    loan = relationship("Loan", back_populates="scenarios")
