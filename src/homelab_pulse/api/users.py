from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from homelab_pulse.database import get_db
from homelab_pulse.dependencies import AdminUser, CurrentUser
from homelab_pulse.models.user import User
from homelab_pulse.schemas.user import UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse, summary="Retorna o usuário autenticado")
async def get_my_profile(current_user: CurrentUser) -> User:
    return current_user


@router.get("", response_model=list[UserResponse], summary="Lista usuários para administração")
async def list_users(
    _admin: AdminUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[User]:
    users = await db.scalars(select(User).order_by(User.created_at))
    return list(users)
