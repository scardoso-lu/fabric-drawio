---
name: Workspace Scoping
description: Governs how the agent chooses between single-workspace and cross-workspace design modes. Use when deciding which Purview collections to query for a given epic, and when placing nodes from different workspaces into the same diagram.
---

## Overview

A data pipeline epic can be scoped to one Fabric workspace (self-contained medallion) or span multiple workspaces (distributed medallion, e.g. a shared Bronze workspace feeding several domain-specific Gold workspaces). Choosing the wrong scope produces diagrams that either miss cross-workspace dependencies or include irrelevant assets that obscure the design intent.

## When to Use

- After calling `list_purview_collections` and before querying assets
- When an epic description references more than one workspace or domain
- When cross-workspace lineage hints are returned by `get_cross_workspace_assets`

## Workspace Modes

### Single-workspace mode
Use when:
- The epic explicitly names one workspace or collection
- All medallion layers (Bronze/Silver/Gold) exist within the same workspace
- No cross-workspace lineage hints are present for the relevant assets
- The `--workspace` CLI flag was provided

Behaviour:
- Call `get_workspace_assets` with the single collection ID
- All diagram nodes are drawn from that collection's inventory
- No workspace labels are needed on individual nodes

### Cross-workspace mode
Use when:
- The epic references multiple workspaces, domains, or teams
- Bronze is in a shared ingestion workspace; Silver/Gold are in domain workspaces
- `get_cross_workspace_assets` returns lineage hints connecting two or more collections
- The `--cross-workspace` CLI flag was provided with multiple collection IDs

Behaviour:
- Call `get_cross_workspace_assets` with the relevant collection IDs
- Include a `workspace` label on each node (the collection's friendly name)
- Cross-workspace edges must carry a label that names the target workspace
  (e.g. "to Domain-Gold WS")
- The diagram should still follow the Bronze → Silver → Gold → Serving flow
  even if that flow crosses workspace boundaries

### Auto mode (no CLI flag)
When no explicit scope is provided:
1. Inspect each epic's title, description, and tags for workspace/domain names
2. Match those names against the `friendly_name` values from `list_purview_collections`
3. If one collection matches: use single-workspace mode
4. If multiple collections match or if the epic mentions "cross-workspace", "shared", or
   "federated": use cross-workspace mode with the matched collections
5. If no match: default to single-workspace mode using the first collection returned;
   record the assumption in the run summary

## Cross-Workspace Diagram Rules

- Each workspace is represented as a **labelled swimlane** within its medallion zone
  (e.g. the Bronze zone may contain two sub-regions: "Ingestion WS" and "Raw WS")
- Node `workspace` field maps to a subtitle or bracket label — never alters the node's primary name
- Cross-workspace edges exit the source zone from the right and enter the target zone from the left,
  same as standard intra-diagram edges
- Do not duplicate a node that appears in one workspace into another — use an edge to show the hand-off

## Process

1. Call `list_purview_collections` → identify all available scopes
2. Read epic details → match workspace/domain signals to collection friendly names
3. Select mode (single / cross / auto-inferred)
4. Call the appropriate asset query tool
5. If cross-workspace: review lineage hints and add corresponding edges to the diagram spec
6. In the run summary: record which mode was used and which collections were included

## Boundaries

**Always:**
- Record workspace_mode ("single" or "cross") in the `generate_diagram` call
- Include the collection friendly name as the `workspace` field on nodes in cross-workspace mode
- Add a cross-workspace edge label when a data hop moves between collections

**Ask First:**
- Including more than three workspaces in a single diagram (may become unreadable)
- Mixing auto-inferred and explicitly flagged workspaces in the same run

**Never:**
- Query all collections by default when a specific scope is available
- Place nodes from different workspaces in the same zone sub-region without labelling their workspace
- Omit cross-workspace edges when lineage hints show table-level sharing between collections
- Use collection IDs (GUIDs) as visible diagram labels — always use friendly names

## Red Flags

- An epic mentions "shared Bronze" or "federated" but single-workspace mode was used
- A node's name contains a workspace prefix not present in the Purview collection list
- Cross-workspace edges are missing when `get_cross_workspace_assets` returned lineage hints
- The diagram contains nodes from a collection not relevant to the epic

## Verification

- `generate_diagram` was called with `workspace_mode` set
- In cross-workspace diagrams, every node has a non-empty `workspace` field matching a collection friendly name
- Every lineage hint from `get_cross_workspace_assets` has a corresponding edge in the diagram
- The run summary states which collections were included and why
