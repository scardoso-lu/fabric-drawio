import json
import os
from pathlib import Path

from .devops_client import DevOpsClient
from .fabric_client import FabricClient
from .diagram import build_drawio, slugify

# ── Tool schemas (passed to Claude) ──────────────────────────────────────────

TOOL_SCHEMAS = [
    {
        "name": "list_devops_epics",
        "description": (
            "List all epics in the Azure DevOps project. "
            "Returns a list with id and title for each epic."
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
        "name": "get_fabric_context",
        "description": (
            "Fetch the existing Microsoft Fabric workspace items: "
            "lakehouses, data pipelines, and notebooks. "
            "Use this once to understand what resources already exist before designing diagrams."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "generate_diagram",
        "description": (
            "Generate a .drawio medallion architecture diagram for a single epic and write it to disk. "
            "All name values must be plain text — no HTML tags. "
            "Reuse existing Fabric resource names from get_fabric_context where applicable. "
            "The 'type' field controls node shape/colour: "
            "use 'source' for data sources, 'pipeline' for pipelines/dataflows, "
            "'lakehouse' for Delta lakehouses, 'notebook' for PySpark notebooks, "
            "'semantic_model' for Direct Lake models, 'report' for Power BI reports."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "epic_id": {"type": "integer"},
                "epic_title": {"type": "string"},
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
                            "type": {"type": "string", "enum": ["pipeline", "dataflow", "lakehouse", "notebook", "default"]},
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
                            "type": {"type": "string", "enum": ["pipeline", "dataflow", "lakehouse", "notebook", "default"]},
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
                            "type": {"type": "string", "enum": ["pipeline", "dataflow", "lakehouse", "notebook", "default"]},
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
                            "type": {"type": "string", "enum": ["semantic_model", "report", "default"]},
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
                "epic_id", "epic_title",
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
    fabric: FabricClient,
    output_dir: Path,
) -> str:
    if name == "list_devops_epics":
        epics = devops.list_epics(
            area_path=inputs.get("area_path"),
            state=inputs.get("state"),
        )
        # Enrich with titles to save Claude an extra round-trip
        result = []
        for ep in epics:
            details = devops.get_epic_details(ep["id"])
            result.append({"id": details["id"], "title": details["title"], "state": details["state"]})
        return json.dumps(result)

    if name == "get_epic_details":
        return json.dumps(devops.get_epic_details(inputs["epic_id"]))

    if name == "get_fabric_context":
        return json.dumps(fabric.get_workspace_context())

    if name == "generate_diagram":
        xml = build_drawio(inputs)
        filename = f"{inputs['epic_id']}-{slugify(inputs['epic_title'])}.drawio"
        out_path = output_dir / filename
        out_path.write_text(xml, encoding="utf-8")
        return json.dumps({"status": "ok", "file": str(out_path)})

    return json.dumps({"error": f"Unknown tool: {name}"})
