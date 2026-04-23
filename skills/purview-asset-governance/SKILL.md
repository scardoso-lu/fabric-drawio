---
name: Purview Asset Governance
description: Ensures the agent only references data assets that verifiably exist in Microsoft Purview's Data Map. Use before generating any diagram node that represents a catalogued asset (Lakehouse, Pipeline, Notebook, Warehouse, Table).
---

## Overview

Diagrams that reference invented assets mislead engineers and produce architectures that cannot be implemented without provisioning work that was never budgeted. Every node in a generated diagram that represents a Fabric item must be grounded in an asset returned by `get_workspace_assets` or `get_cross_workspace_assets`, or explicitly described as new in the epic text.

## When to Use

- After calling `get_workspace_assets` or `get_cross_workspace_assets` and before calling `generate_diagram`
- When an epic description mentions a Lakehouse, Pipeline, Notebook, or Table by name
- When reviewing a proposed architecture spec for asset validity

## Asset Grounding Rules

### Existing assets (from Purview)
- Use the **exact `name`** returned by the Purview API — do not abbreviate, rename, or paraphrase
- If an asset fits the epic's layer and type, prefer reusing it over proposing a new one
- Tables within a Lakehouse are individual nodes only when the epic specifically references them; otherwise represent the Lakehouse as the atomic unit

### New assets (not in Purview)
- A new asset is permitted only when the epic's requirements cannot be satisfied by any existing catalogued asset
- New asset names must follow the naming convention inferred from existing catalogued names
  (e.g. if existing names are `bronze_sales_lh`, `bronze_hr_lh`, a new one should follow `bronze_<domain>_lh`)
- Mark new assets as "(new)" in your planning notes but **not** in the diagram label

### Asset-type-to-zone mapping

| Purview Entity Type | Diagram Node Type | Typical Zone |
|---|---|---|
| `microsoft_fabric_lakehouse` | `lakehouse` | Bronze, Silver, or Gold |
| `microsoft_fabric_pipeline` | `pipeline` | Bronze (ingestion) |
| `microsoft_fabric_notebook` | `notebook` | Silver or Gold (transformation) |
| `microsoft_fabric_warehouse` | `warehouse` | Gold or Serving |
| `microsoft_fabric_table` | Use parent Lakehouse node | — |

### Tables
- Do not create a separate node for every table — one `lakehouse` node represents the whole Lakehouse item
- Exception: when an epic calls out a specific table as the subject of a lineage hop, a table node is acceptable with the format `<lakehouse_name>.<table_name>`

## Process

1. Call `get_workspace_assets` or `get_cross_workspace_assets` and record the full inventory
2. For each proposed diagram node that is a Fabric item, check if it exists in the inventory
3. If it exists: use exact name, assign to the correct layer and type
4. If it does not exist: verify the epic requires it; follow naming convention; note it as new in the run summary
5. After generating the diagram, cross-reference every Fabric node against the Purview inventory or epic text

## Boundaries

**Always:**
- Use the exact `name` from the Purview API for existing assets
- Prefer existing catalogued assets over proposing new ones
- Respect the asset-type-to-zone mapping table above

**Ask First:**
- Proposing more than two new assets for a single epic
- Using individual table nodes instead of Lakehouse nodes
- Placing a Notebook in Bronze or a Pipeline in Silver/Gold

**Never:**
- Invent an asset name not grounded in Purview or epic text
- Rename or abbreviate a catalogued asset name in a diagram label
- Assign a Fabric item to the wrong zone
- Show `microsoft_fabric_table` qualified names as primary nodes unless epic-justified

## Red Flags

- A diagram node name does not match any Purview inventory entry and the epic never mentions it
- A Pipeline node appears in Silver or Gold (pipelines belong in Bronze ingestion)
- A Notebook node appears in Bronze (notebooks belong in Silver/Gold transformation)
- The epic mentions a domain but no matching Lakehouse exists and no new one is proposed
- Two nodes represent the same physical Purview asset

## Verification

- Every `lakehouse`, `pipeline`, `notebook`, and `warehouse` node name either matches a Purview inventory entry exactly or is explicitly justified by epic text
- No two nodes represent the same physical Fabric item
- Asset types match their assigned zones per the mapping table
- New assets follow the naming convention of the existing catalogued workspace
