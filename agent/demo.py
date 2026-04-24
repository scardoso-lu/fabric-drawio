"""
Stub clients that serve fixture data from examples/ — no network calls, no credentials.

Usage: pass --demo to agent.main to use these instead of the real API clients.
"""

import json
from pathlib import Path

from purview.client import _infer_cross_workspace_lineage

_EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


class DevOpsClientStub:
    """Serves epics from examples/devops_epics.json."""

    def __init__(self) -> None:
        self._epics: list[dict] = json.loads(
            (_EXAMPLES_DIR / "devops_epics.json").read_text(encoding="utf-8")
        )

    def list_epics(
        self, area_path: str | None = None, state: str | None = None
    ) -> list[dict]:
        epics = self._epics
        if state:
            epics = [e for e in epics if e["state"] == state]
        if area_path:
            epics = [e for e in epics if e["area_path"].startswith(area_path)]
        return [{"id": e["id"], "url": f"https://example.visualstudio.com/_workitems/edit/{e['id']}"} for e in epics]

    def get_epic_details(self, epic_id: int) -> dict:
        for epic in self._epics:
            if epic["id"] == epic_id:
                return epic
        raise KeyError(f"Epic {epic_id} not found in example data")


class PurviewClientStub:
    """Serves collections and assets from examples/purview_collections.json and purview_assets.json."""

    def __init__(self) -> None:
        self._collections: list[dict] = json.loads(
            (_EXAMPLES_DIR / "purview_collections.json").read_text(encoding="utf-8")
        )
        self._assets: dict[str, dict] = json.loads(
            (_EXAMPLES_DIR / "purview_assets.json").read_text(encoding="utf-8")
        )

    def list_collections(self) -> list[dict]:
        return self._collections

    def get_workspace_assets(self, collection_id: str) -> dict:
        data = self._assets.get(collection_id, {})
        return {
            "collection_id": collection_id,
            "collection_name": data.get("collection_name", collection_id),
            "lakehouses": data.get("lakehouses", []),
            "pipelines": data.get("pipelines", []),
            "notebooks": data.get("notebooks", []),
            "warehouses": data.get("warehouses", []),
            "tables": data.get("tables", []),
        }

    def get_cross_workspace_assets(self, collection_ids: list[str]) -> dict:
        workspaces: dict[str, dict] = {}
        by_workspace: dict[str, list] = {}
        for cid in collection_ids:
            data = self._assets.get(cid, {})
            workspaces[cid] = {
                "collection_name": data.get("collection_name", cid),
                "lakehouses": data.get("lakehouses", []),
                "pipelines": data.get("pipelines", []),
                "notebooks": data.get("notebooks", []),
                "warehouses": data.get("warehouses", []),
                "tables": data.get("tables", []),
            }
            by_workspace[cid] = [
                {"entityType": "microsoft_fabric_table", "displayText": t["name"]}
                for t in data.get("tables", [])
            ]

        lineage_hints = _infer_cross_workspace_lineage(by_workspace, [])
        return {"workspaces": workspaces, "cross_workspace_lineage": lineage_hints}
