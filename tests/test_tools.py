"""Tests for agent/tools.py — ToolRegistry and build_registry."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agent.tools import Tool, ToolRegistry, build_registry


# ── ToolRegistry ───────────────────────────────────────────────────────────────

class TestToolRegistry:
    def _make_tool(self, name: str, return_value: str = "ok") -> Tool:
        schema = {"name": name, "input_schema": {"type": "object", "properties": {}}}
        handler = MagicMock(return_value=return_value)
        return Tool(schema=schema, handler=handler)

    def test_register_and_dispatch(self):
        registry = ToolRegistry()
        tool = self._make_tool("my_tool", '{"status": "ok"}')
        registry.register(tool)

        result = registry.dispatch("my_tool", {"x": 1})

        assert result == '{"status": "ok"}'
        tool.handler.assert_called_once_with({"x": 1})

    def test_dispatch_unknown_tool(self):
        registry = ToolRegistry()
        result = registry.dispatch("nonexistent", {})
        data = json.loads(result)
        assert "error" in data
        assert "nonexistent" in data["error"]

    def test_schemas_returns_all(self):
        registry = ToolRegistry()
        registry.register(self._make_tool("tool_a"))
        registry.register(self._make_tool("tool_b"))
        names = [s["name"] for s in registry.schemas]
        assert "tool_a" in names
        assert "tool_b" in names
        assert len(names) == 2

    def test_register_overwrites_same_name(self):
        registry = ToolRegistry()
        registry.register(self._make_tool("t", return_value="first"))
        registry.register(self._make_tool("t", return_value="second"))
        assert registry.dispatch("t", {}) == "second"

    def test_schemas_order_stable(self):
        registry = ToolRegistry()
        for name in ["z_tool", "a_tool", "m_tool"]:
            registry.register(self._make_tool(name))
        names = [s["name"] for s in registry.schemas]
        assert names == ["z_tool", "a_tool", "m_tool"]


# ── build_registry ─────────────────────────────────────────────────────────────

class TestBuildRegistry:
    def _make_dependencies(self, tmp_path: Path):
        devops = MagicMock()
        purview = MagicMock()
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        return devops, purview, output_dir

    def test_all_tools_registered(self, tmp_path):
        devops, purview, output_dir = self._make_dependencies(tmp_path)
        registry = build_registry(devops, purview, output_dir)
        names = {s["name"] for s in registry.schemas}
        expected = {
            "list_devops_epics",
            "get_epic_details",
            "list_purview_collections",
            "get_workspace_assets",
            "get_cross_workspace_assets",
            "generate_diagram",
        }
        assert names == expected

    def test_list_devops_epics_calls_devops(self, tmp_path):
        devops, purview, output_dir = self._make_dependencies(tmp_path)
        devops.list_epics.return_value = [{"id": 10, "url": "http://..."}]
        devops.get_epic_details.return_value = {"id": 10, "title": "My Epic", "state": "Active"}
        registry = build_registry(devops, purview, output_dir)

        result = json.loads(registry.dispatch("list_devops_epics", {"state": "Active"}))

        devops.list_epics.assert_called_once_with(area_path=None, state="Active")
        assert result[0]["id"] == 10
        assert result[0]["title"] == "My Epic"

    def test_list_devops_epics_area_path(self, tmp_path):
        devops, purview, output_dir = self._make_dependencies(tmp_path)
        devops.list_epics.return_value = []
        registry = build_registry(devops, purview, output_dir)

        registry.dispatch("list_devops_epics", {"area_path": "Proj\\Team"})

        devops.list_epics.assert_called_once_with(area_path="Proj\\Team", state=None)

    def test_get_epic_details(self, tmp_path):
        devops, purview, output_dir = self._make_dependencies(tmp_path)
        devops.get_epic_details.return_value = {"id": 5, "title": "Epic"}
        registry = build_registry(devops, purview, output_dir)

        result = json.loads(registry.dispatch("get_epic_details", {"epic_id": 5}))

        devops.get_epic_details.assert_called_once_with(5)
        assert result["id"] == 5

    def test_list_purview_collections(self, tmp_path):
        devops, purview, output_dir = self._make_dependencies(tmp_path)
        purview.list_collections.return_value = [{"id": "col1", "friendly_name": "Bronze"}]
        registry = build_registry(devops, purview, output_dir)

        result = json.loads(registry.dispatch("list_purview_collections", {}))

        assert result[0]["id"] == "col1"

    def test_get_workspace_assets(self, tmp_path):
        devops, purview, output_dir = self._make_dependencies(tmp_path)
        purview.get_workspace_assets.return_value = {"collection_id": "c1", "lakehouses": []}
        registry = build_registry(devops, purview, output_dir)

        result = json.loads(registry.dispatch("get_workspace_assets", {"collection_id": "c1"}))

        purview.get_workspace_assets.assert_called_once_with("c1")
        assert result["collection_id"] == "c1"

    def test_get_cross_workspace_assets(self, tmp_path):
        devops, purview, output_dir = self._make_dependencies(tmp_path)
        purview.get_cross_workspace_assets.return_value = {"workspaces": {}}
        registry = build_registry(devops, purview, output_dir)

        registry.dispatch("get_cross_workspace_assets", {"collection_ids": ["c1", "c2"]})

        purview.get_cross_workspace_assets.assert_called_once_with(["c1", "c2"])

    def test_generate_diagram_writes_both_files(self, tmp_path):
        devops, purview, output_dir = self._make_dependencies(tmp_path)
        registry = build_registry(devops, purview, output_dir)

        inputs = {
            "epic_id": 42,
            "epic_title": "My Epic",
            "workspace_mode": "single",
            "data_sources": [], "bronze_nodes": [], "silver_nodes": [],
            "gold_nodes": [], "serving_nodes": [], "edges": [],
            "pseudoalgorithm": [], "tradeoffs": [], "unclear_steps": [],
        }
        result = json.loads(registry.dispatch("generate_diagram", inputs))

        assert result["status"] == "ok"
        assert Path(result["drawio"]).exists()
        assert Path(result["drawio"]).suffix == ".drawio"
        assert Path(result["tech_spec"]).exists()
        assert Path(result["tech_spec"]).suffix == ".md"

    def test_generate_diagram_drawio_contains_xml(self, tmp_path):
        devops, purview, output_dir = self._make_dependencies(tmp_path)
        registry = build_registry(devops, purview, output_dir)

        inputs = {
            "epic_id": 42, "epic_title": "My Epic", "workspace_mode": "single",
            "data_sources": [], "bronze_nodes": [], "silver_nodes": [],
            "gold_nodes": [], "serving_nodes": [], "edges": [],
            "pseudoalgorithm": [], "tradeoffs": [], "unclear_steps": [],
        }
        result = json.loads(registry.dispatch("generate_diagram", inputs))

        assert "<?xml" in Path(result["drawio"]).read_text()

    def test_generate_diagram_filename_uses_epic_id_and_slug(self, tmp_path):
        devops, purview, output_dir = self._make_dependencies(tmp_path)
        registry = build_registry(devops, purview, output_dir)

        inputs = {
            "epic_id": 99, "epic_title": "Sales Report!", "workspace_mode": "single",
            "data_sources": [], "bronze_nodes": [], "silver_nodes": [],
            "gold_nodes": [], "serving_nodes": [], "edges": [],
            "pseudoalgorithm": [], "tradeoffs": [], "unclear_steps": [],
        }
        result = json.loads(registry.dispatch("generate_diagram", inputs))

        assert Path(result["drawio"]).name == "99-sales-report.drawio"
        assert Path(result["tech_spec"]).name == "99-sales-report.md"

    def test_generate_diagram_both_files_share_same_stem(self, tmp_path):
        devops, purview, output_dir = self._make_dependencies(tmp_path)
        registry = build_registry(devops, purview, output_dir)

        inputs = {
            "epic_id": 7, "epic_title": "HR Platform", "workspace_mode": "single",
            "data_sources": [], "bronze_nodes": [], "silver_nodes": [],
            "gold_nodes": [], "serving_nodes": [], "edges": [],
            "pseudoalgorithm": [], "tradeoffs": [], "unclear_steps": [],
        }
        result = json.loads(registry.dispatch("generate_diagram", inputs))

        drawio_stem = Path(result["drawio"]).stem
        md_stem = Path(result["tech_spec"]).stem
        assert drawio_stem == md_stem

    def test_dispatch_unknown_tool_returns_error_json(self, tmp_path):
        devops, purview, output_dir = self._make_dependencies(tmp_path)
        registry = build_registry(devops, purview, output_dir)
        result = json.loads(registry.dispatch("nonexistent_tool", {}))
        assert "error" in result
