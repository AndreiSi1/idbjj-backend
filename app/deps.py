from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session

DB = Depends(get_session)

__all__ = ["DB", "AsyncSession"]
