import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from src.database import engine, Base, DATA_DIR
from src.routers import health, loans, schedule, scenarios, import_export

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(DATA_DIR, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    logger.info(f"Database initialized at {DATA_DIR}")
    yield


app = FastAPI(title="LoanRepay", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(loans.router)
app.include_router(schedule.router)
app.include_router(scenarios.router)
app.include_router(import_export.router)

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
