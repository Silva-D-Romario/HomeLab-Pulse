from time import perf_counter
from typing import Any

import httpx

from homelab_pulse.config import get_settings
from homelab_pulse.models.service import ServiceKind
from homelab_pulse.models.service_check import CheckStatus
from homelab_pulse.monitoring.http_probe import ProbeResult


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _jellyfin_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "product": payload.get("ProductName", "Jellyfin"),
        "version": payload.get("Version"),
        "instance_name": payload.get("ServerName"),
        "os": payload.get("OperatingSystem"),
    }


def _portainer_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "product": "Portainer",
        "version": payload.get("Version"),
    }


def _arr_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "product": payload.get("appName", "*arr"),
        "version": payload.get("version"),
        "instance_name": payload.get("instanceName"),
        "os": payload.get("osName"),
        "runtime": payload.get("runtimeName"),
        "runtime_version": payload.get("runtimeVersion"),
    }


async def probe_integration_service(
    kind: ServiceKind,
    target_url: str,
    api_key: str | None,
    client: httpx.AsyncClient | None = None,
) -> ProbeResult:
    if kind == ServiceKind.ARR and not api_key:
        return ProbeResult(
            status=CheckStatus.DOWN,
            response_time_ms=None,
            http_status=None,
            detail="Integration credential not configured",
        )

    headers: dict[str, str] = {}
    if api_key:
        if kind == ServiceKind.JELLYFIN:
            headers["X-Emby-Token"] = api_key
        else:
            headers["X-API-Key"] = api_key

    if kind == ServiceKind.JELLYFIN:
        paths = ["/System/Info/Public"]
        metadata_builder = _jellyfin_metadata
    elif kind == ServiceKind.PORTAINER:
        paths = ["/api/system/status", "/api/status"]
        metadata_builder = _portainer_metadata
    elif kind == ServiceKind.ARR:
        paths = ["/api/v3/system/status"]
        metadata_builder = _arr_metadata
    else:
        return ProbeResult(CheckStatus.DOWN, None, None, "Unsupported integration type")

    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            timeout=get_settings().monitor_timeout_seconds,
            follow_redirects=True,
        )

    started_at = perf_counter()
    try:
        response: httpx.Response | None = None
        for path in paths:
            response = await client.get(_join_url(target_url, path), headers=headers)
            if response.status_code != 404:
                break
        if response is None:
            return ProbeResult(CheckStatus.DOWN, None, None, "Integration endpoint unavailable")

        elapsed_ms = round((perf_counter() - started_at) * 1000)
        if not 200 <= response.status_code < 400:
            return ProbeResult(
                CheckStatus.DOWN,
                elapsed_ms,
                response.status_code,
                f"HTTP {response.status_code}",
            )
        try:
            payload = response.json()
        except ValueError:
            return ProbeResult(
                CheckStatus.DOWN,
                elapsed_ms,
                response.status_code,
                "Invalid JSON response",
            )
        if not isinstance(payload, dict):
            return ProbeResult(
                CheckStatus.DOWN,
                elapsed_ms,
                response.status_code,
                "Unexpected integration response",
            )
        metadata = {
            key: value for key, value in metadata_builder(payload).items() if value is not None
        }
        return ProbeResult(
            CheckStatus.UP,
            elapsed_ms,
            response.status_code,
            integration_data=metadata,
        )
    except httpx.RequestError as error:
        return ProbeResult(
            CheckStatus.DOWN,
            None,
            None,
            f"{type(error).__name__}: {error}"[:500],
        )
    finally:
        if owns_client:
            await client.aclose()
