---
name: Azure DevOps Epic Mapping
description: Governs how Azure DevOps epics are interpreted and translated into medallion architecture diagrams. Use when reading epic details and deciding which data sources, transformations, and serving outputs belong in the diagram.
---

## Overview

An Azure DevOps epic describes a business outcome, not a technical architecture. The agent must extract architectural signals from the epic's title, description, acceptance criteria, and tags — and resist the temptation to over-engineer or under-specify. One epic produces exactly one diagram. Epics with no data-engineering scope are skipped with a written explanation.

## When to Use

- After calling `get_epic_details` and before calling `generate_diagram`
- When interpreting ambiguous or sparse epic descriptions
- When deciding whether an epic warrants a diagram at all

## Extraction Rules

### Data Sources (Bronze inputs)
Signals in epic text that indicate a data source:
- Mentions of systems by name: "SQL Server", "Salesforce", "SAP", "SharePoint", "REST API", "S3", "SFTP"
- Verbs implying ingestion: "ingest", "pull", "import", "receive", "sync from", "load from"
- File format mentions: "CSV", "JSON", "Parquet", "Excel" — imply a file drop source
- If no source is mentioned, infer "Source System" as a generic placeholder and note the ambiguity

### Transformations (Silver / Gold)
Signals that indicate transformation work:
- Silver: "cleanse", "validate", "deduplicate", "standardise", "normalise", "quality check"
- Gold: "aggregate", "KPI", "metric", "report", "dashboard", "summary", "calculate", "join", "dimension"
- If both silver and gold signals exist, diagram both layers fully
- If only gold signals exist, still include a Silver layer (it is architecturally mandatory)

### Serving outputs
Signals that indicate a serving layer:
- "Power BI", "report", "dashboard", "dataset", "semantic model" → `semantic_model` + `report` nodes
- "API", "export", "feed", "publish to" → `pipeline` node in Serving zone labelled "Export Pipeline"
- "Direct Lake" explicitly mentioned → ensure the semantic model node is present

### Epic Scope Filter
An epic warrants a diagram if it contains at least one of:
- A named data source or ingestion verb
- A transformation or calculation requirement
- A data output or reporting requirement

Skip the epic (with explanation) if it is purely about:
- UI/UX design with no data backend
- Infrastructure provisioning unrelated to data
- Process or governance documentation only

## Process

1. Read `title`, `description`, `acceptance_criteria`, and `tags` from `get_epic_details`
2. Extract data source signals → map to `data_sources` nodes with `type: source`
3. Extract transformation signals → decide Silver nodes (notebooks), Gold nodes (notebooks)
4. Extract serving signals → map to `serving_nodes`
5. Identify which existing Fabric resources (from `get_fabric_context`) map to each layer
6. Build the `edges` list to connect every node in the flow
7. Call `generate_diagram` with the complete spec

## One-Epic One-Diagram Rule

- Generate exactly one `.drawio` file per epic; never merge two epics into one diagram
- If an epic is very large (many sources, many outputs), still produce one diagram — use vertical stacking within zones
- File name: `{epic_id}-{slugified_title}.drawio`

## Ambiguity Handling

| Situation | Action |
|---|---|
| Epic has no data source | Add a generic "Source System" node; note ambiguity in run summary |
| Epic mentions a source but no ingestion tool | Default to "Dataflows Gen2" in Bronze; note assumption |
| Epic has no serving output | Add a placeholder "TBD Report" node; note ambiguity |
| Epic is ambiguous about Silver vs Gold | Default to including both layers |
| Epic explicitly says "no reporting needed" | Omit Serving layer; note deviation |

## Boundaries

**Always:**
- Produce exactly one diagram per in-scope epic
- Include all five zones even if a zone has only one node
- Record assumptions and ambiguities in the post-run summary, not in diagram labels

**Ask First:**
- Skipping an epic that has partial data-engineering signals
- Combining two closely related epics into one diagram

**Never:**
- Invent a business requirement not present in the epic text
- Skip the Silver layer even if the epic only mentions Gold-level outputs
- Use the epic ID or work item URL as a diagram node label
- Include epic metadata (state, area path, tags) as diagram nodes

## Red Flags

- A diagram has no data source nodes (every architecture has an origin)
- A diagram has no serving nodes (every architecture has a consumer)
- The diagram nodes do not correspond to any language in the epic text
- Two epics produced identical diagrams (likely a mapping error)
- An epic's acceptance criteria mention a specific tool that is absent from the diagram

## Verification

- Every `data_sources` node name maps to a system or file format mentioned in the epic
- Every `serving_nodes` node maps to an output or consumer mentioned in the epic
- The run summary lists any assumptions made during extraction
- Skipped epics have a written justification in the run summary
