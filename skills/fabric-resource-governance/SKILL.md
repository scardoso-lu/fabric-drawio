---
name: Fabric Resource Governance
description: Ensures the agent only references Microsoft Fabric resources that verifiably exist in the target workspace. Use before generating any diagram node that represents a Fabric item (Lakehouse, Pipeline, Notebook, Semantic Model).
---

## Overview

Diagrams that reference invented Fabric resources mislead engineers, create false dependencies in sprint planning, and produce architectures that cannot be implemented without provisioning work that was never budgeted. Every node in a generated diagram that represents a Fabric item must be grounded either in a resource returned by `get_fabric_context` or in an explicit new-resource decision recorded in the epic.

## When to Use

- After calling `get_fabric_context` and before calling `generate_diagram`
- When an epic description mentions a Lakehouse, Pipeline, or Notebook by name
- When reviewing a proposed architecture spec for resource validity

## Resource Grounding Rules

### Existing Resources (from `get_fabric_context`)
- Use the **exact display name** returned by the API — do not abbreviate, rename, or paraphrase
- If a resource fits the epic's layer and type, prefer reusing it over proposing a new one
- Document reuse decisions in the edge label (e.g. "reuses Bronze Lakehouse")

### New Resources (not in `get_fabric_context`)
- A new resource is permitted only when the epic's requirements cannot be satisfied by any existing resource
- New resource names must follow the workspace naming convention inferred from existing names (e.g. if existing names are `bronze_sales`, `bronze_hr`, a new one should follow `bronze_<domain>`)
- New resources must be distinguishable from existing ones — never propose a name that could be confused with an existing resource

### Resource Type Mapping

| Fabric Item Type | Diagram Node Type | Zone |
|---|---|---|
| Lakehouse | `lakehouse` (cylinder) | Bronze, Silver, or Gold |
| Data Pipeline | `pipeline` | Bronze (ingestion) |
| Notebook | `notebook` | Silver or Gold (transformation) |
| Dataflow Gen2 | `dataflow` | Bronze (ingestion) |
| Semantic Model | `semantic_model` | Serving |
| Report | `report` | Serving |

### Prohibited Patterns
- Do not diagram a Fabric Data Warehouse unless it was returned by `get_fabric_context`
- Do not diagram a Semantic Model unless the epic explicitly describes a reporting or analytics output
- Do not split one Lakehouse into multiple nodes to represent different tables — one node per Lakehouse item

## Process

1. Call `get_fabric_context` and record the full inventory
2. For each proposed diagram node that is a Fabric item, check if it exists in the inventory
3. If it exists: use exact name, assign to correct layer and type
4. If it does not exist: verify the epic requires it; follow naming convention; mark as "(new)" in planning notes (not in the diagram label)
5. After generating the diagram, cross-reference every Fabric node against the inventory or epic text

## Boundaries

**Always:**
- Use the exact `displayName` from `get_fabric_context` for existing resources
- Prefer existing resources over new ones when the type and layer match
- Respect the resource-type-to-zone mapping table above

**Ask First:**
- Proposing more than two new Fabric resources for a single epic
- Placing a Notebook in the Bronze layer (unusual; Bronze is typically pipeline/dataflow-only)
- Diagnosing a missing resource type (e.g. the epic needs a Warehouse but none exists)

**Never:**
- Invent a Fabric resource name not grounded in `get_fabric_context` or epic text
- Rename or abbreviate an existing resource name in a diagram label
- Assign a Fabric item to the wrong zone (e.g. a Lakehouse in Serving)
- Represent Lakehouse tables as separate nodes — the Lakehouse item is the atomic unit

## Red Flags

- A diagram node name does not match any entry in `get_fabric_context` and the epic never mentions it
- Two diagram nodes have very similar names that could be the same Lakehouse
- A Pipeline node appears in Silver or Gold (pipelines belong in Bronze ingestion)
- A Notebook node appears in Bronze (notebooks belong in Silver/Gold transformation)
- The epic mentions a domain but no matching Lakehouse exists and no new one is proposed

## Verification

- Every `lakehouse`, `pipeline`, `notebook`, and `dataflow` node name either matches a `get_fabric_context` entry exactly or is explicitly justified by epic text
- No two nodes represent the same physical Fabric item
- Resource types match their assigned zones per the mapping table
- New resources follow the naming convention of the existing workspace
