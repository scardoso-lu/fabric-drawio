# fabric-drawio

AI agent that reads **Azure DevOps epics** and your live **Microsoft Purview Data Map**, then generates one editable **`.drawio` medallion architecture diagram per epic**.

Supports **single-workspace** diagrams (one Fabric workspace) and **cross-workspace** diagrams (Bronze in one workspace feeding Silver/Gold in another).

Built with Claude (`claude-opus-4-6`) using the Anthropic tool-use API and the [speckit](https://github.com/github/spec-kit) skills pattern for constraint enforcement. An OpenAI provider is also supported for teams using GPT models.

---

## How it works

```
Azure DevOps epics
       │
       ▼
  agent/main.py  ──── skills/*.SKILL.md (constraints)
       │
       ├─ devops/client.py    →  list epics, fetch details
       ├─ purview/client.py   →  list collections, query assets, infer lineage
       └─ drawio/builder.py   →  generate .drawio XML
              │
              ▼
       output/{epic-id}-{slug}.drawio
```

For each eligible epic Claude:
1. Calls `list_purview_collections` to understand available workspace scopes
2. Queries assets from one or more collections (single or cross-workspace mode)
3. Reads the epic text and maps it to real Purview-catalogued assets
4. Calls `generate_diagram` with a structured spec — the builder writes the `.drawio` file

---

## Project structure

```
fabric-drawio/
├── agent/
│   ├── main.py        # Agentic loop + CLI entry point
│   ├── llm.py         # LLM provider abstraction (Anthropic + OpenAI)
│   └── tools.py       # Tool registry + 6 tool schemas and handlers
├── devops/
│   └── client.py      # Azure DevOps REST API (WIQL, work items)
├── purview/
│   └── client.py      # Purview Data Map API (collections, assets, lineage)
├── drawio/
│   └── builder.py     # Deterministic draw.io XML builder
├── skills/            # Speckit-pattern constraint skills (loaded at runtime)
│   ├── medallion-architecture/SKILL.md
│   ├── drawio-constraints/SKILL.md
│   ├── purview-asset-governance/SKILL.md
│   ├── workspace-scoping/SKILL.md
│   └── devops-epic-mapping/SKILL.md
├── tests/             # Pytest test suite (101 tests)
├── output/            # Generated .drawio files (gitignored)
├── pyproject.toml
├── CLAUDE.md
└── .env.example
```

---

## Setup

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Azure DevOps organisation with epics and a Personal Access Token
- Microsoft Purview account with a service principal granted **Data Reader** on the collections
- Anthropic API key

### Install

```bash
git clone https://github.com/scardoso-lu/fabric-drawio
cd fabric-drawio
uv sync
```

### Configure

```bash
cp .env.example .env
```

Edit `.env`:

| Variable | Description |
|---|---|
| `AZURE_DEVOPS_ORG` | DevOps organisation name |
| `AZURE_DEVOPS_PROJECT` | DevOps project name |
| `AZURE_DEVOPS_PAT` | Personal Access Token (read work items) |
| `AZURE_TENANT_ID` | Entra ID tenant ID |
| `AZURE_CLIENT_ID` | Service principal client ID |
| `AZURE_CLIENT_SECRET` | Service principal client secret |
| `PURVIEW_ACCOUNT_NAME` | Purview account name (not the full URL) |
| `ANTHROPIC_API_KEY` | Anthropic API key (required for `--llm claude`) |
| `OPENAI_API_KEY` | OpenAI API key (required for `--llm codex`) |
| `ANTHROPIC_MODEL` | Override the Claude model (default: `claude-opus-4-6`) |
| `OPENAI_MODEL` | Override the OpenAI model (default: `gpt-4o`) |
| `OUTPUT_DIR` | Output directory (default: `./output`) |

The service principal needs **Purview Data Reader** role on the target collections.

---

## Usage

```bash
# All active epics — agent infers workspace scope from epic text
uv run python -m agent.main --state Active

# Scope all queries to a single Purview collection
uv run python -m agent.main --workspace my-collection-id

# Cross-workspace: show flows across Bronze, Silver, and Gold workspaces
uv run python -m agent.main --cross-workspace bronze-ws-id silver-ws-id gold-ws-id

# Filter by area path
uv run python -m agent.main --state Active --area-path "MyProject\Data Team"

# Use OpenAI instead of Claude (requires uv sync --extra openai)
uv run python -m agent.main --llm codex
```

Console output during a run:

```
Loaded 5 skill(s) from ./skills
Starting Fabric Medallion Architecture Agent...
  -> list_devops_epics(state='Active')
  -> list_purview_collections()
  -> get_cross_workspace_assets(collection_ids=[3 items])
  -> get_epic_details(epic_id=42)
  -> generate_diagram(epic_id=42, epic_title='Sales Analytics...', workspace_mode='cross')

Summary:
  Epic 42 — Sales Analytics Pipeline  → output/42-sales-analytics-pipeline.drawio  [cross-workspace]
  Epic 57 — HR Data Ingestion         → output/57-hr-data-ingestion.drawio          [single-workspace]
  Epic 61 — Marketing Dashboard       → SKIPPED (no data-engineering scope)
```

---

## Skills

Each skill lives in `skills/<name>/SKILL.md` with YAML frontmatter and structured sections:
**Overview · When to Use · Process · Always/Ask First/Never · Red Flags · Verification**

| Skill | Enforces |
|---|---|
| `medallion-architecture` | Bronze/Silver/Gold layer contracts — no layer skipping |
| `drawio-constraints` | Plain-text labels, `html=0`, left-to-right layout |
| `purview-asset-governance` | Only reference assets catalogued in Purview |
| `workspace-scoping` | Single vs cross-workspace mode selection and labelling rules |
| `devops-epic-mapping` | Extract sources, transforms, and outputs from epic text |

To add a constraint, create `skills/<your-skill>/SKILL.md` — no code changes needed.

---

## Development

```bash
uv sync --dev                  # install with dev dependencies
uv sync --extra openai --dev   # include OpenAI provider
uv run ruff check .            # lint
uv run ruff format .           # format
uv run pytest                  # run tests (101 tests across all modules)
```

---

## Architecture decisions

**Why Purview instead of the Fabric REST API?**
Purview's Data Map is the authoritative governance layer — it catalogs assets across all workspaces, tracks lineage, and is the single source of truth for what physically exists. The Fabric REST API only covers one workspace at a time and has no lineage information.

**Why single-workspace and cross-workspace modes?**
Real data platforms often split medallion layers across workspaces (e.g. a shared Bronze ingestion workspace feeding domain-specific Gold workspaces). Cross-workspace mode makes these flows visible and auditable.

**Why one file per epic?**
Each epic represents an independent data product. Merging epics into one diagram hides ownership boundaries and makes diagrams unmaintainable as epics evolve.

**Why deterministic XML generation?**
The draw.io builder produces the same output for the same input, making diffs readable in PRs.

**Why skills instead of a long system prompt?**
Skills are versioned alongside code, reviewable in PRs, and independently testable. Adding a constraint requires no changes to the agent loop.

**Why a provider abstraction (`LLMClient`) instead of calling Anthropic directly?**
Teams that already use OpenAI can pass `--llm codex` without touching the agent logic. The abstraction normalises message formats, tool call packaging, and tool schema conversion — `main.py` stays provider-agnostic.
