from contextlib import asynccontextmanager
import structlog
from fastapi import FastAPI
from api.config import settings

def _configure_logging() -> None:
    structlog.configure()

@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_logging()

    logger=structlog.get_logger()
    logger.info("app.startup")
    yield

def create_app() -> FastAPI:
    app =FastAPI(
        title=settings.app_name,
        docts_url= "/docs" if settings.debug else None,
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health():
        return {
            "status":"ok",
            "version": "0.1.0",
        }
    
    return app

app=create_app()