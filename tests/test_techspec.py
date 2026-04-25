"""Tests for drawio/techspec.py — build_tech_spec_md."""

import pytest

from techspec.builder import build_tech_spec_md


def _spec(**overrides) -> dict:
    base = {
        "epic_id": 1,
        "epic_title": "My Epic",
        "workspace_mode": "single",
        "data_sources": [],
        "bronze_nodes": [],
        "silver_nodes": [],
        "gold_nodes": [],
        "serving_nodes": [],
        "edges": [],
        "pseudoalgorithm": [],
        "tradeoffs": [],
        "unclear_steps": [],
    }
    base.update(overrides)
    return base


# ── Open Questions (first section) ────────────────────────────────────────────

class TestOpenQuestions:
    def _item(self, step="Unclear step", ref="epic says nothing", assumption="TBD", lands_from="Node A") -> dict:
        return {"step": step, "epic_reference": ref, "assumption": assumption, "lands_from": lands_from}

    def test_section_header_always_present(self):
        md = build_tech_spec_md(_spec())
        assert "## Open Questions" in md

    def test_preamble_present(self):
        md = build_tech_spec_md(_spec())
        assert "Resolve each one before starting the build." in md

    def test_empty_unclear_steps_shows_none_identified(self):
        md = build_tech_spec_md(_spec(unclear_steps=[]))
        assert "_No open questions identified._" in md

    def test_each_step_is_h3(self):
        items = [self._item(step="Schema unknown"), self._item(step="Auth method unclear")]
        md = build_tech_spec_md(_spec(unclear_steps=items))
        assert "### Schema unknown" in md
        assert "### Auth method unclear" in md

    def test_epic_reference_quoted(self):
        item = self._item(ref="the source is fully defined")
        md = build_tech_spec_md(_spec(unclear_steps=[item]))
        assert '"the source is fully defined"' in md

    def test_lands_from_backtick_quoted(self):
        item = self._item(lands_from="bronze_lakehouse")
        md = build_tech_spec_md(_spec(unclear_steps=[item]))
        assert "`bronze_lakehouse`" in md

    def test_assumption_present(self):
        item = self._item(assumption="Engineer must confirm SFTP path with vendor.")
        md = build_tech_spec_md(_spec(unclear_steps=[item]))
        assert "Engineer must confirm SFTP path with vendor." in md

    def test_h3_appears_before_assumption(self):
        item = self._item(step="My Step", assumption="My Assumption")
        md = build_tech_spec_md(_spec(unclear_steps=[item]))
        assert md.index("### My Step") < md.index("My Assumption")

    def test_multiple_items_all_rendered(self):
        items = [self._item(step=f"Step {i}") for i in range(4)]
        md = build_tech_spec_md(_spec(unclear_steps=items))
        for i in range(4):
            assert f"### Step {i}" in md

    def test_open_questions_before_architecture_overview(self):
        md = build_tech_spec_md(_spec())
        assert md.index("## Open Questions") < md.index("## Architecture Overview")

    def test_no_h3_when_no_unclear_steps(self):
        """With empty unclear_steps, no ### headings should appear (tradeoffs also empty)."""
        md = build_tech_spec_md(_spec(unclear_steps=[], tradeoffs=[]))
        assert "###" not in md


# ── Heading and metadata ───────────────────────────────────────────────────────

class TestHeading:
    def test_title_in_h1(self):
        md = build_tech_spec_md(_spec(epic_title="Sales Pipeline"))
        assert "# Tech Spec: Sales Pipeline" in md

    def test_epic_id_in_metadata(self):
        md = build_tech_spec_md(_spec(epic_id=42))
        assert "**Epic ID:** 42" in md

    def test_workspace_mode_single(self):
        md = build_tech_spec_md(_spec(workspace_mode="single"))
        assert "**Workspace mode:** single" in md

    def test_workspace_mode_cross(self):
        md = build_tech_spec_md(_spec(workspace_mode="cross"))
        assert "**Workspace mode:** cross" in md

    def test_architecture_overview_section_present(self):
        md = build_tech_spec_md(_spec())
        assert "## Architecture Overview" in md


# ── Data sources ──────────────────────────────────────────────────────────────

class TestDataSources:
    def test_sources_listed(self):
        sources = [
            {"name": "data.lu GTFS Feed", "type": "source"},
            {"name": "Address Register", "type": "source"},
        ]
        md = build_tech_spec_md(_spec(data_sources=sources))
        assert "`data.lu GTFS Feed`" in md
        assert "`Address Register`" in md

    def test_sources_line_absent_when_empty(self):
        md = build_tech_spec_md(_spec(data_sources=[]))
        assert "**Data sources:**" not in md

    def test_all_source_names_appear(self):
        names = ["Source A", "Source B", "Source C"]
        sources = [{"name": n, "type": "source"} for n in names]
        md = build_tech_spec_md(_spec(data_sources=sources))
        for name in names:
            assert f"`{name}`" in md


# ── Layer table ───────────────────────────────────────────────────────────────

