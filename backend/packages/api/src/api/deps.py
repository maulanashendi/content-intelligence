from collections.abc import AsyncIterator
from typing import Annotated

from core.db import get_session
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession


async def db_session() -> AsyncIterator[AsyncSession]:
    async with get_session() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(db_session)]
