import uuid
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from homelab_pulse.api.resources import get_owned_service
from homelab_pulse.database import get_db
from homelab_pulse.dependencies import CurrentUser
from homelab_pulse.models.service_check import ServiceCheck
from homelab_pulse.monitoring.http_probe import probe_http_service
from homelab_pulse.schemas.monitoring import ServiceCheckResponse

router = APIRouter(prefix="/services", tags=["monitoring"])


@router.post(
    "/{service_id}/check",
    response_model=ServiceCheckResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Verifica um serviço imediatamente",
)
async def check_service(
    service_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ServiceCheck:
    service = await get_owned_service(db, service_id, current_user.id)
    if not service.enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Service monitoring is disabled",
        )

    result = await probe_http_service(service.target_url)
    check = ServiceCheck(service_id=service.id, **asdict(result))
    db.add(check)
    await db.commit()
    await db.refresh(check)
    return check


@router.get(
    "/{service_id}/checks",
    response_model=list[ServiceCheckResponse],
    summary="Lista o histórico recente do serviço",
)
async def list_service_checks(
    service_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[ServiceCheck]:
    service = await get_owned_service(db, service_id, current_user.id)
    result = await db.scalars(
        select(ServiceCheck)
        .where(ServiceCheck.service_id == service.id)
        .order_by(ServiceCheck.checked_at.desc())
        .limit(limit)
    )
    return list(result)
