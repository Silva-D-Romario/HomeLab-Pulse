import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from homelab_pulse.api.resources import get_owned_server, get_owned_service
from homelab_pulse.database import get_db
from homelab_pulse.dependencies import CurrentUser
from homelab_pulse.models.service import Service
from homelab_pulse.schemas.service import ServiceCreate, ServiceResponse, ServiceUpdate

router = APIRouter(tags=["services"])


def duplicate_service_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="A service with this name already exists on the server",
    )


@router.post(
    "/servers/{server_id}/services",
    response_model=ServiceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_service(
    server_id: uuid.UUID,
    payload: ServiceCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Service:
    await get_owned_server(db, server_id, current_user.id)
    service_data = payload.model_dump()
    service_data["target_url"] = str(payload.target_url)
    service = Service(server_id=server_id, **service_data)
    db.add(service)
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise duplicate_service_error() from error
    await db.refresh(service)
    return service


@router.get("/servers/{server_id}/services", response_model=list[ServiceResponse])
async def list_services(
    server_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[Service]:
    await get_owned_server(db, server_id, current_user.id)
    result = await db.scalars(
        select(Service).where(Service.server_id == server_id).order_by(Service.name)
    )
    return list(result)


@router.get("/services/{service_id}", response_model=ServiceResponse)
async def get_service(
    service_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Service:
    return await get_owned_service(db, service_id, current_user.id)


@router.patch("/services/{service_id}", response_model=ServiceResponse)
async def update_service(
    service_id: uuid.UUID,
    payload: ServiceUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Service:
    service = await get_owned_service(db, service_id, current_user.id)
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    if "target_url" in changes:
        changes["target_url"] = str(changes["target_url"])
    for field, value in changes.items():
        setattr(service, field, value)

    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise duplicate_service_error() from error
    await db.refresh(service)
    return service


@router.delete("/services/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_service(
    service_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    service = await get_owned_service(db, service_id, current_user.id)
    await db.delete(service)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)

