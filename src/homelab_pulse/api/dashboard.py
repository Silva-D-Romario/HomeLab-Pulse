from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from homelab_pulse.database import get_db
from homelab_pulse.dependencies import CurrentUser
from homelab_pulse.models.incident import Incident, IncidentStatus
from homelab_pulse.models.server import Server
from homelab_pulse.models.service import Service
from homelab_pulse.models.service_check import CheckStatus, ServiceCheck
from homelab_pulse.schemas.dashboard import (
    DashboardCheckPoint,
    DashboardResponse,
    DashboardServiceMetric,
)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse, summary="Retorna indicadores do dashboard")
async def get_dashboard(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> DashboardResponse:
    now = datetime.now(UTC)
    window_hours = 24
    cutoff = now - timedelta(hours=window_hours)

    servers_total = await db.scalar(
        select(func.count(Server.id)).where(Server.owner_id == current_user.id)
    )
    services = list(
        await db.scalars(
            select(Service)
            .join(Server, Service.server_id == Server.id)
            .where(Server.owner_id == current_user.id)
            .order_by(Service.name)
        )
    )
    service_ids = [service.id for service in services]

    checks: list[ServiceCheck] = []
    open_incidents = 0
    if service_ids:
        checks = list(
            await db.scalars(
                select(ServiceCheck)
                .where(
                    ServiceCheck.service_id.in_(service_ids),
                    ServiceCheck.checked_at >= cutoff,
                )
                .order_by(ServiceCheck.checked_at.desc())
                .limit(500)
            )
        )
        open_incidents = (
            await db.scalar(
                select(func.count(Incident.id)).where(
                    Incident.service_id.in_(service_ids),
                    Incident.status == IncidentStatus.OPEN,
                )
            )
            or 0
        )

    checks_by_service: dict[object, list[ServiceCheck]] = defaultdict(list)
    for check in checks:
        checks_by_service[check.service_id].append(check)

    service_metrics: list[DashboardServiceMetric] = []
    services_up = 0
    services_down = 0
    for service in services:
        service_checks = checks_by_service[service.id]
        latest_check = service_checks[0] if service_checks else None
        latest_status = latest_check.status if latest_check else None
        if latest_status == CheckStatus.UP:
            services_up += 1
        elif latest_status == CheckStatus.DOWN:
            services_down += 1

        response_times = [
            check.response_time_ms
            for check in service_checks
            if check.response_time_ms is not None
        ]
        successful_checks = sum(check.status == CheckStatus.UP for check in service_checks)
        service_metrics.append(
            DashboardServiceMetric(
                id=service.id,
                name=service.name,
                status=latest_status,
                availability_percent=(
                    round(successful_checks / len(service_checks) * 100, 1)
                    if service_checks
                    else None
                ),
                average_response_time_ms=(
                    round(sum(response_times) / len(response_times)) if response_times else None
                ),
                last_checked_at=latest_check.checked_at if latest_check else None,
                integration_data=latest_check.integration_data if latest_check else None,
            )
        )

    service_names = {service.id: service.name for service in services}
    response_times = [
        check.response_time_ms for check in checks if check.response_time_ms is not None
    ]
    successful_checks = sum(check.status == CheckStatus.UP for check in checks)

    return DashboardResponse(
        generated_at=now,
        window_hours=window_hours,
        servers_total=servers_total or 0,
        services_total=len(services),
        services_up=services_up,
        services_down=services_down,
        services_unknown=len(services) - services_up - services_down,
        open_incidents=open_incidents,
        availability_percent=(
            round(successful_checks / len(checks) * 100, 1) if checks else None
        ),
        average_response_time_ms=(
            round(sum(response_times) / len(response_times)) if response_times else None
        ),
        services=service_metrics,
        recent_checks=[
            DashboardCheckPoint(
                service_id=check.service_id,
                service_name=service_names[check.service_id],
                status=check.status,
                response_time_ms=check.response_time_ms,
                checked_at=check.checked_at,
            )
            for check in reversed(checks[:100])
        ],
    )
