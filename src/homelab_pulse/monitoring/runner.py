from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from homelab_pulse.models.incident import Incident, IncidentStatus
from homelab_pulse.models.service import Service
from homelab_pulse.models.service_check import CheckStatus, ServiceCheck
from homelab_pulse.monitoring.http_probe import probe_http_service


async def run_service_check(db: AsyncSession, service: Service) -> ServiceCheck:
    result = await probe_http_service(service.target_url)
    check = ServiceCheck(
        service_id=service.id,
        status=result.status,
        response_time_ms=result.response_time_ms,
        http_status=result.http_status,
        detail=result.detail,
    )
    db.add(check)

    open_incident = await db.scalar(
        select(Incident).where(
            Incident.service_id == service.id,
            Incident.status == IncidentStatus.OPEN,
        )
    )
    if result.status == CheckStatus.DOWN and open_incident is None:
        db.add(Incident(service_id=service.id, detail=result.detail))
    elif result.status == CheckStatus.UP and open_incident is not None:
        open_incident.status = IncidentStatus.RESOLVED
        open_incident.resolved_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(check)
    return check

