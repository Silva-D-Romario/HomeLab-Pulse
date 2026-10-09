from fastapi import APIRouter

from homelab_pulse.dependencies import CurrentUser
from homelab_pulse.models.user import User
from homelab_pulse.schemas.user import UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse, summary="Retorna o usuário autenticado")
async def get_my_profile(current_user: CurrentUser) -> User:
    return current_user

