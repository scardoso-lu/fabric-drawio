# fabric-drawio

AI agent that reads **Azure DevOps epics** and your live **Microsoft Fabric workspace**, then generates one editable **`.drawio` medallion architecture diagram per epic**.

Built with Claude (`claude-sonnet-4-6`) using the Anthropic tool-use API and the [speckit](https://github.com/github/spec-kit) skills pattern for constraint enforcement.

---

## How it works

```
Azure DevOps epics
       │
       ▼
  agent/main.py  ──── skills/*.SKILL.md (constraints)
       │
       ├─ devops/client.py   →  list epics, fetch details
       ├─ fabric/client.py   →  snapshot workspace (lakehouses, pipelines, notebooks)
       └─ drawio/builder.py  →  generate .drawio XML
              │
              ▼
       output/{epic-id}-{slug}.drawio
```

For each eligible epic Claude:
1. Extracts data sources, transformations, and serving outputs from the epic text
2. Maps them to real Fabric resources in your workspace
3. Calls `generate_diagram` with a structured spec
4. The diagram builder writes a 5-zone left-to-right `.drawio` file

---

## Project structure

```
fabric-drawio/
├── agent/
│   ├── main.py        # Agentic loop + CLI entry point
│   └── tools.py       # Claude tool schemas + dispatcher
├── devops/
│   └── client.py      # Azure DevOps REST API (WIQL, work items)
├── fabric/
│   └── client.py      # Fabric REST API (auth, lakehouses, pipelines, notebooks)
├── drawio/
│   └── builder.py     # Deterministic draw.io XML builder
├── skills/            # Speckit-pattern constraint skills (loaded at runtime)
│   ├── medallion-architecture/SKILL.md
│   ├── drawio-constraints/SKILL.md
│   ├── fabric-resource-governance/SKILL.md
│   └── devops-epic-mapping/SKILL.md
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
- Microsoft Fabric workspace with a service principal (Entra ID app registration)
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

Edit `.env` with your credentials:

| Variable | Description |
|---|---|
| `AZURE_DEVOPS_ORG` | DevOps organisation name (e.g. `myorg`) |
| `AZURE_DEVOPS_PROJECT` | DevOps project name |
| `AZURE_DEVOPS_PAT` | Personal Access Token (read work items scope) |
| `AZURE_TENANT_ID` | Entra ID tenant ID |
| `AZURE_CLIENT_ID` | Service principal client ID |
| `AZURE_CLIENT_SECRET` | Service principal client secret |
| `FABRIC_WORKSPACE_ID` | Target Fabric workspace GUID |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `OUTPUT_DIR` | Output directory (default: `./output`) |

The service principal needs **Viewer** role on the Fabric workspace to read item names.

---

## Usage

```bash
# All active epics
uv run python -m agent.main --state Active

# Filter by area path
uv run python -m agent.main --state Active --area-path "MyProject\Data Team"

# All epics regardless of state
uv run python -m agent.main
```

On startup the agent prints the number of skills loaded, then streams tool calls to the console:

```
Loaded 4 skill(s) from ./skills
Starting Fabric Medallion Architecture Agent...
  -> list_devops_epics(state='Active')
  -> get_fabric_context()
  -> get_epic_details(epic_id=42)
  -> generate_diagram(epic_id=42, epic_title='Sales Analytics Pipeline', ...)
...

Summary:
  Epic 42 — Sales Analytics Pipeline → output/42-sales-analytics-pipeline.drawio
  Epic 57 — HR Data Ingestion        → output/57-hr-data-ingestion.drawio
  Epic 61 — Marketing Dashboard      → SKIPPED (no data-engineering scope)
```

Open any `.drawio` file at [diagrams.net](https://app.diagrams.net) or in draw.io Desktop.

---

## Skills

The `skills/` folder contains constraint files that the agent must respect on every run. Each skill follows the [speckit](https://github.com/github/spec-kit) convention:

```
skills/<name>/SKILL.md
```

With YAML frontmatter (`name`, `description`) and structured sections:
**Overview · When to Use · Process · Boundaries (Always/Ask First/Never) · Red Flags · Verification**

| Skill | Enforces |
|---|---|
| `medallion-architecture` | Bronze/Silver/Gold layer contracts — no layer skipping |
| `drawio-constraints` | Plain-text labels, html=0, left-to-right layout, unique cell IDs |
| `fabric-resource-governance` | Only reference Fabric items that exist in the workspace |
| `devops-epic-mapping` | How to extract sources, transforms, and outputs from epic text |

To add a constraint, create `skills/<your-skill>/SKILL.md` — no code changes needed.

---

## Development

```bash
# Install with dev dependencies
uv sync --dev

# Lint
uv run ruff check .

# Format
uv run ruff format .

# Run tests
uv run pytest
```

---

## Architecture decisions

**Why one file per epic?** Each epic represents an independent data product. Merging epics into one diagram hides ownership boundaries and makes the diagram unmaintainable as epics evolve.

**Why deterministic XML generation?** The draw.io builder produces the same output for the same input, making diffs readable in PRs and avoiding non-deterministic layout shifts between runs.

**Why skills instead of a long system prompt?** Skills are versioned alongside the code, reviewable in PRs, and independently testable. Adding or tightening a constraint requires no changes to the agent loop.
