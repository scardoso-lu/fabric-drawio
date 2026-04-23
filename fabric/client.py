import time
import httpx


class FabricClient:
    _TOKEN_URL = "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    _FABRIC_BASE = "https://api.fabric.microsoft.com/v1"

    def __init__(self, tenant_id: str, client_id: str, client_secret: str, workspace_id: str):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.workspace_id = workspace_id
        self._token: str | None = None
        self._token_expiry: float = 0

    def _get_token(self) -> str:
        if self._token and time.time() < self._token_expiry - 60:
            return self._token
        resp = httpx.post(
            self._TOKEN_URL.format(tenant_id=self.tenant_id),
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "https://api.fabric.microsoft.com/.default",
            },
            timeout=30,
        )
        resp.raise_for_status()
        body = resp.json()
        self._token = body["access_token"]
        self._token_expiry = time.time() + body.get("expires_in", 3600)
        return self._token

    def _get(self, path: str) -> list[dict]:
        headers = {"Authorization": f"Bearer {self._get_token()}"}
        resp = httpx.get(
            f"{self._FABRIC_BASE}{path}",
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("value", [])

    def get_workspace_context(self) -> dict:
        wid = self.workspace_id
        lakehouses = self._get(f"/workspaces/{wid}/lakehouses")
        pipelines = self._get(f"/workspaces/{wid}/datapipelines")
        notebooks = self._get(f"/workspaces/{wid}/notebooks")
        return {
            "workspace_id": wid,
            "lakehouses": [{"id": i.get("id"), "name": i.get("displayName")} for i in lakehouses],
            "pipelines": [{"id": i.get("id"), "name": i.get("displayName")} for i in pipelines],
            "notebooks": [{"id": i.get("id"), "name": i.get("displayName")} for i in notebooks],
        }
