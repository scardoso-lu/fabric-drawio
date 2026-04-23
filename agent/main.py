"""
Fabric Medallion Architecture Agent

Fetches epics from Azure DevOps and data asset context from Microsoft Purview,
then generates one .drawio medallion architecture diagram per epic.

Usage:
    python -m agent.main [--state Active] [--area-path "MyProject\\Team"]
                         [--workspace <collection-id>]
                         [--cross-workspace <id1> <id2> ...]
"""

import argparse
import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from devops.client import DevOpsClient
from purview.client import PurviewClient
from .tools import TOOL_SCHEMAS, dispatch_tool

load_dotenv()

_BASE_SYSTEM_PROMPT = """You are a Principal Data Architect specialising in Microsoft Fabric
Medallion Architecture (Bronze / Silver / Gold). Your job each run:

1. Call list_devops_epics to retrieve all epics (filtered by area_path / state if provided).
2. Call list_purview_collections to understand available workspace scopes.
3. Based on the workspace mode passed by the user:
   - Single workspace: call get_workspace_assets for the specified collection.
   - Cross-workspace: call get_cross_workspace_assets with the specified collection IDs.
   - Auto (no scope given): inspect epic text to infer relevant workspaces, then call
     get_workspace_assets or get_cross_workspace_assets accordingly.
4. For each epic, call get_epic_details then reason about the appropriate medallion
   architecture strictly following all skills loaded below.
5. Call generate_diagram for each in-scope epic. Set workspace_mode to "single" or "cross".
6. Output a summary listing every epic processed: diagram filename, workspace_mode used,
   and any assumptions or skipped epics with reasons.
"""


def _load_skills(skills_dir: Path) -> str:
    blocks: list[str] = []
    for skill_file in sorted(skills_dir.rglob("SKILL.md")):
        relative = skill_file.relative_to(skills_dir)
        content = skill_file.read_text(encoding="utf-8").strip()
        blocks.append(f"### Skill: {relative.parent}\n\n{content}")
    if not blocks:
        return ""
    joined = "\n\n---\n\n".join(blocks)
    return f"\n\n## Active Skills (constraints you must respect)\n\n{joined}"


def _build_system_prompt(skills_dir: Path) -> str:
    return _BASE_SYSTEM_PROMPT + _load_skills(skills_dir)


def _require(var: str) -> str:
    value = os.getenv(var)
    if not value:
        print(f"ERROR: environment variable {var} is not set.", file=sys.stderr)
        sys.exit(1)
    return value


def run(
    area_path: str | None = None,
    state: str | None = None,
    workspace: str | None = None,
    cross_workspaces: list[str] | None = None,
) -> None:
    skills_dir = Path(__file__).parent.parent / "skills"
    system_prompt = _build_system_prompt(skills_dir)
    skill_count = sum(1 for _ in skills_dir.rglob("SKILL.md"))
    print(f"Loaded {skill_count} skill(s) from {skills_dir}")

    devops = DevOpsClient(
        org=_require("AZURE_DEVOPS_ORG"),
        project=_require("AZURE_DEVOPS_PROJECT"),
        pat=_require("AZURE_DEVOPS_PAT"),
    )
    purview = PurviewClient(
        tenant_id=_require("AZURE_TENANT_ID"),
        client_id=_require("AZURE_CLIENT_ID"),
        client_secret=_require("AZURE_CLIENT_SECRET"),
        account_name=_require("PURVIEW_ACCOUNT_NAME"),
    )
    output_dir = Path(os.getenv("OUTPUT_DIR", "./output"))
    output_dir.mkdir(parents=True, exist_ok=True)

    client = anthropic.Anthropic(api_key=_require("ANTHROPIC_API_KEY"))

    # Build the user instruction with explicit workspace scope if provided
    parts = ["Generate medallion architecture diagrams for all active epics."]
    if area_path:
        parts.append(f"Filter epics by area path: {area_path}.")
    if state:
        parts.append(f"Filter epics by state: {state}.")
    if workspace:
        parts.append(
            f"Use single-workspace mode: scope all asset queries to collection '{workspace}'."
        )
    elif cross_workspaces:
        ids = ", ".join(cross_workspaces)
        parts.append(
            f"Use cross-workspace mode: query assets across collections [{ids}] together "
            "and show cross-workspace data flows in the diagrams."
        )
    else:
        parts.append(
            "Workspace scope is not specified — infer from each epic's description "
            "which collection(s) are relevant and choose single or cross-workspace mode accordingly."
        )

    messages: list[dict] = [{"role": "user", "content": " ".join(parts)}]

    print("Starting Fabric Medallion Architecture Agent...")
    while True:
        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=8096,
            system=system_prompt,
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
                    result = dispatch_tool(block.name, block.input, devops, purview, output_dir)
                except Exception as exc:
                    result = f'{{"error": "{exc}"}}'
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })

        messages.append({"role": "user", "content": tool_results})


def _summarise(inputs: dict) -> str:
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

    scope = parser.add_mutually_exclusive_group()
    scope.add_argument(
        "--workspace",
        metavar="COLLECTION_ID",
        help="Scope all asset queries to a single Purview collection.",
    )
    scope.add_argument(
        "--cross-workspace",
        nargs="+",
        metavar="COLLECTION_ID",
        help="Query assets across multiple Purview collections (cross-workspace mode).",
    )

    args = parser.parse_args()
    run(
        area_path=args.area_path,
        state=args.state,
        workspace=args.workspace,
        cross_workspaces=args.cross_workspace,
    )


if __name__ == "__main__":
    main()