class TestLayerTable:
    def test_table_headers_always_present(self):
        md = build_tech_spec_md(_spec())
        assert "| Layer | Assets |" in md
        assert "|---|---|" in md

    def test_non_empty_layers_appear_as_rows(self):
        md = build_tech_spec_md(_spec(
            bronze_nodes=[{"name": "raw_lh", "type": "lakehouse"}],
            gold_nodes=[{"name": "agg_nb", "type": "notebook"}],
        ))
        assert "| Bronze |" in md
        assert "| Gold |" in md

    def test_empty_layers_omitted(self):
        md = build_tech_spec_md(_spec(
            bronze_nodes=[{"name": "raw_lh", "type": "lakehouse"}],
            silver_nodes=[],
        ))
        assert "| Silver |" not in md

    def test_node_names_backtick_quoted_in_row(self):
        md = build_tech_spec_md(_spec(
            silver_nodes=[
                {"name": "cleanse_nb", "type": "notebook"},
                {"name": "silver_lh", "type": "lakehouse"},
            ]
        ))
        assert "`cleanse_nb`" in md
        assert "`silver_lh`" in md

    def test_cross_workspace_node_with_workspace_field(self):
        md = build_tech_spec_md(_spec(
            workspace_mode="cross",
            bronze_nodes=[{"name": "raw_lh", "type": "lakehouse", "workspace": "Sales Bronze"}],
        ))
        assert "`raw_lh`" in md

    def test_all_four_layers_present_when_populated(self):
        md = build_tech_spec_md(_spec(
            bronze_nodes=[{"name": "b", "type": "lakehouse"}],
            silver_nodes=[{"name": "s", "type": "lakehouse"}],
            gold_nodes=[{"name": "g", "type": "lakehouse"}],
            serving_nodes=[{"name": "r", "type": "report"}],
        ))
        for layer in ("Bronze", "Silver", "Gold", "Serving"):
            assert f"| {layer} |" in md


# ── Pseudoalgorithm ───────────────────────────────────────────────────────────

class TestPseudoalgorithm:
    def test_section_header_always_present(self):
        md = build_tech_spec_md(_spec())
        assert "## Implementation Pseudoalgorithm" in md

    def test_steps_are_numbered(self):
        steps = ["Ingest data", "Cleanse data", "Aggregate KPIs"]
        md = build_tech_spec_md(_spec(pseudoalgorithm=steps))
        assert "1. Ingest data" in md
        assert "2. Cleanse data" in md
        assert "3. Aggregate KPIs" in md

    def test_step_count_matches(self):
        steps = [f"Step {i}" for i in range(7)]
        md = build_tech_spec_md(_spec(pseudoalgorithm=steps))
        for i, step in enumerate(steps, 1):
            assert f"{i}. {step}" in md

    def test_empty_pseudoalgorithm_no_numbered_items(self):
        md = build_tech_spec_md(_spec(pseudoalgorithm=[]))
        assert "1." not in md

    def test_step_text_preserved_verbatim(self):
        step = "FOR each residence r: distance = haversine(r, nearest_stop)"
        md = build_tech_spec_md(_spec(pseudoalgorithm=[step]))
        assert step in md


# ── Tradeoffs ─────────────────────────────────────────────────────────────────

class TestTradeoffs:
    def test_section_header_always_present(self):
        md = build_tech_spec_md(_spec())
        assert "## Tradeoffs" in md

    def test_engineer_preamble_present(self):
        md = build_tech_spec_md(_spec())
        assert "left to the engineer" in md

    def test_each_topic_is_h3(self):
        tradeoffs = [
            {"topic": "Haversine vs. routing", "description": "..."},
            {"topic": "Daily vs. event-driven", "description": "..."},
        ]
        md = build_tech_spec_md(_spec(tradeoffs=tradeoffs))
        assert "### Haversine vs. routing" in md
        assert "### Daily vs. event-driven" in md

    def test_each_description_present(self):
        tradeoffs = [
            {"topic": "Topic A", "description": "First option is fast, second is accurate."},
            {"topic": "Topic B", "description": "Cost vs. governance tradeoff here."},
        ]
        md = build_tech_spec_md(_spec(tradeoffs=tradeoffs))
        assert "First option is fast, second is accurate." in md
        assert "Cost vs. governance tradeoff here." in md

    def test_empty_tradeoffs_no_h3(self):
        md = build_tech_spec_md(_spec(tradeoffs=[]))
        assert "###" not in md

    def test_tradeoff_topic_and_description_order(self):
        """Topic heading must appear before its description in the output."""
        tradeoffs = [{"topic": "My Topic", "description": "My Description"}]
        md = build_tech_spec_md(_spec(tradeoffs=tradeoffs))
        topic_pos = md.index("### My Topic")
        desc_pos = md.index("My Description")
        assert topic_pos < desc_pos


# ── Section ordering ──────────────────────────────────────────────────────────

class TestSectionOrder:
    def test_open_questions_before_overview_before_pseudoalgorithm_before_tradeoffs(self):
        md = build_tech_spec_md(_spec(
            unclear_steps=[{"step": "Q", "epic_reference": "r", "assumption": "a", "lands_from": "N"}],
            pseudoalgorithm=["Step 1"],
            tradeoffs=[{"topic": "T", "description": "D"}],
        ))
        oq_pos = md.index("## Open Questions")
        overview_pos = md.index("## Architecture Overview")
        algo_pos = md.index("## Implementation Pseudoalgorithm")
        tradeoffs_pos = md.index("## Tradeoffs")
        assert oq_pos < overview_pos < algo_pos < tradeoffs_pos

    def test_title_is_first_line(self):
        md = build_tech_spec_md(_spec(epic_title="My Title"))
        assert md.startswith("# Tech Spec: My Title")
