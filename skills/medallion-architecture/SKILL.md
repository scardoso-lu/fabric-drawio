---
name: Medallion Architecture
description: Enforces Bronze/Silver/Gold layer discipline when designing Microsoft Fabric data architectures. Use when generating or reviewing any medallion architecture diagram for a Fabric workspace.
---

## Overview

The Medallion Architecture is a layered data organisation pattern in Microsoft Fabric. Each layer has a strict contract: Bronze is immutable raw ingestion, Silver is cleansed and typed, Gold is business-curated. Violating layer contracts produces diagrams that mislead engineers about where transformations occur and who owns data quality.

## When to Use

- Before generating any `.drawio` diagram for a Fabric-based epic
- When evaluating whether a proposed node belongs in Bronze, Silver, or Gold
- When an epic description is ambiguous about where a transformation should happen

## Layer Contracts

### Bronze (Raw)
- Stores data exactly as received from the source — no field renaming, no type casting, no filtering
- Ingestion tools only: Dataflows Gen2, Data Pipelines, COPY activity
- Schema is source-native; schema-on-read applies
- Append-only Delta tables; no deletes or updates
- Every source system gets its own table or folder partition

### Silver (Cleansed)
- Reads exclusively from Bronze; never directly from a source system
- Applies: deduplication, null handling, type casting, date standardisation, referential integrity checks
- PySpark Notebooks are the canonical transformation tool
- Produces typed, validated Delta tables with enforced schemas
- One Silver table per business entity (not per source)

### Gold (Curated)
- Reads exclusively from Silver; never from Bronze or a source
- Applies: business aggregations, dimensional modelling, KPI calculations, joins across entities
- PySpark Notebooks or SQL stored procedures
- Optimised for analytical query patterns (wide tables, pre-aggregated facts)
- Named after business concepts, not technical ones (e.g. `sales_summary` not `tbl_agg_sales`)

### Serving
- Reads from Gold only
- Permitted: Direct Lake Semantic Models, Power BI reports, SQL endpoints, export pipelines
- No transformation logic in the serving layer; data must arrive ready-to-consume

## Process

1. Identify each data hop in the epic and assign it to exactly one layer
2. Verify no layer skips exist (source → Silver, Bronze → Gold are both illegal)
3. Name every node after its business role, not its technical implementation
4. Confirm the serving layer node matches the epic's stated output (report, API, export)
5. Document any cross-layer dependency as a diagram edge with a descriptive label

## Boundaries

**Always:**
- Assign every node to exactly one layer
- Route data strictly Bronze → Silver → Gold → Serving
- Use lakehouse nodes for Bronze, Silver, and Gold storage
- Label edges with the semantic meaning of the data hop

**Ask First:**
- Deviating from the strict layer order for a documented architectural reason
- Placing a transformation directly inside a pipeline activity instead of a notebook

**Never:**
- Bypass a layer (e.g. source → Silver, Bronze → Gold)
- Place business logic (aggregations, KPIs) in Bronze
- Place raw source data in Silver or Gold
- Show transformation logic in the Serving layer

## Red Flags

- An epic description mentions "cleansing" but no Silver layer is planned
- A Gold node is connected directly to a data source
- A Bronze node has a notebook attached performing business calculations
- Two different layers share the same Lakehouse node

## Verification

- Every source node connects to exactly one Bronze node
- Every Silver node's only input is a Bronze node
- Every Gold node's only input is a Silver node
- Every Serving node's only input is a Gold node
- No node appears in more than one layer zone
