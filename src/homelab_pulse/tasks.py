import asyncio
from typing import Any

from sqlalchemy import select

from homelab_pulse.celery_app import celery_app
from homelab_pulse.database import async_session_factory, engine
from homelab_pulse.models.service import Service
from homelab_pulse.models.service_check import CheckStatus
from homelab_pulse.monitoring.runner import run_service_check


async def monitor_enabled_services() -> dict[str, int]:
    summary = {"checked": 0, "up": 0, "down": 0, "errors": 0}
    try:
        async with async_session_factory() as db:
            services = list(await db.scalars(select(Service).where(Service.enabled.is_(True))))
            for service in services:
                try:
                    check = await run_service_check(db, service)
                except Exception:
                    await db.rollback()
                    summary["errors"] += 1
                    continue

                summary["checked"] += 1
                if check.status == CheckStatus.UP:
                    summary["up"] += 1
                else:
                    summary["down"] += 1
        return summary
    finally:
        await engine.dispose()


@celery_app.task(name="homelab_pulse.monitor_enabled_services")
def monitor_enabled_services_task() -> dict[str, Any]:
    return asyncio.run(monitor_enabled_services())
