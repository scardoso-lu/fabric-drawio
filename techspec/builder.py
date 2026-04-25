"""
Markdown tech-spec builder.

Given the same generate_diagram spec dict it always produces the same output.
"""


def build_tech_spec_md(spec: dict) -> str:
    title = spec.get("epic_title", "")
    mode = spec.get("workspace_mode", "")
    sources = spec.get("data_sources", [])
    layers = [
        ("Bronze",  spec.get("bronze_nodes", [])),
        ("Silver",  spec.get("silver_nodes", [])),
        ("Gold",    spec.get("gold_nodes", [])),
        ("Serving", spec.get("serving_nodes", [])),
    ]
    unclear_steps = spec.get("unclear_steps", [])

    lines: list[str] = [
        f"# Tech Spec: {title}",
        "",
        f"**Epic ID:** {spec.get('epic_id', '')}  ",
        f"**Workspace mode:** {mode}  ",
        "",
    ]

    # Open Questions comes first so the engineer sees gaps before reading the plan.
    lines += [
        "## Open Questions",
        "",
        "> The items below are ambiguous or underdefined in the epic or Purview catalogue.",
        "> Resolve each one before starting the build.",
        "",
    ]
    if unclear_steps:
        for item in unclear_steps:
            lines += [
                f"### {item['step']}",
                "",
                f"**From node:** `{item['lands_from']}`  ",
                f"**Epic says:** \"{item['epic_reference']}\"  ",
                f"**Assumption / action required:** {item['assumption']}",
                "",
            ]
    else:
        lines += ["_No open questions identified._", ""]

    lines += [
        "## Architecture Overview",
        "",
    ]

    if sources:
        lines.append("**Data sources:** " + ", ".join(f"`{s['name']}`" for s in sources))
        lines.append("")

    lines += ["| Layer | Assets |", "|---|---|"]
    for layer_name, nodes in layers:
        if nodes:
            asset_list = ", ".join(f"`{n['name']}`" for n in nodes)
            lines.append(f"| {layer_name} | {asset_list} |")
    lines.append("")

    lines += ["## Implementation Pseudoalgorithm", ""]
    for i, step in enumerate(spec.get("pseudoalgorithm", []), 1):
        lines.append(f"{i}. {step}")
    lines.append("")

    lines += [
        "## Tradeoffs",
        "",
        "> The following decisions are left to the engineer.",
        "> Each option carries different cost, complexity, and governance implications.",
        "",
    ]
    for t in spec.get("tradeoffs", []):
        lines += [f"### {t['topic']}", "", t["description"], ""]

    return "\n".join(lines)
