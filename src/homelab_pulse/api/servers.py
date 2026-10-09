import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from homelab_pulse.api.resources import get_owned_server
from homelab_pulse.database import get_db
from homelab_pulse.dependencies import CurrentUser
from homelab_pulse.models.server import Server
from homelab_pulse.schemas.server import ServerCreate, ServerResponse, ServerUpdate

router = APIRouter(prefix="/servers", tags=["servers"])


def duplicate_server_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="A server with this name already exists",
    )


@router.post("", response_model=ServerResponse, status_code=status.HTTP_201_CREATED)
async def create_server(
    payload: ServerCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Server:
    server = Server(owner_id=current_user.id, **payload.model_dump())
    db.add(server)
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise duplicate_server_error() from error
    await db.refresh(server)
    return server


@router.get("", response_model=list[ServerResponse])
async def list_servers(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[Server]:
    result = await db.scalars(
        select(Server).where(Server.owner_id == current_user.id).order_by(Server.name)
    )
    return list(result)


@router.get("/{server_id}", response_model=ServerResponse)
async def get_server(
    server_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Server:
    return await get_owned_server(db, server_id, current_user.id)


@router.patch("/{server_id}", response_model=ServerResponse)
async def update_server(
    server_id: uuid.UUID,
    payload: ServerUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Server:
    server = await get_owned_server(db, server_id, current_user.id)
    for field, value in payload.model_dump(exclude_unset=True, exclude_none=True).items():
        setattr(server, field, value)

    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise duplicate_server_error() from error
    await db.refresh(server)
    return server


@router.delete("/{server_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_server(
    server_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    server = await get_owned_server(db, server_id, current_user.id)
    await db.delete(server)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

