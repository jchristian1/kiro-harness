import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from kiro_worker.logging_config import configure_logging
from kiro_worker.config import settings
from kiro_worker.db.engine import create_tables
from kiro_worker.routes import health, projects, tasks, runs, dashboard, cleanup

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.LOG_LEVEL)
    logger.info("kiro-worker starting up", extra={"version": "1.0.0"})
    create_tables()
    logger.info("Database tables ready")
    yield
    logger.info("kiro-worker shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="kiro-worker",
        version="1.0.0",
        description="Backend system for managing Kiro CLI task execution",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception")
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": str(exc), "details": {}}},
        )

    from fastapi.exceptions import RequestValidationError

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed.",
                    "details": {"errors": exc.errors()},
                }
            },
        )

    from fastapi import HTTPException

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            return JSONResponse(
                status_code=exc.status_code,
                content={"error": exc.detail},
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": "INTERNAL_ERROR", "message": str(exc.detail), "details": {}}},
        )

    app.include_router(health.router)
    app.include_router(projects.router)
    app.include_router(tasks.router)
    app.include_router(runs.router)
    app.include_router(dashboard.router)
    app.include_router(cleanup.router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("kiro_worker.main:app", host=settings.HOST, port=settings.PORT, reload=False)
