# fabric-drawio

AI agent that generates Microsoft Fabric Medallion Architecture `.drawio` diagrams from Azure DevOps epics.

## Project structure

```
agent/          Orchestration layer — agentic loop (main.py) and Claude tool schemas (tools.py)
devops/         Azure DevOps REST client — WIQL queries, work item details
fabric/         Microsoft Fabric REST client — Entra ID auth, lakehouses, pipelines, notebooks
drawio/         draw.io XML builder — deterministic 5-zone layout generator
skills/         Speckit-pattern constraint files loaded into the system prompt at runtime
output/         Generated .drawio files (gitignored)
```

## Commands

```bash
uv sync                                   # install all dependencies
uv sync --dev                             # install with dev dependencies
uv run python -m agent.main --state Active  # run the agent
uv run ruff check .                       # lint
uv run ruff format .                      # format
uv run pytest                             # run tests
```

## Architecture conventions

### Component boundaries
- `devops/` and `fabric/` are pure API clients — no Claude logic, no draw.io logic
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

### Fabric resource governance (enforced by `skills/fabric-resource-governance/SKILL.md`)
- Only diagram Fabric items (Lakehouses, Pipelines, Notebooks) that exist in `get_fabric_context`
- Use the exact `displayName` from the API — no renaming or abbreviation

### Skills
- Every skill lives in `skills/<name>/SKILL.md` with YAML frontmatter (`name`, `description`)
- `agent/main.py` reads all `SKILL.md` files at startup via `_load_skills()` and appends them to the system prompt
- To add a constraint: create `skills/<your-skill>/SKILL.md` — no code changes needed

## Adding a new Fabric item type

1. Add a `get_<type>s()` method to `fabric/client.py` calling the appropriate Fabric API endpoint
2. Include the new type in `get_workspace_context()` return dict
3. Add a `"type"` entry to the node style map in `drawio/builder.py` (`_NODE_STYLES`)
4. Update the `fabric-resource-governance` skill's resource-type mapping table
5. Add the new type to the `generate_diagram` tool schema enum in `agent/tools.py`

## Adding a new Azure DevOps field

Add the field key to `get_epic_details()` in `devops/client.py` and update the `devops-epic-mapping` skill to document how to interpret the new field.

## Environment variables

See `.env.example` for the full list. Required at runtime:
`AZURE_DEVOPS_ORG`, `AZURE_DEVOPS_PROJECT`, `AZURE_DEVOPS_PAT`,
`AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`,
`FABRIC_WORKSPACE_ID`, `ANTHROPIC_API_KEY`
