# fabric-drawio

AI agent that generates Microsoft Fabric Medallion Architecture `.drawio` diagrams from Azure DevOps epics.

## Project structure

```
agent/          Orchestration layer — agentic loop (main.py), LLM abstraction (llm.py), tool registry (tools.py)
devops/         Azure DevOps REST client — WIQL queries, work item details
purview/        Microsoft Purview Data Map client — collections, asset queries, lineage
drawio/         draw.io XML builder — deterministic 5-zone layout generator
skills/         Speckit-pattern constraint files loaded into the system prompt at runtime
tests/          Pytest test suite — unit tests for all modules (no external calls)
output/         Generated .drawio files (gitignored)
```

## Commands

```bash
uv sync                                           # install all dependencies
uv sync --dev                                     # install with dev dependencies
uv sync --extra openai --dev                      # include OpenAI provider
uv run python -m agent.main --state Active        # run the agent (auto workspace scope)
uv run python -m agent.main --workspace <id>      # single-workspace mode
uv run python -m agent.main --cross-workspace <id1> <id2>  # cross-workspace mode
uv run python -m agent.main --llm codex           # use OpenAI instead of Claude
uv run ruff check .                               # lint
uv run ruff format .                              # format
uv run pytest                                     # run tests
```

## Architecture conventions

### Component boundaries
- `devops/` and `purview/` are pure API clients — no Claude logic, no draw.io logic
- `drawio/builder.py` is deterministic — given the same spec dict it always produces the same XML
- `agent/llm.py` owns all LLM provider logic — `main.py` only talks to the `LLMClient` ABC
- `agent/` is the only layer that imports from all three components; never cross-import between components

### LLM provider abstraction (`agent/llm.py`)
- `LLMClient` ABC defines `send`, `pack_assistant`, `pack_tool_results`, and `user_message`
- `AnthropicClient` wraps the Anthropic Messages API; default model is `claude-opus-4-6`
- `OpenAIClient` wraps OpenAI Chat Completions; converts Anthropic `input_schema` tool format to OpenAI `parameters` format automatically
- `make_client(provider)` is the factory — model overrides via `ANTHROPIC_MODEL` / `OPENAI_MODEL` env vars
- Both providers use deferred imports (`import anthropic` / `import openai` inside `__init__`) so the missing package only errors at instantiation, not at import time
- OpenAI is an optional dependency: `uv sync --extra openai`

### Tool registry (`agent/tools.py`)
- `Tool` is a frozen dataclass pairing a schema dict with a handler callable
- `ToolRegistry.dispatch(name, inputs)` routes calls; returns `{"error": "..."}` JSON for unknown tools
- `build_registry(devops, purview, output_dir)` wires all six tools — adding a tool requires only a schema constant, a handler closure, and a `register()` call (OCP)
- Six tools: `list_devops_epics`, `get_epic_details`, `list_purview_collections`, `get_workspace_assets`, `get_cross_workspace_assets`, `generate_diagram`

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

### Tests
- All tests live in `tests/` and use only `unittest.mock` — no network calls, no real credentials
- `httpx` calls are patched via `patch("httpx.get")` / `patch("httpx.post")`
- Anthropic/OpenAI SDK imports are patched via `patch.dict("sys.modules", {...})` — deferred imports in the client `__init__` methods make this pattern necessary
- `AnthropicClient` content blocks must be mocked with `spec=["type", "text"]` or `spec=["type", "id", "name", "input"]` so `hasattr` checks on the mock return the right result

## Adding a new Purview asset type

1. Add the new `microsoft_fabric_*` entity type to `_FABRIC_ENTITY_TYPES` in `purview/client.py`
2. Add a mapping entry in `_classify()` in `purview/client.py`
3. Add a `"type"` entry to `_NODE_STYLES` in `drawio/builder.py`
4. Update the asset-type-to-zone mapping table in `skills/purview-asset-governance/SKILL.md`
5. Add the new type to the `generate_diagram` tool schema enum in `agent/tools.py`

## Adding a new LLM provider

1. Add a concrete subclass of `LLMClient` in `agent/llm.py` implementing `send`, `pack_assistant`, `pack_tool_results`
2. Add a branch in `make_client()` for the new provider name
3. Add the provider name to the `--llm` choices in `agent/main.py`
4. If the provider has an optional dependency, add it under `[project.optional-dependencies]` in `pyproject.toml`

## Adding a new Azure DevOps field

Add the field key to `get_epic_details()` in `devops/client.py` and update the `devops-epic-mapping` skill to document how to interpret the new field.

## Environment variables

See `.env.example` for the full list. Required at runtime:
`AZURE_DEVOPS_ORG`, `AZURE_DEVOPS_PROJECT`, `AZURE_DEVOPS_PAT`,
`AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`,
`PURVIEW_ACCOUNT_NAME`, `ANTHROPIC_API_KEY`

Optional: `OPENAI_API_KEY`, `ANTHROPIC_MODEL`, `OPENAI_MODEL`, `OUTPUT_DIR`
