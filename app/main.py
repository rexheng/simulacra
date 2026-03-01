import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import init_db

# Import simulation modules to trigger registry registration
import app.engine.policy.simulation  # noqa: F401
import app.engine.game_theory.ultimatum.simulation  # noqa: F401
import app.engine.game_theory.prison.simulation  # noqa: F401
import app.engine.game_theory.bystander.simulation  # noqa: F401

from app.api.simulations import router as simulations_router
from app.api.agents import router as agents_router
from app.api.experiments import router as experiments_router

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL, logging.INFO))
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database...")
    await init_db()
    logger.info("Database initialized. App ready.")
    yield
    logger.info("Shutting down.")


app = FastAPI(
    title="Social Simulation Engine",
    description="AI-powered social simulation engine using Strands Agents SDK",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(simulations_router)
app.include_router(agents_router)
app.include_router(experiments_router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}


app.mount("/", StaticFiles(directory="static", html=True), name="static")
