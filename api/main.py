from contextlib import asynccontextmanager
import structlog
import redis.asyncio as aioredis
from sqlalchemy import text
from fastapi import FastAPI, Request, Response, status

from api.config import settings
from api.database import AsyncSessionLocal
from api.routes import review, webhook


def _configure_logging() -> None:
    structlog.configure()


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_logging()

    logger = structlog.get_logger()
    logger.info("app.startup")
    yield


async def check_database() -> tuple[bool, str | None]:
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True, None
    except Exception as exc:
        return False, str(exc)


async def check_redis() -> tuple[bool, str | None]:
    try:
        r = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
        await r.ping()
        await r.aclose()
        return True, None
    except Exception as exc:
        return False, str(exc)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        docs_url="/docs" if settings.debug else None,
        lifespan=lifespan,
    )

    @app.get("/health", tags=["system"])
    async def health():
        return {
            "status": "ok",
            "version": "0.1.0",
        }

    @app.get("/ready", tags=["system"])
    async def readiness(response: Response):
        db_ok, db_err = await check_database()
        redis_ok, redis_err = await check_redis()

        all_healthy = db_ok and redis_ok
        if not all_healthy:
            response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

        return {
            "status": "ready" if all_healthy else "unhealthy",
            "checks": {
                "database": {"status": "healthy" if db_ok else "unhealthy", "error": db_err},
                "redis": {"status": "healthy" if redis_ok else "unhealthy", "error": redis_err},
            },
        }

    app.include_router(review.router)
    app.include_router(webhook.router)

    # Route fallback: also accept webhooks posted to root /
    @app.post("/", status_code=202, tags=["webhook"], include_in_schema=False)
    async def root_webhook_fallback(request: Request):
        return await webhook.github_webhook(
            request=request,
            x_github_event=request.headers.get("x-github-event"),
            x_hub_signature_256=request.headers.get("x-hub-signature-256"),
            x_github_delivery=request.headers.get("x-github-delivery"),
        )

    return app



app = create_app()


