import httpx

from homelab_pulse.config import get_settings
from homelab_pulse.schemas.agent import ContainerSummary


async def fetch_containers(client: httpx.AsyncClient | None = None) -> list[ContainerSummary]:
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=10.0)

    try:
        response = await client.get(
            f"{get_settings().docker_api_url}/containers/json",
            params={"all": "true"},
        )
        response.raise_for_status()
        containers = []
        for item in response.json():
            names = item.get("Names") or []
            name = names[0].removeprefix("/") if names else item["Id"][:12]
            containers.append(
                ContainerSummary(
                    id=item["Id"],
                    name=name,
                    image=item.get("Image", "unknown"),
                    state=item.get("State", "unknown"),
                    status=item.get("Status", "unknown"),
                )
            )
        return containers
    finally:
        if owns_client:
            await client.aclose()

