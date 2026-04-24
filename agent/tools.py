import json
from pathlib import Path

from devops.client import DevOpsClient
from purview.client import PurviewClient
from drawio.builder import build_drawio, slugify

# ── Tool schemas (passed to Claude) ──────────────────────────────────────────

TOOL_SCHEMAS = [
    {
        "name": "list_devops_epics",
        "description": (
            "List all epics in the Azure DevOps project. "
            "Returns a list with id, title, and state for each epic."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "area_path": {
                    "type": "string",
                    "description": "Optional area path to filter epics (e.g. 'MyProject\\Team A').",
                },
                "state": {
                    "type": "string",
                    "description": "Optional state filter (e.g. 'Active', 'New', 'Resolved').",
                },
            },
            "required": [],
        },
    },
    {
        "name": "get_epic_details",
        "description": (
            "Get full details of a specific Azure DevOps epic including "
            "description, acceptance criteria, tags, and area path."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "epic_id": {
                    "type": "integer",
                    "description": "The numeric ID of the Azure DevOps work item.",
                },
            },
            "required": ["epic_id"],
        },
    },
    {
        "name": "list_purview_collections",
        "description": (
            "List all Microsoft Purview collections. Each collection represents a catalogued "
            "scope — typically a Fabric workspace or organisational domain. "
            "Call this first to understand available workspace scopes before querying assets."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "get_workspace_assets",
        "description": (
            "Get all Fabric assets catalogued in a single Purview collection (workspace): "
            "lakehouses, pipelines, notebooks, warehouses, and tables. "
            "Use when an epic is scoped to one workspace."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "collection_id": {
                    "type": "string",
                    "description": "The Purview collection ID returned by list_purview_collections.",
                },
            },
            "required": ["collection_id"],
        },
    },
    {
        "name": "get_cross_workspace_assets",
        "description": (
            "Get Fabric assets across multiple Purview collections and infer cross-workspace "
            "lineage hints (e.g. Bronze workspace → Silver workspace → Gold workspace). "
            "Use when an epic spans multiple workspaces or when related workspaces need "
            "to be shown together in one architecture diagram."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "collection_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of Purview collection IDs to query together.",
                    "minItems": 2,
                },
            },
            "required": ["collection_ids"],
        },
    },
    {
        "name": "generate_diagram",
        "description": (
            "Generate a .drawio medallion architecture diagram for a single epic and write it to disk. "
            "All name values must be plain text — no HTML tags. "
            "Reuse exact asset names from Purview. "
            "The 'type' field controls node shape/colour: "
            "use 'source' for data sources, 'pipeline' for pipelines/dataflows, "
            "'lakehouse' for Delta lakehouses, 'notebook' for PySpark notebooks, "
            "'warehouse' for Fabric Warehouses, "
            "'semantic_model' for Direct Lake models, 'report' for Power BI reports. "
            "Set workspace_mode to 'single' or 'cross' to record how the diagram was scoped."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "epic_id": {"type": "integer"},
                "epic_title": {"type": "string"},
                "workspace_mode": {
                    "type": "string",
                    "enum": ["single", "cross"],
                    "description": "Whether the diagram covers one workspace or multiple.",
                },
                "data_sources": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "type": {"type": "string", "enum": ["source"]},
                        },
                        "required": ["name", "type"],
                    },
                },
                "bronze_nodes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "type": {"type": "string", "enum": ["pipeline", "dataflow", "lakehouse", "notebook", "warehouse", "default"]},
                            "workspace": {"type": "string", "description": "Collection friendly name (cross-workspace mode only)"},
                        },
                        "required": ["name", "type"],
                    },
                },
                "silver_nodes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "type": {"type": "string", "enum": ["pipeline", "dataflow", "lakehouse", "notebook", "warehouse", "default"]},
                            "workspace": {"type": "string"},
                        },
                        "required": ["name", "type"],
                    },
                },
                "gold_nodes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "type": {"type": "string", "enum": ["pipeline", "dataflow", "lakehouse", "notebook", "warehouse", "default"]},
                            "workspace": {"type": "string"},
                        },
                        "required": ["name", "type"],
                    },
                },
                "serving_nodes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "type": {"type": "string", "enum": ["semantic_model", "report", "warehouse", "default"]},
                            "workspace": {"type": "string"},
                        },
                        "required": ["name", "type"],
                    },
                },
                "edges": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "from": {"type": "string"},
                            "to": {"type": "string"},
                            "label": {"type": "string"},
                        },
                        "required": ["from", "to"],
                    },
                },
            },
            "required": [
                "epic_id", "epic_title", "workspace_mode",
                "data_sources", "bronze_nodes", "silver_nodes",
                "gold_nodes", "serving_nodes", "edges",
            ],
        },
    },
]


# ── Tool dispatcher ───────────────────────────────────────────────────────────

def dispatch_tool(
    name: str,
    inputs: dict,
    devops: DevOpsClient,
    purview: PurviewClient,
    output_dir: Path,
) -> str:
    if name == "list_devops_epics":
        epics = devops.list_epics(
            area_path=inputs.get("area_path"),
            state=inputs.get("state"),
        )
        result = []
        for ep in epics:
            details = devops.get_epic_details(ep["id"])
            result.append({"id": details["id"], "title": details["title"], "state": details["state"]})
        return json.dumps(result)

    if name == "get_epic_details":
        return json.dumps(devops.get_epic_details(inputs["epic_id"]))

    if name == "list_purview_collections":
        return json.dumps(purview.list_collections())

    if name == "get_workspace_assets":
        return json.dumps(purview.get_workspace_assets(inputs["collection_id"]))

    if name == "get_cross_workspace_assets":
        return json.dumps(purview.get_cross_workspace_assets(inputs["collection_ids"]))

    if name == "generate_diagram":
        xml = build_drawio(inputs)
        filename = f"{inputs['epic_id']}-{slugify(inputs['epic_title'])}.drawio"
        out_path = output_dir / filename
        out_path.write_text(xml, encoding="utf-8")
        return json.dumps({"status": "ok", "file": str(out_path)})

    return json.dumps({"error": f"Unknown tool: {name}"})
