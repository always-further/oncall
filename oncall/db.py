import ssl

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from oncall.config import settings


def _connect_args() -> dict:
    if not settings.database_ssl:
        return {}
    ctx = ssl.create_default_context(cafile=settings.database_ssl_ca or None)
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    return {"ssl": ctx}


engine = create_async_engine(
    settings.database_url, echo=False, connect_args=_connect_args()
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session():
    async with async_session() as session:
        yield session
