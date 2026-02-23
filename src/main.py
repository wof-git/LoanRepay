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

        result = conn.exec_driver_sql("PRAGMA table_info(scenarios)")
        columns = {row[1] for row in result}
        if "is_default" not in columns:
            conn.exec_driver_sql("ALTER TABLE scenarios ADD COLUMN is_default INTEGER NOT NULL DEFAULT 0")
            conn.commit()
            logger.info("Migration: added is_default column to scenarios")

        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_scenario_loan_name ON scenarios(loan_id, name)"
        )
        conn.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(DATA_DIR, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    _run_migrations(engine)
    logger.info(f"Database initialized at {DATA_DIR}")
    yield


_is_production = os.getenv("ENV") == "production"

app = FastAPI(
    title="LoanRepay",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None if _is_production else "/docs",
    redoc_url=None,
    openapi_url=None if _is_production else "/openapi.json",
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' https://cdn.tailwindcss.com/3.4.17 https://cdn.jsdelivr.net/npm/chart.js@4.5.1; "
            "style-src 'self' https://cdn.tailwindcss.com 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'"
        )
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
        return response


app.add_middleware(SecurityHeadersMiddleware)

app.include_router(health.router)
app.include_router(loans.router)
app.include_router(schedule.router)
app.include_router(scenarios.router)
app.include_router(import_export.router)

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
