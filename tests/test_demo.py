"""Tests for agent/demo.py — fixture-backed stub clients."""

import pytest

from agent.demo import DevOpsClientStub, PurviewClientStub


class TestDevOpsClientStub:
    def test_list_epics_returns_results(self):
        stub = DevOpsClientStub()
        result = stub.list_epics()
        assert len(result) > 0
        assert all("id" in e and "url" in e for e in result)

    def test_list_epics_filters_by_state(self):
        stub = DevOpsClientStub()
        active = stub.list_epics(state="Active")
        closed = stub.list_epics(state="Closed")
        assert len(active) > 0
        assert len(closed) == 0

    def test_list_epics_filters_by_area_path(self):
        stub = DevOpsClientStub()
        sales = stub.list_epics(area_path="FabricPlatform\\Sales")
        assert len(sales) == 1

    def test_get_epic_details_returns_all_fields(self):
        stub = DevOpsClientStub()
        epics = stub.list_epics()
        detail = stub.get_epic_details(epics[0]["id"])
        for key in ("id", "title", "state", "description", "acceptance_criteria", "tags", "area_path"):
            assert key in detail

    def test_get_epic_details_id_matches(self):
        stub = DevOpsClientStub()
        detail = stub.get_epic_details(101)
        assert detail["id"] == 101

    def test_get_epic_details_unknown_raises(self):
        stub = DevOpsClientStub()
        with pytest.raises(KeyError):
            stub.get_epic_details(99999)

    def test_descriptions_are_non_empty(self):
        stub = DevOpsClientStub()
        for epic in stub.list_epics():
            detail = stub.get_epic_details(epic["id"])
            assert len(detail["description"]) > 20


class TestPurviewClientStub:
    def test_list_collections_returns_results(self):
        stub = PurviewClientStub()
        result = stub.list_collections()
        assert len(result) > 0
        assert all("id" in c and "friendly_name" in c for c in result)

    def test_list_collections_has_expected_ids(self):
        stub = PurviewClientStub()
        ids = {c["id"] for c in stub.list_collections()}
        assert "sales-bronze" in ids
        assert "sales-silver" in ids
        assert "sales-gold" in ids
        assert "hr-platform" in ids

    def test_get_workspace_assets_returns_shape(self):
        stub = PurviewClientStub()
        result = stub.get_workspace_assets("hr-platform")
        assert result["collection_id"] == "hr-platform"
        assert result["collection_name"] == "HR Platform"
        for key in ("lakehouses", "pipelines", "notebooks", "warehouses", "tables"):
            assert key in result
            assert isinstance(result[key], list)

    def test_get_workspace_assets_hr_has_all_layers(self):
        stub = PurviewClientStub()
        result = stub.get_workspace_assets("hr-platform")
        assert len(result["lakehouses"]) == 3
        assert len(result["pipelines"]) >= 1
        assert len(result["notebooks"]) >= 2
        assert len(result["warehouses"]) >= 1

    def test_get_workspace_assets_sales_bronze_has_pipelines(self):
        stub = PurviewClientStub()
        result = stub.get_workspace_assets("sales-bronze")
        assert len(result["pipelines"]) >= 2

    def test_get_workspace_assets_unknown_collection(self):
        stub = PurviewClientStub()
        result = stub.get_workspace_assets("nonexistent")
        assert result["collection_id"] == "nonexistent"
        assert result["lakehouses"] == []

    def test_get_cross_workspace_assets_returns_shape(self):
        stub = PurviewClientStub()
        result = stub.get_cross_workspace_assets(["sales-bronze", "sales-silver", "sales-gold"])
        assert "workspaces" in result
        assert "cross_workspace_lineage" in result
        assert isinstance(result["cross_workspace_lineage"], list)

    def test_get_cross_workspace_assets_groups_by_collection(self):
        stub = PurviewClientStub()
        result = stub.get_cross_workspace_assets(["sales-bronze", "sales-silver"])
        assert "sales-bronze" in result["workspaces"]
        assert "sales-silver" in result["workspaces"]

    def test_cross_workspace_lineage_hints_for_shared_tables(self):
        stub = PurviewClientStub()
        # raw_orders and raw_products appear in both sales-bronze and sales-silver tables
        result = stub.get_cross_workspace_assets(["sales-bronze", "sales-silver"])
        hints = result["cross_workspace_lineage"]
        assert len(hints) > 0
        table_names = {h["table"] for h in hints}
        assert "raw_orders" in table_names or "raw_products" in table_names

    def test_cross_workspace_workspace_names_resolved(self):
        stub = PurviewClientStub()
        result = stub.get_cross_workspace_assets(["sales-bronze", "sales-silver"])
        assert result["workspaces"]["sales-bronze"]["collection_name"] == "Sales Bronze"
        assert result["workspaces"]["sales-silver"]["collection_name"] == "Sales Silver"
