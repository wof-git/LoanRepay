import csv
import io
import logging
import re
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from src.database import get_db
from src.models import Loan
from src.schemas import LoanCreate, LoanResponse
from src.routers.schedule import _build_schedule

logger = logging.getLogger(__name__)
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

router = APIRouter(prefix="/api/loans", tags=["import_export"])


@router.post("/import", response_model=LoanResponse, status_code=201)
async def import_spreadsheet(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename or not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=422, detail="Only .xlsx files are supported")

    try:
        import openpyxl
        contents = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(contents) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail=f"File too large (max {MAX_UPLOAD_BYTES // 1024 // 1024} MB)")
        if contents[:4] != b'PK\x03\x04':
            raise HTTPException(status_code=422, detail="Invalid file: not a valid .xlsx archive")
        wb = openpyxl.load_workbook(io.BytesIO(contents), data_only=True)
        ws = wb.active

        # Parse expected cells based on spreadsheet layout
        # B1 = loan amount (may be negative), B2 = start date
        # G1 = periods/year, G2 = total periods, G3 = starting rate
        loan_amount = ws["B1"].value
        start_date = ws["B2"].value
        periods_year = ws["G1"].value
        total_periods = ws["G2"].value
        starting_rate = ws["G3"].value

        if loan_amount is None:
            raise HTTPException(status_code=422, detail="Expected loan amount in B1, found: empty")
        if start_date is None:
            raise HTTPException(status_code=422, detail="Expected start date in B2, found: empty")
        if total_periods is None:
            raise HTTPException(status_code=422, detail="Expected total periods in G2, found: empty")

        # Convert loan amount (may be negative in spreadsheet)
        principal = abs(float(loan_amount))

        # Convert rate (may be percentage or decimal)
        rate = float(starting_rate) if starting_rate else 0.0
        if rate > 1:
            rate = rate / 100  # Convert from percentage

        # Determine frequency from periods/year
        ppy = int(periods_year) if periods_year else 26
        if ppy == 52:
            frequency = "weekly"
        elif ppy == 26:
            frequency = "fortnightly"
        elif ppy == 12:
            frequency = "monthly"
        else:
            frequency = "fortnightly"

        # Convert start date
        if hasattr(start_date, "isoformat"):
            start_date_str = start_date.strftime("%Y-%m-%d")
        else:
            start_date_str = str(start_date)

        # Try to get fixed repayment from J column (first data row)
        fixed_repayment = None
        j_val = ws["J6"].value  # First repayment row
        if j_val is not None:
            fixed_repayment = round(float(j_val), 2)

        # Extract name from filename
        name = file.filename.replace(".xlsx", "").replace("_", " ").strip()

        # Validate through Pydantic before DB insert
        loan_data = LoanCreate(
            name=name,
            principal=principal,
            annual_rate=rate,
            frequency=frequency,
            start_date=start_date_str,
            loan_term=int(total_periods),
            fixed_repayment=fixed_repayment,
        )
        loan = Loan(**loan_data.model_dump())
        db.add(loan)
        db.commit()
        db.refresh(loan)
        return loan

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Spreadsheet import failed: {e}", exc_info=True)
        raise HTTPException(status_code=422, detail="Failed to parse spreadsheet. Check the file format matches the expected layout.")


@router.get("/{loan_id}/export")
def export_schedule(loan_id: int, format: str = Query("csv"), db: Session = Depends(get_db)):
    loan = db.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    schedule = _build_schedule(loan, db)
    safe_name = re.sub(r'[^\w\s\-]', '', loan.name).strip() or 'schedule'

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Number", "Date", "Opening Balance", "Principal", "Interest",
            "Rate", "Calculated PMT", "Additional", "Extra", "Closing Balance", "Paid"
        ])
        for row in schedule.rows:
            writer.writerow([
                row.number, row.date, row.opening_balance, row.principal,
                row.interest, row.rate, row.calculated_pmt, row.additional,
                row.extra, row.closing_balance, row.is_paid,
            ])
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{safe_name}_schedule.csv"'},
        )

    elif format == "xlsx":
        try:
            import openpyxl
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Schedule"
            headers = [
                "Number", "Date", "Opening Balance", "Principal", "Interest",
                "Rate", "Calculated PMT", "Additional", "Extra", "Closing Balance", "Paid"
            ]
            ws.append(headers)
            for row in schedule.rows:
                ws.append([
                    row.number, row.date, row.opening_balance, row.principal,
                    row.interest, row.rate, row.calculated_pmt, row.additional,
                    row.extra, row.closing_balance, row.is_paid,
                ])

            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            return StreamingResponse(
                output,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f'attachment; filename="{safe_name}_schedule.xlsx"'},
            )
        except ImportError:
            raise HTTPException(status_code=500, detail="openpyxl not installed for xlsx export")

    else:
        raise HTTPException(status_code=422, detail="Format must be 'csv' or 'xlsx'")
