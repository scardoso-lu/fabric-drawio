"""
Fabric Medallion Architecture Agent

Fetches epics from Azure DevOps and existing resources from Microsoft Fabric,
then generates one .drawio medallion architecture diagram per epic.

Usage:
    python -m agent.main [--area-path "MyProject\\Team"] [--state Active]
"""

import argparse
import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from devops.client import DevOpsClient
from fabric.client import FabricClient
from .tools import TOOL_SCHEMAS, dispatch_tool

load_dotenv()

SYSTEM_PROMPT = """You are a Principal Data Architect specialising in Microsoft Fabric
Medallion Architecture (Bronze / Silver / Gold). Your job each run:

1. Call list_devops_epics to get all epics (optionally filtered by area_path / state).
2. Call get_fabric_context once to learn which Lakehouses, Pipelines, and Notebooks
   already exist in the workspace.
3. For each epic call get_epic_details to read its title, description, and acceptance
   criteria.
4. Reason about the appropriate medallion architecture for that epic:
   - Map data sources from the epic description to DATA SOURCES nodes.
   - Decide which existing Fabric resources (lakehouses, pipelines, notebooks) belong
     in Bronze / Silver / Gold. Reuse existing resource names where appropriate.
   - Add a SERVING layer with semantic models or reports as implied by the epic.
   - Define edges (from, to, label) for every data-flow hop.
5. Call generate_diagram for the epic. All node names must be plain text —
   absolutely no HTML tags in any label.
6. After all epics are processed, output a short summary: list each epic ID + title
   and the filename of the diagram generated.

Rules:
- Never invent Fabric resources that were not found in get_fabric_context or implied
  by the epic requirements.
- If an epic has no clear data-engineering scope, skip it and explain why.
- One diagram per epic; do not batch multiple epics into one diagram.
"""


def _require(var: str) -> str:
    value = os.getenv(var)
    if not value:
        print(f"ERROR: environment variable {var} is not set.", file=sys.stderr)
        sys.exit(1)
    return value


def run(area_path: str | None = None, state: str | None = None) -> None:
    devops = DevOpsClient(
        org=_require("AZURE_DEVOPS_ORG"),
        project=_require("AZURE_DEVOPS_PROJECT"),
        pat=_require("AZURE_DEVOPS_PAT"),
    )
    fabric = FabricClient(
        tenant_id=_require("AZURE_TENANT_ID"),
        client_id=_require("AZURE_CLIENT_ID"),
        client_secret=_require("AZURE_CLIENT_SECRET"),
        workspace_id=_require("FABRIC_WORKSPACE_ID"),
    )
    output_dir = Path(os.getenv("OUTPUT_DIR", "./output"))
    output_dir.mkdir(parents=True, exist_ok=True)

    client = anthropic.Anthropic(api_key=_require("ANTHROPIC_API_KEY"))

    user_content = "Generate medallion architecture diagrams for all active epics."
    if area_path:
        user_content += f" Filter by area path: {area_path}."
    if state:
        user_content += f" Filter by state: {state}."

    messages: list[dict] = [{"role": "user", "content": user_content}]

    print("Starting Fabric Medallion Architecture Agent...")
    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8096,
            system=SYSTEM_PROMPT,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            for block in response.content:
                if hasattr(block, "text"):
                    print("\n" + block.text)
            break

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"  -> {block.name}({_summarise(block.input)})")
                try:
                    result = dispatch_tool(block.name, block.input, devops, fabric, output_dir)
                except Exception as exc:  # surface API errors back to Claude
                    result = f'{{"error": "{exc}"}}'
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        messages.append({"role": "user", "content": tool_results})


def _summarise(inputs: dict) -> str:
    """Short one-line representation of tool inputs for console logging."""
    parts = []
    for k, v in inputs.items():
        if isinstance(v, list):
            parts.append(f"{k}=[{len(v)} items]")
        elif isinstance(v, str) and len(v) > 40:
            parts.append(f"{k}={v[:37]}...")
        else:
            parts.append(f"{k}={v!r}")
    return ", ".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fabric Medallion Architecture Agent")
    parser.add_argument("--area-path", help="Azure DevOps area path filter")
    parser.add_argument("--state", default="Active", help="Epic state filter (default: Active)")
    args = parser.parse_args()
    run(area_path=args.area_path, state=args.state)


if __name__ == "__main__":
    main()
