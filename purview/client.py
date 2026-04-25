import time
import httpx

# Fabric entity types registered in Purview's Data Map
_FABRIC_ENTITY_TYPES = [
    "microsoft_fabric_lakehouse",
    "microsoft_fabric_pipeline",
    "microsoft_fabric_notebook",
    "microsoft_fabric_warehouse",
    "microsoft_fabric_table",
]

_COLLECTION_API_VERSION = "2019-11-01-preview"
_DATAMAP_API_VERSION = "2023-09-01"


class PurviewClient:
    def __init__(self, tenant_id: str, client_id: str, client_secret: str, account_name: str):
        self.account_name = account_name
        self._account_base = f"https://{account_name}.purview.azure.com/account"
        self._datamap_base = f"https://{account_name}.purview.azure.com/datamap/api"
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self._token: str | None = None
        self._token_expiry: float = 0

    # ── Authentication ────────────────────────────────────────────────────────

    def _get_token(self) -> str:
        if self._token and time.time() < self._token_expiry - 60:
            return self._token
        resp = httpx.post(
            f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "https://purview.azure.com/.default",
            },
            timeout=30,
        )
        resp.raise_for_status()
        body = resp.json()
        self._token = body["access_token"]
        self._token_expiry = time.time() + body.get("expires_in", 3600)
        return self._token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._get_token()}"}

    # ── Collections (workspaces) ──────────────────────────────────────────────

    def list_collections(self) -> list[dict]:
        """Return all Purview collections. Each collection maps to a Fabric workspace scope."""
        resp = httpx.get(
            f"{self._account_base}/collections",
            params={"api-version": _COLLECTION_API_VERSION},
            headers=self._headers(),
            timeout=30,
        )
        resp.raise_for_status()
        items = resp.json().get("value", [])
        return [
            {
                "id": c.get("name"),
                "friendly_name": c.get("friendlyName") or c.get("name"),
                "description": c.get("description", ""),
                "parent_collection": (c.get("parentCollection") or {}).get("referenceName"),
            }
            for c in items
        ]

    # ── Asset discovery ───────────────────────────────────────────────────────

    def _search(self, collection_ids: list[str], entity_types: list[str] | None = None) -> list[dict]:
        """Run a discovery query scoped to given collections and entity types."""
        types = entity_types or _FABRIC_ENTITY_TYPES
        filters: list[dict] = [
            {"or": [{"collectionId": cid} for cid in collection_ids]},
            {"or": [{"entityType": t} for t in types]},
        ]
        payload = {"keywords": None, "filter": {"and": filters}, "limit": 1000}
        resp = httpx.post(
            f"{self._datamap_base}/discovery/query",
            params={"api-version": _DATAMAP_API_VERSION},
            headers=self._headers(),
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("value", [])

    def _classify(self, assets: list[dict], collection_id: str | None = None) -> dict:
        """Group raw search results by Fabric item type."""
        result: dict = {
            "lakehouses": [], "pipelines": [], "notebooks": [],
            "warehouses": [], "tables": [],
        }
        type_map = {
            "microsoft_fabric_lakehouse": "lakehouses",
            "microsoft_fabric_pipeline": "pipelines",
            "microsoft_fabric_notebook": "notebooks",
            "microsoft_fabric_warehouse": "warehouses",
            "microsoft_fabric_table": "tables",
        }
        for asset in assets:
            bucket = type_map.get(asset.get("entityType", ""))
            if not bucket:
                continue
            entry = {
                "id": asset.get("id"),
                "name": asset.get("displayText") or asset.get("name", ""),
                "qualified_name": asset.get("qualifiedName", ""),
                "collection_id": asset.get("collectionId") or collection_id,
            }
            if bucket == "tables":
                entry["parent_asset"] = asset.get("qualifiedName", "").split("/")[0]
            result[bucket].append(entry)
        return result

    def get_workspace_assets(self, collection_id: str) -> dict:
        """Return all catalogued Fabric assets in a single Purview collection."""
        assets = self._search([collection_id])
        classified = self._classify(assets, collection_id)
        # Resolve the friendly collection name
        collections = {c["id"]: c["friendly_name"] for c in self.list_collections()}
        return {
            "collection_id": collection_id,
            "collection_name": collections.get(collection_id, collection_id),
            **classified,
        }

    def get_cross_workspace_assets(self, collection_ids: list[str]) -> dict:
        """Return assets across multiple collections plus cross-workspace lineage hints."""
        collections = {c["id"]: c["friendly_name"] for c in self.list_collections()}
        assets = self._search(collection_ids)

        # Group by collection
        by_workspace: dict[str, list] = {cid: [] for cid in collection_ids}
        for asset in assets:
            cid = asset.get("collectionId")
            if cid in by_workspace:
                by_workspace[cid].append(asset)

        workspaces = {
            cid: {
                "collection_name": collections.get(cid, cid),
                **self._classify(asset_list, cid),
            }
            for cid, asset_list in by_workspace.items()
        }

        lineage_hints = _infer_cross_workspace_lineage(by_workspace)

        return {"workspaces": workspaces, "cross_workspace_lineage": lineage_hints}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _infer_cross_workspace_lineage(by_workspace: dict[str, list]) -> list[dict]:
    """
    Produce lightweight lineage hints when a table name appears in multiple workspaces
    (common in Bronze→Silver→Gold split-workspace patterns).
    """
    name_to_workspaces: dict[str, list[str]] = {}
    for cid, assets in by_workspace.items():
        for asset in assets:
            name = asset.get("displayText", "")
            if asset.get("entityType") == "microsoft_fabric_table" and name:
                name_to_workspaces.setdefault(name, []).append(cid)

    hints = []
    for name, workspaces in name_to_workspaces.items():
        if len(workspaces) > 1:
            for i in range(len(workspaces) - 1):
                hints.append({
                    "table": name,
                    "from_workspace": workspaces[i],
                    "to_workspace": workspaces[i + 1],
                    "hint": "same table name appears in multiple workspaces",
                })
    return hints
