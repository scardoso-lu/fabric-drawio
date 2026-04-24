import re
import xml.etree.ElementTree as ET


# ── colour palette (matches fabric-medallion-architecture.drawio) ─────────────
_ZONE_STYLES = {
    "sources": ("DATA SOURCES", "#dae8fc", "#6c8ebf"),
    "bronze":  ("BRONZE (Raw)", "#ffe6cc", "#d6b656"),
    "silver":  ("SILVER (Cleansed)", "#d5e8d4", "#82b366"),
    "gold":    ("GOLD (Curated)", "#fff2cc", "#d6b656"),
    "serving": ("SERVING", "#e1d5e7", "#9673a6"),
}

_NODE_STYLES = {
    "source":         "rounded=1;whiteSpace=wrap;html=0;fillColor=#dae8fc;strokeColor=#6c8ebf;fontStyle=1;fontSize=11;",
    "pipeline":       "rounded=1;whiteSpace=wrap;html=0;fillColor=#f0a30a;strokeColor=#BD7000;fontColor=#000000;fontStyle=1;fontSize=11;",
    "dataflow":       "rounded=1;whiteSpace=wrap;html=0;fillColor=#f0a30a;strokeColor=#BD7000;fontColor=#000000;fontStyle=1;fontSize=11;",
    "lakehouse":      "shape=cylinder3;whiteSpace=wrap;html=0;boundedLbl=1;backgroundOutline=1;size=15;fillColor=#f0a30a;strokeColor=#BD7000;fontStyle=1;fontSize=11;",
    "notebook":       "rounded=1;whiteSpace=wrap;html=0;fillColor=#f8cecc;strokeColor=#b85450;fontStyle=1;fontSize=11;",
    "semantic_model": "rounded=1;whiteSpace=wrap;html=0;fillColor=#e1d5e7;strokeColor=#9673a6;fontStyle=1;fontSize=11;",
    "report":         "rounded=1;whiteSpace=wrap;html=0;fillColor=#7B68EE;strokeColor=#5A4FCF;fontColor=#ffffff;fontStyle=1;fontSize=11;",
    "default":        "rounded=1;whiteSpace=wrap;html=0;fillColor=#f5f5f5;strokeColor=#666666;fontStyle=1;fontSize=11;",
}

_LAKEHOUSE_COLORS = {
    "bronze": "fillColor=#f0a30a;strokeColor=#BD7000;",
    "silver": "fillColor=#d5e8d4;strokeColor=#82b366;",
    "gold":   "fillColor=#fff2cc;strokeColor=#d6b656;",
}

_EDGE_STYLE = (
    "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;"
    "exitX=1;exitY=0.5;exitDx=0;exitDy=0;"
    "entryX=0;entryY=0.5;entryDx=0;entryDy=0;fontSize=9;"
)

_NODE_W = 160
_NODE_H = 60
_NODE_H_TALL = 80
_ZONE_GAP = 40        # horizontal gap between zones
_NODE_GAP = 20        # vertical gap between stacked nodes
_ZONE_PAD_X = 30      # horizontal padding inside zone
_ZONE_PAD_TOP = 50    # space below zone label
_ZONE_PAD_BOT = 30


def _node_style(node_type: str, zone: str) -> str:
    if node_type == "lakehouse":
        base = "shape=cylinder3;whiteSpace=wrap;html=0;boundedLbl=1;backgroundOutline=1;size=15;fontStyle=1;fontSize=11;"
        colors = _LAKEHOUSE_COLORS.get(zone, "fillColor=#f5f5f5;strokeColor=#666666;")
        return base + colors
    return _NODE_STYLES.get(node_type, _NODE_STYLES["default"])


def _node_height(node_type: str) -> int:
    return _NODE_H_TALL if node_type == "semantic_model" else _NODE_H


def _zone_height(nodes: list[dict]) -> int:
    if not nodes:
        return _ZONE_PAD_TOP + _NODE_H + _ZONE_PAD_BOT
    total = sum(_node_height(n.get("type", "default")) for n in nodes)
    gaps = _NODE_GAP * (len(nodes) - 1)
    return _ZONE_PAD_TOP + total + gaps + _ZONE_PAD_BOT


_ZONE_W = _NODE_W + 2 * _ZONE_PAD_X


def slugify(title: str) -> str:
    s = title.lower().strip()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"[\s-]+", "-", s)
    return s.strip("-")[:80]


