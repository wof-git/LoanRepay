import csv
import io
import re
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from src.database import get_db
from src.models import Loan
from src.routers.schedule import _build_schedule

router = APIRouter(prefix="/api/loans", tags=["import_export"])


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
            raise HTTPException(status_code=422, detail="xlsx export requires openpyxl package")

    else:
        raise HTTPException(status_code=422, detail="Format must be 'csv' or 'xlsx'")
