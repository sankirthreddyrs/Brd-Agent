"""FastAPI application factory and server entrypoint for BRD Agent."""

from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes_projects import router as projects_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("brd-agent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Log startup message and documentation URL."""
    logger.info("BRD Agent API started successfully.")
    logger.info("Interactive API documentation available at: http://localhost:8000/docs")
    yield


app = FastAPI(
    title="BRD Agent API",
    description="AI Agent that converts business ideas and source documents into structured Business Requirements Documents.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS configuration allowing common frontend origins and wildcard for MVP development
origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include route handlers
app.include_router(projects_router)


@app.exception_handler(ValueError)
async def value_error_exception_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Global handler translating domain ValueErrors into standard HTTP 400 responses."""
    err_str = str(exc)
    status_code = status.HTTP_404_NOT_FOUND if "not found" in err_str.lower() else status.HTTP_400_BAD_REQUEST
    return JSONResponse(
        status_code=status_code,
        content={"detail": err_str},
    )


@app.get("/health", tags=["system"], summary="Health check endpoint")
async def health_check() -> dict[str, str]:
    """Return system operational status."""
    return {"status": "ok"}
