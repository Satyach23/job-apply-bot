"""lt_common - DataLake client (mock for local dev)."""
import httpx
from lt_common.config import settings


class DataLakeClient:
    """DataLake client - calls mock service or real DataLake."""

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or settings.datalake_base_url

    async def get_object(self, object_id: str, collection_id: str) -> dict | bytes:
        try:
            async with httpx.AsyncClient() as c:
                r = await c.get(
                    f"{self.base_url}/objects/v1/{object_id}",
                    params={"collection-id": collection_id},
                    timeout=10,
                )
                if r.status_code == 200:
                    return r.json() if r.headers.get("content-type", "").startswith("application/json") else r.content
        except Exception:
            pass
        return {}
