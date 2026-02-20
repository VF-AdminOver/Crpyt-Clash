from __future__ import annotations

from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from dnd_cli.server.models import Base


class Database:
    def __init__(self, url: str) -> None:
        self.url = url
        self.engine: AsyncEngine = create_async_engine(url, future=True)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)

    async def create_all(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    @asynccontextmanager
    async def session(self):
        async with self.session_factory() as session:
            yield session

    async def close(self) -> None:
        await self.engine.dispose()
