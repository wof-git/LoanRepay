# LoanRepay

Loan repayment schedule web app replacing an Excel spreadsheet.

## Tech Stack
- Backend: Python FastAPI + synchronous SQLite (SQLAlchemy ORM)
- Frontend: Vanilla JS (ES modules) + TailwindCSS (CDN) + Chart.js (CDN)
- Deployment: Docker on Synology NAS, port 5050

## Project Structure
- `src/` - FastAPI app, models, calculator, routers
- `src/static/` - Frontend HTML/JS/CSS served by FastAPI
- `data/` - SQLite database (gitignored)
- `tests/` - pytest unit, integration, and Playwright E2E tests
- `docker/` - Dockerfile and compose files
- `scripts/` - Dev setup, test runner, deployment

## Key Patterns
- Calculator is pure functions in `calculator.py` - no DB, no async
- Schedule computed on-the-fly, never stored (except scenario snapshots)
- All money values rounded to 2 decimal places at each step
- PRAGMA foreign_keys=ON set on every SQLite connection
- WAL mode enabled for concurrent access safety
- API errors return `{"detail": "message"}` with appropriate HTTP status

## Running
```bash
# Dev
pip install -r requirements.txt
uvicorn src.main:app --reload --port 8000

# Tests
pytest tests/test_calculator.py tests/test_api.py -v

# Docker
docker compose -f docker/compose.yaml up --build
```

## Database
SQLite in `data/loanrepay.db`. 6 tables:

- `loans` — principal, annual_rate, frequency, start_date, loan_term, fixed_repayment
- `rate_changes` — effective_date, annual_rate, adjusted_repayment (optional new repayment on rate change)
- `repayment_changes` — effective_date, amount (override fixed repayment from a date)
- `extra_repayments` — payment_date, amount (lump-sum payments)
- `paid_repayments` — loan_id + repayment_number (`UniqueConstraint`)
- `scenarios` — snapshot of schedule + config; loan_id + name (`UniqueConstraint`), is_default flag
