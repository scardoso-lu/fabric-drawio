"""Tests for drawio/builder.py — deterministic XML generation."""

import xml.etree.ElementTree as ET

import pytest

from drawio.builder import build_drawio, slugify


# ── slugify ────────────────────────────────────────────────────────────────────

class TestSlugify:
    def test_basic(self):
        assert slugify("Hello World") == "hello-world"

    def test_special_characters_removed(self):
        assert slugify("Epic #42: Data!") == "epic-42-data"

    def test_multiple_spaces_and_dashes(self):
        assert slugify("foo  --  bar") == "foo-bar"

    def test_leading_trailing_whitespace(self):
        assert slugify("  hello  ") == "hello"

    def test_truncated_to_80(self):
        long = "a" * 100
        assert len(slugify(long)) == 80

    def test_empty_string(self):
        assert slugify("") == ""

    def test_numbers_preserved(self):
        assert slugify("Epic 2024") == "epic-2024"


# ── build_drawio ────────────────────────────────────────────────────────────────

def _minimal_spec() -> dict:
    return {
        "data_sources": [{"name": "SQL Source", "type": "source"}],
        "bronze_nodes": [{"name": "Raw Lakehouse", "type": "lakehouse"}],
        "silver_nodes": [{"name": "Cleanse Notebook", "type": "notebook"}],
        "gold_nodes": [{"name": "KPI Lakehouse", "type": "lakehouse"}],
        "serving_nodes": [{"name": "Sales Model", "type": "semantic_model"}],
        "edges": [
            {"from": "SQL Source", "to": "Raw Lakehouse", "label": "ingest"},
            {"from": "Raw Lakehouse", "to": "Cleanse Notebook"},
        ],
    }


class TestBuildDrawio:
    def test_returns_xml_string(self):
        xml = build_drawio(_minimal_spec())
        assert isinstance(xml, str)
        assert xml.startswith("<?xml")

    def test_valid_xml(self):
        xml = build_drawio(_minimal_spec())
        root = ET.fromstring(xml.split("\n", 1)[1])  # strip xml declaration
        assert root.tag == "mxGraphModel"

    def test_reserved_cell_ids(self):
        xml = build_drawio(_minimal_spec())
        root = ET.fromstring(xml.split("\n", 1)[1])
        root_el = root.find("root")
        cells = root_el.findall("mxCell")
        ids = [c.get("id") for c in cells]
        assert "0" in ids
        assert "1" in ids

    def test_no_html_in_values(self):
        xml = build_drawio(_minimal_spec())
        root = ET.fromstring(xml.split("\n", 1)[1])
        for cell in root.iter("mxCell"):
            value = cell.get("value", "")
            assert "<" not in value, f"HTML found in value: {value!r}"

    def test_html_0_in_all_node_styles(self):
        xml = build_drawio(_minimal_spec())
        root = ET.fromstring(xml.split("\n", 1)[1])
        for cell in root.iter("mxCell"):
            style = cell.get("style", "")
            # Zone backgrounds and edge cells don't have html=0 requirement;
            # check vertex node cells with fill colors
            if "vertex" in cell.attrib and "fillColor" in style:
                assert "html=0" in style, f"Missing html=0 in style: {style!r}"

    def test_five_zone_backgrounds(self):
        xml = build_drawio(_minimal_spec())
        root = ET.fromstring(xml.split("\n", 1)[1])
        root_el = root.find("root")
        zone_labels = {"DATA SOURCES", "BRONZE (Raw)", "SILVER (Cleansed)", "GOLD (Curated)", "SERVING"}
        cell_values = {c.get("value") for c in root_el.findall("mxCell")}
        assert zone_labels.issubset(cell_values)

    def test_node_names_appear_in_xml(self):
        xml = build_drawio(_minimal_spec())
        for name in ["SQL Source", "Raw Lakehouse", "Cleanse Notebook", "KPI Lakehouse", "Sales Model"]:
            assert name in xml

    def test_edge_skipped_for_unknown_node(self):
        spec = _minimal_spec()
        spec["edges"].append({"from": "Ghost Node", "to": "SQL Source"})
        xml = build_drawio(spec)
        # Should still produce valid XML without error
        ET.fromstring(xml.split("\n", 1)[1])

    def test_empty_zones_produce_valid_xml(self):
        spec = {
            "data_sources": [],
            "bronze_nodes": [],
            "silver_nodes": [],
            "gold_nodes": [],
            "serving_nodes": [],
            "edges": [],
        }
        xml = build_drawio(spec)
        ET.fromstring(xml.split("\n", 1)[1])

    def test_lakehouse_cylinder_style(self):
        spec = _minimal_spec()
        xml = build_drawio(spec)
        assert "shape=cylinder3" in xml

    def test_semantic_model_taller(self):
        spec = {
            "data_sources": [],
            "bronze_nodes": [],
            "silver_nodes": [],
            "gold_nodes": [],
            "serving_nodes": [
                {"name": "Model A", "type": "semantic_model"},
                {"name": "Report B", "type": "report"},
            ],
            "edges": [],
        }
        xml = build_drawio(spec)
        root = ET.fromstring(xml.split("\n", 1)[1])
        heights = {}
        for cell in root.iter("mxCell"):
            name = cell.get("value")
            geo = cell.find("mxGeometry")
            if geo is not None and name in ("Model A", "Report B"):
                heights[name] = int(geo.get("height"))
        assert heights["Model A"] > heights["Report B"]

    def test_page_dimensions(self):
        xml = build_drawio(_minimal_spec())
        root = ET.fromstring(xml.split("\n", 1)[1])
        assert int(root.get("pageWidth")) >= 1654
        assert int(root.get("pageHeight")) >= 1169

    def test_deterministic_output(self):
        spec = _minimal_spec()
        assert build_drawio(spec) == build_drawio(spec)
