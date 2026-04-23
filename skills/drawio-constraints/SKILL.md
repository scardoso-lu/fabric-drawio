---
name: Draw.io Diagram Constraints
description: Enforces formatting, layout, and label rules for all generated .drawio files. Use whenever calling generate_diagram or reviewing diagram output to ensure files open and render correctly in draw.io Desktop and diagrams.net.
---

## Overview

Draw.io files are XML. Violations of label or style rules silently corrupt the visual output: HTML tags render as literal text, mismatched IDs break edge routing, and non-unique cell IDs crash the renderer. These constraints are non-negotiable because a diagram that does not render is worthless.

## When to Use

- Before calling `generate_diagram` with any node or edge specification
- When reviewing the output of `drawio/builder.py`
- When adding new node types or edge patterns to the builder

## Layout Rules

- Flow direction is strictly **left to right**: Data Sources → Bronze → Silver → Gold → Serving
- Zone background rectangles must be drawn before (lower z-order than) all node cells
- Nodes within a zone are stacked **vertically**, centred inside the zone rectangle
- Minimum horizontal gap between zone rectangles: 40 px
- Minimum vertical gap between stacked nodes: 20 px
- Zone rectangles must include at least 30 px padding on all sides around child nodes
- Page dimensions: A3 landscape (1654 × 1169) or wider; never smaller

## Label Rules

- All `value` attributes in `mxCell` elements must be **plain text only**
- HTML tags (`<b>`, `<i>`, `<br>`, `<font>`, etc.) are **forbidden** inside label values
- The `html=1` attribute must **never** appear in any node style string (use `html=0`)
- Labels must not contain XML special characters unescaped (`&`, `<`, `>`)
- Multi-word labels use spaces, not underscores or camelCase
- Maximum label length: 40 characters; wrap into a shorter name rather than truncating

## Node Style Rules

- Data source nodes: `rounded=1`, light blue fill (`#dae8fc`), blue stroke (`#6c8ebf`)
- Ingestion/processing nodes (pipelines, dataflows, notebooks): use the colours defined in `drawio/builder.py` for the layer they belong to
- Lakehouse nodes: `shape=cylinder3` with `boundedLbl=1;backgroundOutline=1;size=15`
- Semantic model nodes: height = 80 px (taller to fit two-line label); all others height = 60 px
- All nodes: width = 160 px
- Font size: 11 for node labels, 13 for zone headers; `fontStyle=1` (bold) everywhere

## Edge Rules

- Every data-flow hop must have a corresponding directed edge
- Edge style: `edgeStyle=orthogonalEdgeStyle` with explicit `exitX=1;exitY=0.5` and `entryX=0;entryY=0.5`
- Edge labels are plain text; empty string `""` is acceptable when the hop is self-evident
- Edges must reference valid `source` and `target` cell IDs that exist in the same `<root>`
- No floating edges (edges without a source or target)

## Cell ID Rules

- Cell IDs 0 and 1 are reserved for the mxGraph root cells; user content starts at ID 2
- All cell IDs must be unique integers within a file
- Zone rectangles occupy the lowest IDs (2–6 for a 5-zone diagram)
- Node IDs follow zone IDs sequentially; edge IDs follow node IDs

## Boundaries

**Always:**
- Set `html=0` in every node style string
- Use plain text for every `value` attribute
- Assign unique sequential integer IDs starting from 2
- Include both `<mxCell>` and its child `<mxGeometry>` for every vertex

**Ask First:**
- Adding a new node shape not already in `drawio/builder.py`
- Changing page dimensions from A3 landscape

**Never:**
- Use `html=1` in any style string
- Place HTML markup inside a `value` attribute
- Reuse the same cell ID for two different cells
- Create an edge whose `source` or `target` does not match an existing cell ID
- Use relative coordinates (all geometry must use absolute pixel values)

## Red Flags

- A node label contains `<`, `>`, or `&` characters
- An edge's `source` or `target` attribute references a non-existent cell ID
- Two cells share the same `id` attribute
- A zone rectangle's right edge is to the right of the page boundary
- Any style string contains `html=1`

## Verification

After generation, open the file in diagrams.net or draw.io Desktop and confirm:
- All five zone rectangles are visible with correct colour fills
- All node labels display as plain text (no raw HTML visible)
- All edges are connected (no dangling arrow ends)
- Flow reads left-to-right without any node overlapping a zone boundary
- Lakehouse nodes render as cylinders
