"""Tests for purview/client.py — Microsoft Purview Data Map client."""

import time
from unittest.mock import MagicMock, patch

import pytest

from purview.client import PurviewClient, _infer_cross_workspace_lineage


def _make_client() -> PurviewClient:
    return PurviewClient(
        tenant_id="tenant-123",
        client_id="client-abc",
        client_secret="secret-xyz",
        account_name="mypurview",
    )


def _mock_response(body: dict | list, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = body
    resp.raise_for_status = MagicMock()
    if status >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status}")
    return resp


def _token_response() -> MagicMock:
    return _mock_response({"access_token": "tok123", "expires_in": 3600})


# ── Authentication ─────────────────────────────────────────────────────────────

class TestGetToken:
    def test_fetches_token_on_first_call(self):
        client = _make_client()
        with patch("httpx.post", return_value=_token_response()) as mock_post:
            token = client._get_token()
        assert token == "tok123"
        mock_post.assert_called_once()

    def test_caches_token(self):
        client = _make_client()
        with patch("httpx.post", return_value=_token_response()) as mock_post:
            client._get_token()
            client._get_token()
        assert mock_post.call_count == 1

    def test_refreshes_expired_token(self):
        client = _make_client()
        client._token = "old-token"
        client._token_expiry = time.time() - 10  # expired
        with patch("httpx.post", return_value=_token_response()):
            token = client._get_token()
        assert token == "tok123"

    def test_uses_safety_margin(self):
        client = _make_client()
        client._token = "valid-token"
        client._token_expiry = time.time() + 30  # within 60s safety margin
        with patch("httpx.post", return_value=_token_response()):
            token = client._get_token()
        assert token == "tok123"  # refreshed

    def test_token_not_refreshed_when_fresh(self):
        client = _make_client()
        client._token = "fresh-token"
        client._token_expiry = time.time() + 3600
        with patch("httpx.post") as mock_post:
            token = client._get_token()
        assert token == "fresh-token"
        mock_post.assert_not_called()


# ── list_collections ───────────────────────────────────────────────────────────

class TestListCollections:
    def _setup(self, collections: list[dict]) -> PurviewClient:
        client = _make_client()
        client._token = "tok"
        client._token_expiry = time.time() + 3600
        return client, _mock_response({"value": collections})

    def test_returns_mapped_collections(self):
        client, resp = self._setup([{
            "name": "col1",
            "friendlyName": "Bronze WS",
            "description": "desc",
            "parentCollection": {"referenceName": "root"},
        }])
        with patch("httpx.get", return_value=resp):
            result = client.list_collections()
        assert result[0]["id"] == "col1"
        assert result[0]["friendly_name"] == "Bronze WS"
        assert result[0]["parent_collection"] == "root"

    def test_friendly_name_fallback_to_name(self):
        client, resp = self._setup([{"name": "col2", "friendlyName": None}])
        with patch("httpx.get", return_value=resp):
            result = client.list_collections()
        assert result[0]["friendly_name"] == "col2"

    def test_empty_collections(self):
        client, resp = self._setup([])
        with patch("httpx.get", return_value=resp):
            result = client.list_collections()
        assert result == []


# ── get_workspace_assets ───────────────────────────────────────────────────────

class TestGetWorkspaceAssets:
    def _make_asset(self, entity_type: str, display_text: str, collection_id: str) -> dict:
        return {
            "entityType": entity_type,
            "displayText": display_text,
            "id": f"id-{display_text}",
            "qualifiedName": f"{display_text}/qualified",
            "collectionId": collection_id,
        }

    def test_lakehouses_classified(self):
        client = _make_client()
        client._token = "tok"
        client._token_expiry = time.time() + 3600

        assets = [self._make_asset("microsoft_fabric_lakehouse", "MyLakehouse", "col1")]
        collections = [{"name": "col1", "friendlyName": "Bronze", "description": "", "parentCollection": None}]

        with patch("httpx.post", return_value=_mock_response({"value": assets})):
            with patch("httpx.get", return_value=_mock_response({"value": collections})):
                result = client.get_workspace_assets("col1")

        assert len(result["lakehouses"]) == 1
        assert result["lakehouses"][0]["name"] == "MyLakehouse"

    def test_includes_collection_metadata(self):
        client = _make_client()
        client._token = "tok"
        client._token_expiry = time.time() + 3600

        with patch("httpx.post", return_value=_mock_response({"value": []})):
            with patch("httpx.get", return_value=_mock_response({"value": [
                {"name": "col1", "friendlyName": "My Workspace", "description": "", "parentCollection": None}
            ]})):
                result = client.get_workspace_assets("col1")

        assert result["collection_id"] == "col1"
        assert result["collection_name"] == "My Workspace"

    def test_multiple_asset_types(self):
        client = _make_client()
        client._token = "tok"
        client._token_expiry = time.time() + 3600

        assets = [
            self._make_asset("microsoft_fabric_pipeline", "Pipeline1", "col1"),
            self._make_asset("microsoft_fabric_notebook", "Notebook1", "col1"),
            self._make_asset("microsoft_fabric_warehouse", "WH1", "col1"),
        ]
        with patch("httpx.post", return_value=_mock_response({"value": assets})):
            with patch("httpx.get", return_value=_mock_response({"value": [
                {"name": "col1", "friendlyName": "WS", "description": "", "parentCollection": None}
            ]})):
                result = client.get_workspace_assets("col1")

        assert len(result["pipelines"]) == 1
        assert len(result["notebooks"]) == 1
        assert len(result["warehouses"]) == 1

    def test_unknown_entity_type_ignored(self):
        client = _make_client()
        client._token = "tok"
        client._token_expiry = time.time() + 3600

        assets = [{"entityType": "unknown_type", "displayText": "Ghost", "id": "g", "qualifiedName": "q", "collectionId": "col1"}]
        with patch("httpx.post", return_value=_mock_response({"value": assets})):
            with patch("httpx.get", return_value=_mock_response({"value": [
                {"name": "col1", "friendlyName": "WS", "description": "", "parentCollection": None}
            ]})):
                result = client.get_workspace_assets("col1")

        for key in ("lakehouses", "pipelines", "notebooks", "warehouses", "tables"):
            assert result[key] == []


