import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from homelab_pulse.models.server import Server
from homelab_pulse.models.service import Service


async def get_owned_server(db: AsyncSession, server_id: uuid.UUID, owner_id: uuid.UUID) -> Server:
    server = await db.scalar(
        select(Server).where(Server.id == server_id, Server.owner_id == owner_id)
    )
    if server is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Server not found")
    return server


async def get_owned_service(
    db: AsyncSession,
    service_id: uuid.UUID,
    owner_id: uuid.UUID,
) -> Service:
    service = await db.scalar(
        select(Service)
        .join(Server, Service.server_id == Server.id)
        .where(Service.id == service_id, Server.owner_id == owner_id)
    )
    if service is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    return service

