import structlog
import redis.asyncio as aioredis
from fastapi import HTTPException, Request, Response, status
from api.config import settings

logger = structlog.get_logger()


class RateLimiter:
    """Redis-backed sliding/fixed window rate limiter for FastAPI routes."""

    def __init__(self, times: int = 10, seconds: int = 60):
        self.times = times
        self.seconds = seconds

    async def __call__(self, request: Request, response: Response) -> None:
        # Extract identifier: authenticated user/api-key or client IP
        auth_header = request.headers.get("X-API-Key") or request.headers.get("Authorization") or ""
        client_ip = request.client.host if request.client else "unknown"
        identifier = auth_header or client_ip

        path = request.url.path
        key = f"ratelimit:{path}:{identifier}"

        try:
            r = aioredis.from_url(settings.redis_url, socket_connect_timeout=2)
            pipe = r.pipeline()
            pipe.incr(key)
            pipe.ttl(key)
            results = await pipe.execute()

            current_count = results[0]
            ttl = results[1]

            if ttl == -1 or ttl == -2:
                await r.expire(key, self.seconds)
                ttl = self.seconds

            await r.aclose()

            remaining = max(0, self.times - current_count)
            response.headers["X-RateLimit-Limit"] = str(self.times)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(ttl)

            if current_count > self.times:
                retry_after = str(max(1, ttl))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Maximum {self.times} requests per {self.seconds} seconds.",
                    headers={
                        "Retry-After": retry_after,
                        "X-RateLimit-Limit": str(self.times),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(ttl),
                    },
                )

        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("ratelimiter.bypass_on_redis_error", error=str(exc))
            # Fail open gracefully
            return
