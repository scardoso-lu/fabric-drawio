---
name: kiss-yagni
description: Prefer the simplest solution that satisfies the current epic; never add complexity for hypothetical future needs
---

# KISS / YAGNI — Minimum Viable Architecture

## Overview
Generate the simplest architecture that satisfies the epic as written. Every added component, pattern, or abstraction must be justified by a current, concrete requirement in the epic text.

## Always
- Write pseudoalgorithm steps in one short sentence each — name the asset and the action; omit implementation details (data types, column names, NULL handling) that belong in the notebook code
- In every tradeoff, identify which option is simpler and state it as the recommended starting point
- Use a single-node approach (plain PySpark, Pandas) before recommending distributed spatial libraries

## Never
- Add monitoring hooks, or alerting unless the epic requires it
- Recommend distributed processing (Sedona, H3, KD-Tree at scale) when the data volumes in the epic are manageable with a cross-join or BallTree
- Introduce pipeline parameters or config tables for values the epic states as fixed constants
- Design for hypothetical future requirements not mentioned in the epic (e.g. "in case the team later wants…")
- List more than one extra optimisation layer per tradeoff — present the simple option and the one meaningful complex alternative

## Red Flags
- A pseudoalgorithm step that specifies a data type, a column name, or a NULL-handling rule — that is code, not architecture
- A tradeoff that presents two complex options without naming the simpler default
- A diagram node added "for future flexibility" that has no corresponding task in the epic
- A tradeoff description longer than three sentences per option
