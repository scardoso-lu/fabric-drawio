# fabric-drawio

AI agent that generates Microsoft Fabric Medallion Architecture `.drawio` diagrams from Azure DevOps epics.

## Project structure

```
agent/          Orchestration layer — agentic loop (main.py) and Claude tool schemas (tools.py)
devops/         Azure DevOps REST client — WIQL queries, work item details
purview/        Microsoft Purview Data Map client — collections, asset queries, lineage
drawio/         draw.io XML builder — deterministic 5-zone layout generator
skills/         Speckit-pattern constraint files loaded into the system prompt at runtime
output/         Generated .drawio files (gitignored)
```

## Commands

```bash
uv sync                                      # install all dependencies
uv sync --dev                                # install with dev dependencies
uv run python -m agent.main --state Active   # run the agent (auto workspace scope)
uv run python -m agent.main --workspace <id> # single-workspace mode
uv run python -m agent.main --cross-workspace <id1> <id2>  # cross-workspace mode
uv run ruff check .                          # lint
uv run ruff format .                         # format
uv run pytest                                # run tests
```

## Architecture conventions

### Component boundaries
- `devops/` and `purview/` are pure API clients — no Claude logic, no draw.io logic
- `drawio/builder.py` is deterministic — given the same spec dict it always produces the same XML
- `agent/` is the only layer that imports from all three components; never cross-import between components

### draw.io rules (enforced by `skills/drawio-constraints/SKILL.md`)
- All `mxCell` `value` attributes must be plain text — **no HTML tags, ever**
- Style strings must always include `html=0` — never `html=1`
- Zone background rectangles are written before node cells (lower z-order)
- Cell IDs 0 and 1 are reserved; user content starts at ID 2
- Page dimensions: A3 landscape (1654 × 1169) minimum

### Medallion architecture rules (enforced by `skills/medallion-architecture/SKILL.md`)
- Data flows strictly Bronze → Silver → Gold → Serving — no layer skipping
- Bronze: raw ingestion only (Dataflows Gen2, pipelines); no transformations
- Silver: cleansing and typing (PySpark Notebooks); reads from Bronze only
- Gold: business aggregations and KPIs (PySpark Notebooks); reads from Silver only
- Serving: Direct Lake Semantic Models, reports; no transformation logic

### Purview asset governance (enforced by `skills/purview-asset-governance/SKILL.md`)
- Only diagram assets that exist in the Purview Data Map or are explicitly justified by the epic
- Use the exact `name` from the Purview API — no renaming or abbreviation

### Workspace scoping (enforced by `skills/workspace-scoping/SKILL.md`)
- Single-workspace mode: `get_workspace_assets` with one collection ID
- Cross-workspace mode: `get_cross_workspace_assets` with multiple collection IDs
- Every `generate_diagram` call must include `workspace_mode` ("single" or "cross")
- In cross-workspace diagrams every node must have a `workspace` field (collection friendly name)

### Skills
- Every skill lives in `skills/<name>/SKILL.md` with YAML frontmatter (`name`, `description`)
- `agent/main.py` reads all `SKILL.md` files at startup via `_load_skills()` and appends them to the system prompt
- To add a constraint: create `skills/<your-skill>/SKILL.md` — no code changes needed

## Adding a new Purview asset type

1. Add the new `microsoft_fabric_*` entity type to `_FABRIC_ENTITY_TYPES` in `purview/client.py`
2. Add a mapping entry in `_classify()` in `purview/client.py`
3. Add a `"type"` entry to `_NODE_STYLES` in `drawio/builder.py`
4. Update the asset-type-to-zone mapping table in `skills/purview-asset-governance/SKILL.md`
5. Add the new type to the `generate_diagram` tool schema enum in `agent/tools.py`

## Adding a new Azure DevOps field

Add the field key to `get_epic_details()` in `devops/client.py` and update the `devops-epic-mapping` skill to document how to interpret the new field.

## Environment variables

See `.env.example` for the full list. Required at runtime:
`AZURE_DEVOPS_ORG`, `AZURE_DEVOPS_PROJECT`, `AZURE_DEVOPS_PAT`,
`AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`,
`PURVIEW_ACCOUNT_NAME`, `ANTHROPIC_API_KEY`