def build_drawio(spec: dict) -> str:
    zones_def = [
        ("sources", spec.get("data_sources", [])),
        ("bronze",  spec.get("bronze_nodes", [])),
        ("silver",  spec.get("silver_nodes", [])),
        ("gold",    spec.get("gold_nodes", [])),
        ("serving", spec.get("serving_nodes", [])),
    ]

    max_height = max(_zone_height(nodes) for _, nodes in zones_def)

    root = ET.Element("mxGraphModel", {
        "dx": "1422", "dy": "762", "grid": "1", "gridSize": "10",
        "guides": "1", "tooltips": "1", "connect": "1", "arrows": "1",
        "fold": "1", "page": "1", "pageScale": "1",
        "pageWidth": "1654", "pageHeight": "1169",
        "math": "0", "shadow": "0",
    })
    root_el = ET.SubElement(root, "root")
    ET.SubElement(root_el, "mxCell", {"id": "0"})
    ET.SubElement(root_el, "mxCell", {"id": "1", "parent": "0"})

    cell_id = 2
    name_to_id: dict[str, str] = {}

    # ── Layout zones left to right ──────────────────────────────────────────
    x_cursor = 20
    zone_x: dict[str, int] = {}
    zone_w: dict[str, int] = {}

    for zone_key, nodes in zones_def:
        zw = _ZONE_W
        zone_x[zone_key] = x_cursor
        zone_w[zone_key] = zw
        x_cursor += zw + _ZONE_GAP

    # ── Write zone background rectangles ────────────────────────────────────
    for zone_key, nodes in zones_def:
        label, fill, stroke = _ZONE_STYLES[zone_key]
        style = (
            f"rounded=1;whiteSpace=wrap;html=0;fillColor={fill};strokeColor={stroke};"
            "fontSize=13;fontStyle=1;verticalAlign=top;arcSize=3;opacity=50;"
        )
        cell = ET.SubElement(root_el, "mxCell", {
            "id": str(cell_id), "value": label,
            "style": style, "vertex": "1", "parent": "1",
        })
        ET.SubElement(cell, "mxGeometry", {
            "x": str(zone_x[zone_key]), "y": "20",
            "width": str(zone_w[zone_key]), "height": str(max_height),
            "as": "geometry",
        })
        cell_id += 1

    # ── Write nodes inside each zone ─────────────────────────────────────────
    for zone_key, nodes in zones_def:
        if not nodes:
            continue
        zx = zone_x[zone_key]
        node_x = zx + _ZONE_PAD_X
        # vertically centre the stack
        total_h = sum(_node_height(n.get("type", "default")) for n in nodes)
        total_gaps = _NODE_GAP * (len(nodes) - 1)
        stack_h = total_h + total_gaps
        y_start = 20 + _ZONE_PAD_TOP + (max_height - _ZONE_PAD_TOP - _ZONE_PAD_BOT - stack_h) // 2

        y = y_start
        for node in nodes:
            name = node.get("name", f"Node {cell_id}")
            ntype = node.get("type", "default")
            nh = _node_height(ntype)
            style = _node_style(ntype, zone_key)
            c = ET.SubElement(root_el, "mxCell", {
                "id": str(cell_id), "value": name,
                "style": style, "vertex": "1", "parent": "1",
            })
            ET.SubElement(c, "mxGeometry", {
                "x": str(node_x), "y": str(y),
                "width": str(_NODE_W), "height": str(nh),
                "as": "geometry",
            })
            name_to_id[name] = str(cell_id)
            cell_id += 1
            y += nh + _NODE_GAP

    # ── Write edges ──────────────────────────────────────────────────────────
    for edge in spec.get("edges", []):
        src_name = edge.get("from", "")
        tgt_name = edge.get("to", "")
        label = edge.get("label", "")
        src_id = name_to_id.get(src_name)
        tgt_id = name_to_id.get(tgt_name)
        if not src_id or not tgt_id:
            continue
        c = ET.SubElement(root_el, "mxCell", {
            "id": str(cell_id), "value": label,
            "style": _EDGE_STYLE, "edge": "1",
            "source": src_id, "target": tgt_id, "parent": "1",
        })
        ET.SubElement(c, "mxGeometry", {"relative": "1", "as": "geometry"})
        cell_id += 1

    ET.indent(root, space="  ")
    xml_str = ET.tostring(root, encoding="unicode", xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str
