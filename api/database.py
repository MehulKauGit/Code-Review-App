import urllib.parse
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from api.config import settings
from sqlalchemy.pool import NullPool


def normalize_database_url(url: str) -> str:
    if not url:
        return url

    # Normalize scheme to postgresql+asyncpg://
    if url.startswith("postgres://"):
        url = "postgresql+asyncpg://" + url[len("postgres://"):]
    elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]

    try:
        parsed = urllib.parse.urlparse(url)
        if not parsed.query:
            return url

        query_params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)

        # Map sslmode to asyncpg ssl argument
        sslmode_val = query_params.pop("sslmode", [None])[0]
        if sslmode_val:
            if sslmode_val in ("require", "verify-ca", "verify-full", "prefer"):
                query_params["ssl"] = ["require"]
            elif sslmode_val in ("disable", "allow"):
                query_params.pop("ssl", None)

        # Strip libpq-specific parameters unsupported by asyncpg
        incompatible_params = [
            "channel_binding",
            "target_session_attrs",
            "gssencmode",
            "application_name",
            "connect_timeout",
        ]
        for param in incompatible_params:
            query_params.pop(param, None)

        new_query = urllib.parse.urlencode(
            [(k, v) for k, values in query_params.items() for v in values]
        )
        return urllib.parse.urlunparse(parsed._replace(query=new_query))
    except Exception:
        return url



class Base(DeclarativeBase):
    pass


db_url = normalize_database_url(settings.database_url)
engine = create_async_engine(
    db_url,
    echo=False,
    poolclass=NullPool,
)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)