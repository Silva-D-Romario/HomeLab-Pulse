from dataclasses import dataclass
from time import perf_counter

import httpx

from homelab_pulse.config import get_settings
from homelab_pulse.models.service_check import CheckStatus


@dataclass(frozen=True, slots=True)
class ProbeResult:
    status: CheckStatus
    response_time_ms: int | None
    http_status: int | None
    detail: str | None = None


async def probe_http_service(
    target_url: str,
    client: httpx.AsyncClient | None = None,
) -> ProbeResult:
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            timeout=get_settings().monitor_timeout_seconds,
            follow_redirects=True,
        )

    started_at = perf_counter()
    try:
        response = await client.get(target_url)
        elapsed_ms = round((perf_counter() - started_at) * 1000)
        status = CheckStatus.UP if 200 <= response.status_code < 400 else CheckStatus.DOWN
        detail = None if status == CheckStatus.UP else f"HTTP {response.status_code}"
        return ProbeResult(status, elapsed_ms, response.status_code, detail)
    except httpx.RequestError as error:
        return ProbeResult(
            status=CheckStatus.DOWN,
            response_time_ms=None,
            http_status=None,
            detail=f"{type(error).__name__}: {error}"[:500],
        )
    finally:
        if owns_client:
            await client.aclose()