# ── get_cross_workspace_assets ─────────────────────────────────────────────────

class TestGetCrossWorkspaceAssets:
    def test_assets_grouped_by_workspace(self):
        client = _make_client()
        client._token = "tok"
        client._token_expiry = time.time() + 3600

        assets = [
            {"entityType": "microsoft_fabric_lakehouse", "displayText": "LH_Bronze", "id": "1",
             "qualifiedName": "q1", "collectionId": "col1"},
            {"entityType": "microsoft_fabric_lakehouse", "displayText": "LH_Silver", "id": "2",
             "qualifiedName": "q2", "collectionId": "col2"},
        ]
        collections = [
            {"name": "col1", "friendlyName": "Bronze WS", "description": "", "parentCollection": None},
            {"name": "col2", "friendlyName": "Silver WS", "description": "", "parentCollection": None},
        ]
        with patch("httpx.post", return_value=_mock_response({"value": assets})):
            with patch("httpx.get", return_value=_mock_response({"value": collections})):
                result = client.get_cross_workspace_assets(["col1", "col2"])

        assert "col1" in result["workspaces"]
        assert "col2" in result["workspaces"]
        assert len(result["workspaces"]["col1"]["lakehouses"]) == 1
        assert result["workspaces"]["col1"]["lakehouses"][0]["name"] == "LH_Bronze"

    def test_cross_workspace_lineage_hints_included(self):
        client = _make_client()
        client._token = "tok"
        client._token_expiry = time.time() + 3600

        # Same table name in two workspaces triggers a lineage hint
        assets = [
            {"entityType": "microsoft_fabric_table", "displayText": "sales_fact", "id": "t1",
             "qualifiedName": "q/t1", "collectionId": "col1"},
            {"entityType": "microsoft_fabric_table", "displayText": "sales_fact", "id": "t2",
             "qualifiedName": "q/t2", "collectionId": "col2"},
        ]
        collections = [
            {"name": "col1", "friendlyName": "Bronze", "description": "", "parentCollection": None},
            {"name": "col2", "friendlyName": "Silver", "description": "", "parentCollection": None},
        ]
        with patch("httpx.post", return_value=_mock_response({"value": assets})):
            with patch("httpx.get", return_value=_mock_response({"value": collections})):
                result = client.get_cross_workspace_assets(["col1", "col2"])

        hints = result["cross_workspace_lineage"]
        assert len(hints) >= 1
        assert hints[0]["table"] == "sales_fact"


# ── _infer_cross_workspace_lineage ─────────────────────────────────────────────

class TestInferCrossWorkspaceLineage:
    def test_no_shared_tables_no_hints(self):
        by_workspace = {
            "ws1": [{"entityType": "microsoft_fabric_table", "displayText": "table_a"}],
            "ws2": [{"entityType": "microsoft_fabric_table", "displayText": "table_b"}],
        }
        hints = _infer_cross_workspace_lineage(by_workspace, ["table_a", "table_b"])
        assert hints == []

    def test_shared_table_produces_hint(self):
        by_workspace = {
            "ws1": [{"entityType": "microsoft_fabric_table", "displayText": "shared_table"}],
            "ws2": [{"entityType": "microsoft_fabric_table", "displayText": "shared_table"}],
        }
        hints = _infer_cross_workspace_lineage(by_workspace, ["shared_table"])
        assert len(hints) == 1
        assert hints[0]["table"] == "shared_table"
        assert hints[0]["from_workspace"] == "ws1"
        assert hints[0]["to_workspace"] == "ws2"

    def test_non_table_assets_ignored(self):
        by_workspace = {
            "ws1": [{"entityType": "microsoft_fabric_lakehouse", "displayText": "lh"}],
            "ws2": [{"entityType": "microsoft_fabric_lakehouse", "displayText": "lh"}],
        }
        hints = _infer_cross_workspace_lineage(by_workspace, [])
        assert hints == []

    def test_three_workspaces_shared_table(self):
        by_workspace = {
            "ws1": [{"entityType": "microsoft_fabric_table", "displayText": "t"}],
            "ws2": [{"entityType": "microsoft_fabric_table", "displayText": "t"}],
            "ws3": [{"entityType": "microsoft_fabric_table", "displayText": "t"}],
        }
        hints = _infer_cross_workspace_lineage(by_workspace, ["t"])
        assert len(hints) == 2
