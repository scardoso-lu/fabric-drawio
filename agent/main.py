"""
Fabric Medallion Architecture Agent

Fetches epics from Azure DevOps and data asset context from Microsoft Purview,
then generates one .drawio medallion architecture diagram per epic.

Usage:
    python -m agent.main [--state Active] [--area-path "MyProject\\Team"]
                         [--workspace <collection-id>]
                         [--cross-workspace <id1> <id2> ...]
                         [--llm claude|codex]
                         [--demo]
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from devops.client import DevOpsClient
from purview.client import PurviewClient
from .demo import DevOpsClientStub, PurviewClientStub, ScriptedClient
from .llm import LLMClient, AnthropicClient, make_client
from .tools import build_registry

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
   Also populate:
   - pseudoalgorithm: ordered implementation steps (Bronze ingestion → Silver cleansing →
     Gold transformations → Serving publication). Be concrete: name the assets, data formats,
     and key transformation logic inferred from the epic description.
   - tradeoffs: a list of architecture and cost decisions the engineer must make themselves.
     Each tradeoff must have a topic and a description that explains the options and their
     implications (e.g. compute cost, governance, complexity, latency). Do not recommend a
     single answer — present the options and let the engineer decide.
   - unclear_steps: every step or detail that is ambiguous, missing, or underdefined in the
     epic text or Purview catalogue. For each item provide:
       • step: a short label for the gap (e.g. "Source schema unknown")
       • epic_reference: the verbatim phrase from the epic that is ambiguous or absent
       • assumption: what assumption was made to draw the diagram, or what the engineer
         must define before building (never skip this — it surfaces the decision)
       • lands_from: the name of the diagram node that flows into this unclear step
     An empty list is only valid if the epic and Purview data leave absolutely nothing
     ambiguous — treat any implied detail not explicitly stated as an open question.
6. Output a summary listing every epic processed: diagram filename, tech spec filename,
   workspace_mode used, and any assumptions or skipped epics with reasons.
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
    llm_client: LLMClient | None = None,
    devops: DevOpsClient = None,
    purview: PurviewClient = None,
) -> None:
    if llm_client is None:
        llm_client = AnthropicClient()
    if devops is None or purview is None:
        raise ValueError("devops and purview clients must be provided — call main() or supply them explicitly.")

    skills_dir = Path(__file__).parent.parent / "skills"
    system_prompt = _build_system_prompt(skills_dir)
    skill_count = sum(1 for _ in skills_dir.rglob("SKILL.md"))
    print(f"Loaded {skill_count} skill(s) from {skills_dir}")

    output_dir = Path(os.getenv("OUTPUT_DIR", "./output"))
    output_dir.mkdir(parents=True, exist_ok=True)

    registry = build_registry(devops, purview, output_dir)

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

    messages: list[dict] = [llm_client.user_message(" ".join(parts))]

    print(f"Starting Fabric Medallion Architecture Agent ({llm_client.__class__.__name__})...")
    while True:
        response = llm_client.send(system_prompt, messages, registry.schemas)
        messages.extend(llm_client.pack_assistant(response))

        if not response.tool_calls:
            if response.text:
                print("\n" + response.text)
            break

        results: list[str] = []
        for tc in response.tool_calls:
            print(f"  -> {tc.name}({_summarise(tc.input)})")
            try:
                result = registry.dispatch(tc.name, tc.input)
            except Exception as exc:
                result = f'{{"error": "{exc}"}}'
            results.append(result)

        messages.extend(llm_client.pack_tool_results(response.tool_calls, results))


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
    parser.add_argument(
        "--llm",
        choices=["claude", "codex"],
        default="claude",
        help="LLM provider: 'claude' (Anthropic, default) or 'codex' (OpenAI). "
             "Override model with ANTHROPIC_MODEL / OPENAI_MODEL env vars.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run with example fixture data from examples/ instead of calling Azure DevOps and Purview APIs. "
             "Only ANTHROPIC_API_KEY (or OPENAI_API_KEY) is required.",
    )

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

    if args.demo:
        devops = DevOpsClientStub()
        purview = PurviewClientStub()
        print("Demo mode: using example fixture data from examples/")
    else:
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

    llm_client = ScriptedClient() if args.demo else make_client(args.llm)

    run(
        area_path=args.area_path,
        state=args.state,
        workspace=args.workspace,
        cross_workspaces=args.cross_workspace,
        llm_client=llm_client,
        devops=devops,
        purview=purview,
    )


if __name__ == "__main__":
    main()
