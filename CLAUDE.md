# fabric-drawio

AI agent that generates Microsoft Fabric Medallion Architecture `.drawio` diagrams and companion Markdown tech specs from Azure DevOps epics.

## Project structure

```
agent/          Orchestration layer — agentic loop (main.py), LLM abstraction (llm.py),
                tool registry (tools.py), demo stubs (demo.py)
devops/         Azure DevOps REST client — WIQL queries, work item details
purview/        Microsoft Purview Data Map client — collections, asset queries, lineage
drawio/         draw.io XML builder — deterministic 5-zone layout generator
techspec/       Markdown tech-spec builder — deterministic companion to drawio/builder.py
skills/         Speckit-pattern constraint files loaded into the system prompt at runtime
tests/          Pytest test suite — unit tests for all modules (no external calls)
output/         Generated .drawio and .md files (gitignored)
examples/       Fixture data for demo mode (devops_epics.json, purview_collections.json,
                purview_assets.json)
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
uv run python -m agent.main --demo                # demo mode — no credentials needed
run.bat                                           # interactive launcher (Windows)
uv run ruff check .                               # lint
uv run ruff format .                              # format
uv run pytest                                     # run tests
```

## Architecture conventions

### Component boundaries
- `devops/` and `purview/` are pure API clients — no Claude logic, no draw.io logic
- `drawio/builder.py` is deterministic — given the same spec dict it always produces the same XML
- `techspec/builder.py` is deterministic — given the same spec dict it always produces the same Markdown
- `agent/llm.py` owns all real LLM provider logic — `main.py` only talks to the `LLMClient` ABC
- `agent/demo.py` owns all demo stubs — `DevOpsClientStub`, `PurviewClientStub`, `ScriptedClient`, and the fixture tech-spec data
- `agent/` is the only layer that imports from all components; never cross-import between components

### LLM provider abstraction (`agent/llm.py`)
- `LLMClient` ABC defines `send`, `pack_assistant`, `pack_tool_results`, and `user_message`
- `AnthropicClient` wraps the Anthropic Messages API; default model is `claude-opus-4-6`
- `OpenAIClient` wraps OpenAI Chat Completions; converts Anthropic `input_schema` tool format to OpenAI `parameters` format automatically
- `make_client(provider)` is the factory — resolves the class from `_PROVIDERS` registry and reads the model from each class's `_ENV_VAR` / `_DEFAULT_MODEL` attributes
- Adding a new provider requires only a new `LLMClient` subclass and one entry in `_PROVIDERS` — no branching in `make_client`
- Both real providers use deferred imports (`import anthropic` / `import openai` inside `__init__`) so the missing package only errors at instantiation, not at import time
- OpenAI is an optional dependency: `uv sync --extra openai`

### Demo mode (`agent/demo.py`)
- `DevOpsClientStub` and `PurviewClientStub` serve fixture data from `examples/` — no network calls
- `ScriptedClient` implements `LLMClient` and drives the full agentic loop (8 tool calls across 3 epics) without any API key
- `_SCRIPTED_TECH_SPECS` maps epic IDs to pre-built `(pseudoalgorithm, tradeoffs)` tuples
- All demo stubs live in one file; `agent/llm.py` contains only real LLM adapters (SRP)
- Activated by passing `--demo` to `agent.main`

### Tool registry (`agent/tools.py`)
- `Tool` is a frozen dataclass pairing a schema dict with a handler callable
- `ToolRegistry.dispatch(name, inputs)` routes calls; returns `{"error": "..."}` JSON for unknown tools
- `build_registry(devops, purview, output_dir)` accepts `DevOpsProvider` and `PurviewProvider` Protocol types — not concrete classes (DIP)
- Adding a tool requires only a schema constant, a handler closure, and a `register()` call (OCP)
- Six tools: `list_devops_epics`, `get_epic_details`, `list_purview_collections`, `get_workspace_assets`, `get_cross_workspace_assets`, `generate_diagram`
- `generate_diagram` writes both a `.drawio` file and a companion `.md` tech spec to `output/`
- Required fields in `generate_diagram`: `epic_id`, `epic_title`, `workspace_mode`, `data_sources`, `bronze_nodes`, `silver_nodes`, `gold_nodes`, `serving_nodes`, `edges`, `pseudoalgorithm`, `tradeoffs`, `unclear_steps`

### Tech spec builder (`techspec/builder.py`)
- `build_tech_spec_md(spec)` takes the same spec dict as `build_drawio` and produces Markdown
- Sections in order: **Open Questions** (first — ambiguous/missing items from the epic), Architecture Overview (data sources + layer/assets table), Implementation Pseudoalgorithm (numbered steps), Tradeoffs (engineer-facing decisions with no prescribed answer)
- `pseudoalgorithm`, `tradeoffs`, and `unclear_steps` fields are required in the `generate_diagram` tool schema — the LLM populates them; `ScriptedClient` uses `_SCRIPTED_TECH_SPECS`
- Each `unclear_step` has: `step` (label), `epic_reference` (verbatim quote), `assumption` (what was assumed / what engineer must define), `lands_from` (upstream diagram node name)

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
- `test_techspec.py` tests `techspec/builder.py` in isolation — content contract tests (heading format, open questions section, numbered steps, tradeoff headings); content testing does not belong in `test_tools.py`
- `test_tools.py` tests the `generate_diagram` handler's I/O contract only (files exist, correct extensions, matching stems)
- All `generate_diagram` test inputs must include `unclear_steps: []`

## Adding a new Purview asset type

1. Add the new `microsoft_fabric_*` entity type to `_FABRIC_ENTITY_TYPES` in `purview/client.py`
2. Add a mapping entry in `_classify()` in `purview/client.py`
3. Add a `"type"` entry to `_NODE_STYLES` in `drawio/builder.py`
4. Update the asset-type-to-zone mapping table in `skills/purview-asset-governance/SKILL.md`
5. Add the new type to the `generate_diagram` tool schema enum in `agent/tools.py`

## Adding a new LLM provider

1. Add a concrete subclass of `LLMClient` in `agent/llm.py` implementing `send`, `pack_assistant`, `pack_tool_results`; set `_DEFAULT_MODEL` and `_ENV_VAR` class attributes
2. Add one entry to `_PROVIDERS` in `agent/llm.py`
3. Add the provider name to the `--llm` choices in `agent/main.py`
4. If the provider has an optional dependency, add it under `[project.optional-dependencies]` in `pyproject.toml`

## Adding a new demo epic

1. Add the epic dict to `examples/devops_epics.json`
2. Add a collection entry to `examples/purview_collections.json`
3. Add asset data (including `data_sources`) to `examples/purview_assets.json`
4. Add a `(pseudoalgorithm, tradeoffs)` tuple to `_SCRIPTED_TECH_SPECS` in `agent/demo.py`

## Adding a new Azure DevOps field

Add the field key to `get_epic_details()` in `devops/client.py` and update the `devops-epic-mapping` skill to document how to interpret the new field.

## Environment variables

See `.env.example` for the full list. Required at runtime (not needed for `--demo`):
`AZURE_DEVOPS_ORG`, `AZURE_DEVOPS_PROJECT`, `AZURE_DEVOPS_PAT`,
`AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`,
`PURVIEW_ACCOUNT_NAME`, `ANTHROPIC_API_KEY`

Optional: `OPENAI_API_KEY`, `ANTHROPIC_MODEL`, `OPENAI_MODEL`, `OUTPUT_DIR`
