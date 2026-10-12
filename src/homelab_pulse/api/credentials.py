import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from homelab_pulse.api.resources import get_owned_service
from homelab_pulse.database import get_db
from homelab_pulse.dependencies import CurrentUser
from homelab_pulse.integration_crypto import encrypt_api_key
from homelab_pulse.models.service import ServiceKind
from homelab_pulse.models.service_credential import ServiceCredential
from homelab_pulse.schemas.credential import ServiceCredentialStatus, ServiceCredentialUpdate

router = APIRouter(tags=["integration credentials"])

SUPPORTED_CREDENTIAL_KINDS = {ServiceKind.JELLYFIN, ServiceKind.PORTAINER, ServiceKind.ARR}


@router.get(
    "/services/{service_id}/credential",
    response_model=ServiceCredentialStatus,
)
async def get_credential_status(
    service_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ServiceCredentialStatus:
    await get_owned_service(db, service_id, current_user.id)
    credential = await db.get(ServiceCredential, service_id)
    return ServiceCredentialStatus(
        configured=credential is not None,
        updated_at=credential.updated_at if credential else None,
    )


@router.put(
    "/services/{service_id}/credential",
    response_model=ServiceCredentialStatus,
)
async def set_credential(
    service_id: uuid.UUID,
    payload: ServiceCredentialUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ServiceCredentialStatus:
    service = await get_owned_service(db, service_id, current_user.id)
    if service.kind not in SUPPORTED_CREDENTIAL_KINDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="This service type does not support integration credentials",
        )

    credential = await db.get(ServiceCredential, service_id)
    now = datetime.now(UTC)
    if credential is None:
        credential = ServiceCredential(
            service_id=service_id,
            encrypted_api_key=encrypt_api_key(payload.api_key),
            created_at=now,
            updated_at=now,
        )
        db.add(credential)
    else:
        credential.encrypted_api_key = encrypt_api_key(payload.api_key)
        credential.updated_at = now
    await db.commit()
    return ServiceCredentialStatus(configured=True, updated_at=credential.updated_at)


@router.delete("/services/{service_id}/credential", status_code=status.HTTP_204_NO_CONTENT)
async def delete_credential(
    service_id: uuid.UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    await get_owned_service(db, service_id, current_user.id)
    credential = await db.get(ServiceCredential, service_id)
    if credential is not None:
        await db.delete(credential)
        await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
