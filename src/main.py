import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from src.database import engine, Base, DATA_DIR
from src.routers import health, loans, schedule, scenarios, import_export

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _run_migrations(eng):
    """Add columns that don't exist yet (SQLite ALTER TABLE ADD COLUMN)."""
    with eng.connect() as conn:
        result = conn.exec_driver_sql("PRAGMA table_info(rate_changes)")
        columns = {row[1] for row in result}
        if "adjusted_repayment" not in columns:
            conn.exec_driver_sql("ALTER TABLE rate_changes ADD COLUMN adjusted_repayment REAL")
            conn.commit()
            logger.info("Migration: added adjusted_repayment column to rate_changes")


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(DATA_DIR, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _run_migrations(engine)
    logger.info(f"Database initialized at {DATA_DIR}")
    yield


app = FastAPI(title="LoanRepay", version="1.0.0", lifespan=lifespan)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


app.add_middleware(SecurityHeadersMiddleware)

app.include_router(health.router)
app.include_router(loans.router)
app.include_router(schedule.router)
app.include_router(scenarios.router)
app.include_router(import_export.router)

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
