import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from homelab_pulse.api.resources import get_owned_service
from homelab_pulse.database import get_db
from homelab_pulse.dependencies import CurrentUser
from homelab_pulse.models.incident import Incident, IncidentStatus
from homelab_pulse.models.server import Server
from homelab_pulse.models.service import Service
from homelab_pulse.schemas.incident import IncidentResponse

router = APIRouter(tags=["incidents"])


@router.get("/incidents", response_model=list[IncidentResponse])
async def list_incidents(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    incident_status: Annotated[IncidentStatus | None, Query(alias="status")] = None,
) -> list[Incident]:
    query = (
        select(Incident)
        .join(Service, Incident.service_id == Service.id)
        .join(Server, Service.server_id == Server.id)
        .where(Server.owner_id == current_user.id)
        .order_by(Incident.opened_at.desc())
    )
    if incident_status is not None:
        query = query.where(Incident.status == incident_status)
    return list(await db.scalars(query))


@router.get("/services/{service_id}/incidents", response_model=list[IncidentResponse])
async def list_service_incidents(
    service_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[Incident]:
    service = await get_owned_service(db, service_id, current_user.id)
    result = await db.scalars(
        select(Incident)
        .where(Incident.service_id == service.id)
        .order_by(Incident.opened_at.desc())
    )
    return list(result)

