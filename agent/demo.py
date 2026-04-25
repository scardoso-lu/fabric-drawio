"""
Stub clients and scripted LLM that serve fixture data from examples/.
No network calls, no credentials — used exclusively by --demo mode.
"""

import json
from pathlib import Path

from purview.client import _infer_cross_workspace_lineage
from agent.llm import LLMClient, ChatResponse, ToolCall

_EXAMPLES_DIR = Path(__file__).parent.parent / "examples"


class DevOpsClientStub:
    """Serves epics from examples/devops_epics.json."""

    def __init__(self) -> None:
        self._epics: list[dict] = json.loads(
            (_EXAMPLES_DIR / "devops_epics.json").read_text(encoding="utf-8")
        )

    def list_epics(
        self, area_path: str | None = None, state: str | None = None
    ) -> list[dict]:
        epics = self._epics
        if state:
            epics = [e for e in epics if e["state"] == state]
        if area_path:
            epics = [e for e in epics if e["area_path"].startswith(area_path)]
        return [{"id": e["id"], "url": f"https://example.visualstudio.com/_workitems/edit/{e['id']}"} for e in epics]

    def get_epic_details(self, epic_id: int) -> dict:
        for epic in self._epics:
            if epic["id"] == epic_id:
                return epic
        raise KeyError(f"Epic {epic_id} not found in example data")


class PurviewClientStub:
    """Serves collections and assets from examples/purview_collections.json and purview_assets.json."""

    def __init__(self) -> None:
        self._collections: list[dict] = json.loads(
            (_EXAMPLES_DIR / "purview_collections.json").read_text(encoding="utf-8")
        )
        self._assets: dict[str, dict] = json.loads(
            (_EXAMPLES_DIR / "purview_assets.json").read_text(encoding="utf-8")
        )

    def list_collections(self) -> list[dict]:
        return self._collections

    def get_workspace_assets(self, collection_id: str) -> dict:
        data = self._assets.get(collection_id, {})
        return {
            "collection_id": collection_id,
            "collection_name": data.get("collection_name", collection_id),
            "data_sources": data.get("data_sources", []),
            "lakehouses": data.get("lakehouses", []),
            "pipelines": data.get("pipelines", []),
            "notebooks": data.get("notebooks", []),
            "warehouses": data.get("warehouses", []),
            "tables": data.get("tables", []),
        }

    def get_cross_workspace_assets(self, collection_ids: list[str]) -> dict:
        workspaces: dict[str, dict] = {}
        by_workspace: dict[str, list] = {}
        for cid in collection_ids:
            data = self._assets.get(cid, {})
            workspaces[cid] = {
                "collection_name": data.get("collection_name", cid),
                "lakehouses": data.get("lakehouses", []),
                "pipelines": data.get("pipelines", []),
                "notebooks": data.get("notebooks", []),
                "warehouses": data.get("warehouses", []),
                "tables": data.get("tables", []),
            }
            by_workspace[cid] = [
                {"entityType": "microsoft_fabric_table", "displayText": t["name"]}
                for t in data.get("tables", [])
            ]

        lineage_hints = _infer_cross_workspace_lineage(by_workspace)
        return {"workspaces": workspaces, "cross_workspace_lineage": lineage_hints}


# ── Scripted tech specs keyed by epic_id ──────────────────────────────────────
# Each value is (pseudoalgorithm steps, tradeoffs list, unclear_steps list).

_SCRIPTED_TECH_SPECS: dict[int, tuple[list[str], list[dict], list[dict]]] = {
    101: (
        [
            "Bronze — SQL_Server_Ingest_Pipeline: connect to AdventureWorks via Fabric Data Pipeline "
            "JDBC source; extract orders and products tables with a full-load watermark on modified_date; "
            "land as Parquet in bronze_sales_lakehouse (raw_orders, raw_products).",
            "Bronze — SharePoint_Ingest_Pipeline: use the SharePoint Online connector to read the "
            "regional targets Excel file; land as raw_regional_targets in bronze_sales_lakehouse.",
            "Silver — cleanse_orders_notebook: cast order_date to DATE, revenue to DECIMAL(18,2), "
            "drop duplicates on order_id, enforce NOT NULL on customer_id; write to silver_sales_lakehouse.",
            "Silver — cleanse_products_notebook: normalise product_category to a controlled vocabulary, "
            "fill null product_subcategory with 'Unknown'; write to silver_sales_lakehouse.",
            "Gold — aggregate_sales_kpis_notebook: JOIN orders × products × regional_targets on "
            "region_code and month; compute monthly_revenue = SUM(revenue), units_sold = COUNT(*), "
            "target_attainment = monthly_revenue / monthly_target; write to gold_sales_lakehouse.",
            "Serving — publish Sales Semantic Model as Direct Lake dataset over gold_sales_lakehouse; "
            "build Sales Dashboard report with revenue trend, units-sold bar chart, and attainment gauge.",
        ],
        [
            {
                "topic": "Incremental vs. full-load ingestion",
                "description": (
                    "Full-load (truncate-and-reload) is simple to implement and guarantees consistency "
                    "but becomes expensive as the orders table grows. Watermark-based incremental load "
                    "on modified_date reduces Fabric CU consumption and pipeline duration, but requires "
                    "the source table to have a reliable last-modified timestamp and the pipeline to "
                    "handle late-arriving updates and deletes."
                ),
            },
            {
                "topic": "SharePoint connector: Dataflow Gen2 vs. custom pipeline",
                "description": (
                    "Dataflow Gen2 has a native SharePoint Online connector and requires no code, making "
                    "it fast to set up. However it lacks fine-grained retry logic and monitoring hooks. "
                    "A custom pipeline using the HTTP connector gives full control over refresh scheduling "
                    "and error handling but requires more development effort."
                ),
            },
            {
                "topic": "Cross-workspace governance vs. single-workspace simplicity",
                "description": (
                    "Three separate workspaces (Bronze / Silver / Gold) enforce strict layer isolation, "
                    "allow per-layer capacity assignment, and enable independent access control for raw "
                    "vs. curated data. A single shared workspace reduces operational overhead and "
                    "cross-workspace data copy costs but makes it harder to enforce least-privilege access "
                    "and to charge costs back to individual teams."
                ),
            },
            {
                "topic": "Direct Lake vs. Import mode for the semantic model",
                "description": (
                    "Direct Lake reads Delta files directly from the lakehouse with no data copy, giving "
                    "near-real-time freshness and zero import refresh cost. Import mode caches data in "
                    "Power BI Premium, enabling faster query performance for large models and supporting "
                    "row-level security (RLS). Choose Import if RLS is required or if query latency on "
                    "Direct Lake is unacceptable."
                ),
            },
        ],
        [
            {
                "step": "AdventureWorks source schema",
                "epic_reference": "sales data from AdventureWorks SQL Server",
                "assumption": (
                    "Tables Orders and Products assumed; engineer must confirm column names, "
                    "data types, and whether a CDC / change-tracking mechanism is available."
                ),
                "lands_from": "AdventureWorks SQL Server",
            },
            {
                "step": "KPI calculation windows",
                "epic_reference": "monthly and quarterly KPIs",
                "assumption": (
                    "Calendar-month window assumed; fiscal calendar alignment, rolling-quarter "
                    "boundaries, and handling of partial months are not specified in the epic."
                ),
                "lands_from": "aggregate_sales_kpis_notebook",
            },
        ],
    ),
    102: (
        [
            "Bronze — SAP_HR_Ingest_Pipeline: pick up the daily SuccessFactors CSV drop from the "
            "SFTP landing zone; validate file presence and row count; load into bronze_hr_lakehouse "
            "as a raw Delta table with ingestion_date partition.",
            "Silver — cleanse_hr_notebook: parse hire_date and termination_date as ISO-8601 DATE; "
            "normalise job_grade to a canonical code list; fill null cost_centre with department default; "
            "deduplicate on employee_id keeping the latest record; write to silver_hr_lakehouse.",
            "Gold — aggregate_hr_kpis_notebook: GROUP BY department, calendar_month to compute "
            "headcount = COUNT(active employees); rolling_attrition_12m = "
            "terminations_in_window / AVG(headcount_in_window); write to gold_hr_lakehouse.",
            "Gold — load HR_Analytics_Warehouse: use COPY INTO to sync gold Delta tables into the "
            "Fabric Warehouse so the People Analytics team can query via SQL endpoint.",
            "Serving — publish HR Semantic Model as Direct Lake dataset; build HR Headcount Report "
            "with headcount-by-department bar chart and 12-month attrition trend line.",
        ],
        [
            {
                "topic": "SFTP drop vs. SAP OData API",
                "description": (
                    "The CSV SFTP drop is the simplest integration and requires no SAP API credentials, "
                    "but it is batch-only (daily at best) and fragile to file-format changes. The SAP "
                    "SuccessFactors OData API supports near-real-time delta feeds and structured payloads, "
                    "but requires an API licence, credential management, and more complex pipeline logic."
                ),
            },
            {
                "topic": "Bronze format: raw CSV landing vs. Delta conversion on ingest",
                "description": (
                    "Landing the raw CSV in the Files section of the lakehouse preserves the original "
                    "bytes for audit and replay but requires a separate step to convert to Delta before "
                    "Silver can read it. Converting directly to Delta on ingest gives time-travel and "
                    "schema enforcement immediately, at the cost of slightly more complex pipeline logic "
                    "and no verbatim raw-file archive."
                ),
            },
            {
                "topic": "Warehouse SQL endpoint vs. Direct Lake for People Analytics",
                "description": (
                    "The Fabric Warehouse SQL endpoint supports T-SQL, row-level security, and familiar "
                    "BI tooling (Excel, SSMS), making it accessible to non-Power BI analysts. Direct Lake "
                    "is faster for Power BI-native consumers but does not support RLS without additional "
                    "configuration and cannot be queried from external SQL tools."
                ),
            },
            {
                "topic": "Attrition window: calendar month vs. rolling 12 months",
                "description": (
                    "Monthly attrition is easy to explain to HR business partners and aligns with "
                    "payroll cycles, but is noisy for small departments. Rolling 12-month attrition "
                    "smooths seasonality and is the industry-standard metric, but requires a larger "
                    "history window and is harder to communicate to non-technical stakeholders."
                ),
            },
        ],
        [
            {
                "step": "SFTP path and file naming convention",
                "epic_reference": "daily SuccessFactors CSV drop",
                "assumption": (
                    "Single daily file assumed; engineer must confirm the SFTP host, directory path, "
                    "and filename pattern (e.g. date-stamped vs. fixed name) with the SAP team."
                ),
                "lands_from": "SAP SuccessFactors CSV Export",
            },
            {
                "step": "Canonical job_grade code list",
                "epic_reference": "normalise job_grade to a controlled vocabulary",
                "assumption": (
                    "Code list not provided in the epic; engineer must obtain the reference table "
                    "from HR and decide whether it lives in a Delta lookup table or pipeline parameter."
                ),
                "lands_from": "cleanse_hr_notebook",
            },
        ],
    ),
    103: (
        [
            "Bronze — data_lu_bus_stops_pipeline: HTTP GET the GTFS static feed ZIP from "
            "data.lu (transport/gtfs); extract stops.txt; parse stop_id, stop_name, stop_lat, "
            "stop_lon; land as raw_bus_stops Delta table in bronze_mobility_lakehouse. "
            "Schedule daily (GTFS feed is versioned on publish date).",
            "Bronze — data_lu_residences_pipeline: HTTP GET the address register GeoJSON from "
            "data.lu (addresses/adresses-luxemburg); parse id, street, postcode, commune, "
            "latitude, longitude; land as raw_residences Delta table in bronze_mobility_lakehouse. "
            "Schedule weekly (address register is stable).",
            "Silver — cleanse_bus_stops_notebook: cast stop_lat/stop_lon to DOUBLE, assert "
            "within Luxembourg bounding box (lat 49.44–50.18, lon 5.73–6.53), drop duplicates "
            "on stop_id, write bus_stops to silver_mobility_lakehouse.",
            "Silver — cleanse_residences_notebook: cast latitude/longitude to DOUBLE, drop "
            "records with null coordinates or outside bounding box, normalise commune names to "
            "official LAU codes, write residences to silver_mobility_lakehouse.",
            "Gold — compute_accessibility_notebook: for each residence r, compute "
            "nearest_stop_distance_km = MIN over all stops s of haversine(r.lat, r.lon, s.lat, s.lon); "
            "add accessibility_band: 'green' if dist < 1, 'yellow' if dist < 2, else 'red'; "
            "write transport_accessibility to gold_mobility_lakehouse.",
            "Gold — load Mobility_Analytics_Warehouse: COPY INTO from gold Delta table for ad-hoc "
            "SQL analysis by the mobility team.",
            "Serving — publish Transport Accessibility Semantic Model as Direct Lake dataset over "
            "transport_accessibility; build Transport Accessibility Heatmap report using a Power BI "
            "filled-map visual coloured by accessibility_band.",
        ],
        [
            {
                "topic": "Distance metric: Haversine (straight-line) vs. routable walking distance",
                "description": (
                    "Haversine geodesic distance is fast, free, and trivially parallelisable in PySpark, "
                    "but overestimates accessibility in areas with rivers, motorways, or irregular street "
                    "grids. Routable walking distance (via OSRM, Valhalla, or the Geoapify API) is far "
                    "more accurate but requires a routing engine or paid API, adds latency, and costs "
                    "money at scale. Start with Haversine and switch to routing if business stakeholders "
                    "require pedestrian-network accuracy."
                ),
            },
            {
                "topic": "PySpark cross-join vs. spatial indexing for nearest-stop lookup",
                "description": (
                    "A naive cross-join (all residences × all stops) is simple to write but O(R × S) in "
                    "compute. With ~200k residences and ~3k bus stops in Luxembourg this is manageable "
                    "today (~600M pairs), but explodes with denser datasets. Alternatives: BallTree / "
                    "KD-Tree in scikit-learn (single-node, fast), Apache Sedona spatial joins "
                    "(distributed, requires adding the sedona dependency), or pre-binning into H3 "
                    "hexagonal grid cells (fast approximation, negligible error at H3 resolution 8)."
                ),
            },
            {
                "topic": "Refresh cadence: daily vs. event-driven",
                "description": (
                    "A daily scheduled pipeline is simple and predictable. Because the GTFS feed and "
                    "address register change infrequently, most daily runs will produce no net changes, "
                    "wasting Fabric CUs. An event-driven trigger (e.g. watch the data.lu dataset "
                    "last-modified header) only runs when the source actually changes, reducing cost. "
                    "The tradeoff is additional pipeline complexity and dependency on data.lu's HTTP "
                    "cache-control headers being reliable."
                ),
            },
            {
                "topic": "Map visual: Power BI filled map vs. Azure Maps custom visual",
                "description": (
                    "Power BI's built-in filled map aggregates data to administrative boundaries "
                    "(commune or canton level) and is included in all Power BI licences. Azure Maps "
                    "visual renders individual point markers with exact coordinates and custom colour "
                    "coding, giving a true per-residence heatmap. Azure Maps requires an Azure Maps "
                    "account (billed by tile requests) and the Power BI custom visual from AppSource."
                ),
            },
            {
                "topic": "Accessibility threshold: fixed 1 km / 2 km vs. configurable parameter",
                "description": (
                    "Hard-coding the green/yellow/red thresholds (< 1 km, 1–2 km, > 2 km) is simple "
                    "but makes the pipeline brittle if the mobility team later wants to experiment with "
                    "different service-level targets (e.g. 500 m urban / 1.5 km rural). Externalising "
                    "the thresholds as a pipeline parameter or a small configuration Delta table adds "
                    "flexibility at the cost of slightly more pipeline and semantic model complexity."
                ),
            },
        ],
        [
            {
                "step": "data.lu GTFS feed URL and authentication",
                "epic_reference": "Ingest bus stop locations (GTFS static feed) from Luxembourg's open data portal (data.lu)",
                "assumption": (
                    "Public HTTP endpoint with no authentication assumed; engineer must verify the "
                    "exact URL path, confirm there is no API key requirement, and check data.lu's "
                    "terms of use for automated download frequency."
                ),
                "lands_from": "data_lu_bus_stops_pipeline",
            },
            {
                "step": "Accessibility band threshold source",
                "epic_reference": "< 1km green, >1 and < 2 yellow, else red",
                "assumption": (
                    "Thresholds taken verbatim from the epic; engineer must decide whether these "
                    "are hard-coded constants in the notebook or externalised as pipeline parameters "
                    "to allow the mobility team to adjust service-level targets without a code change."
                ),
                "lands_from": "compute_accessibility_notebook",
            },
        ],
    ),
}

_DEFAULT_TECH_SPEC: tuple[list[str], list[dict], list[dict]] = (
    [
        "Implement Bronze ingestion",
        "Implement Silver cleansing",
        "Implement Gold aggregation",
        "Publish Serving layer",
    ],
    [{"topic": "Architecture decisions", "description": "Review the epic description and define tradeoffs specific to this domain."}],
    [],
)


def _add_layer_edges(
    sources: list[dict],
    bronze: list[dict],
    silver: list[dict],
    gold: list[dict],
    serving: list[dict],
    edges: list[dict],
) -> None:
    """Wire data-flow edges: sources→bronze pipelines, lakehouses→next-layer notebooks."""
    bronze_pipelines = [n for n in bronze if n["type"] == "pipeline"]
    bronze_lh = next((n for n in bronze if n["type"] == "lakehouse"), None)
    silver_nb = [n for n in silver if n["type"] == "notebook"]
    silver_lh = next((n for n in silver if n["type"] == "lakehouse"), None)
    gold_nb = [n for n in gold if n["type"] == "notebook"]
    gold_lh = next((n for n in gold if n["type"] == "lakehouse"), None)

    for src in sources:
        for pl in bronze_pipelines:
            edges.append({"from": src["name"], "to": pl["name"]})
    if bronze_lh:
        for nb in silver_nb:
            edges.append({"from": bronze_lh["name"], "to": nb["name"]})
    if silver_lh:
        for nb in gold_nb:
            edges.append({"from": silver_lh["name"], "to": nb["name"]})
    if gold_lh:
        for sn in serving:
            edges.append({"from": gold_lh["name"], "to": sn["name"]})


class ScriptedClient(LLMClient):
    """
    Drives the agentic loop without calling any external LLM API.
    Issues a fixed sequence of tool calls derived from the fixture data at runtime.
    Used in --demo mode so no API key is required.
    """

    def __init__(self) -> None:
        self._phase = "list_epics"
        self._epics: list[dict] = []
        self._collections: list[dict] = []
        self._epic_idx = 0
        self._current_epic: dict = {}
        self._pending_assets: dict = {}
        self._tc_id = 0

    def _new_id(self) -> str:
        self._tc_id += 1
        return f"demo_{self._tc_id}"

    def _last_tool_results(self, messages: list[dict]) -> list[str]:
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, list):
                    results = [
                        item["content"]
                        for item in content
                        if isinstance(item, dict) and item.get("type") == "tool_result"
                    ]
                    if results:
                        return results
        return []

    def send(self, system: str, messages: list[dict], tools: list[dict]) -> ChatResponse:
        results = self._last_tool_results(messages)

        if self._phase == "list_epics":
            self._phase = "list_collections"
            return ChatResponse(
                text=None,
                tool_calls=[ToolCall(id=self._new_id(), name="list_devops_epics", input={})],
                _native=None,
            )

        if self._phase == "list_collections":
            self._epics = json.loads(results[0]) if results else []
            self._phase = "fetch_epic_details"
            return ChatResponse(
                text=None,
                tool_calls=[ToolCall(id=self._new_id(), name="list_purview_collections", input={})],
                _native=None,
            )

        if self._phase == "fetch_epic_details":
            self._collections = json.loads(results[0]) if results else []
            self._epic_idx = 0
            return self._next_epic_details()

        if self._phase == "fetch_assets":
            self._current_epic = json.loads(results[0]) if results else {}
            return self._fetch_assets()

        if self._phase == "generate":
            self._pending_assets = json.loads(results[0]) if results else {}
            return self._generate()

        if self._phase == "advance":
            self._epic_idx += 1
            return self._next_epic_details()

        return ChatResponse(text="Demo complete.", tool_calls=[], _native=None)

    def _next_epic_details(self) -> ChatResponse:
        if self._epic_idx >= len(self._epics):
            return ChatResponse(
                text=(
                    f"Demo complete. Generated {len(self._epics)} diagram(s) from fixture data "
                    "in examples/. No LLM API was called — all decisions were scripted."
                ),
                tool_calls=[],
                _native=None,
            )
        self._phase = "fetch_assets"
        epic = self._epics[self._epic_idx]
        return ChatResponse(
            text=None,
            tool_calls=[ToolCall(id=self._new_id(), name="get_epic_details", input={"epic_id": epic["id"]})],
            _native=None,
        )

    def _is_cross(self, epic: dict) -> bool:
        return "cross-workspace" in epic.get("tags", "")

    def _fetch_assets(self) -> ChatResponse:
        self._phase = "generate"
        epic = self._current_epic
        area = epic.get("area_path", "").lower().split("\\")[-1]
        if self._is_cross(epic):
            cids = [c["id"] for c in self._collections if area in c["id"]]
            return ChatResponse(
                text=None,
                tool_calls=[ToolCall(
                    id=self._new_id(),
                    name="get_cross_workspace_assets",
                    input={"collection_ids": cids},
                )],
                _native=None,
            )
        matched = next(
            (c["id"] for c in self._collections if area in c["id"]),
            self._collections[-1]["id"] if self._collections else "",
        )
        return ChatResponse(
            text=None,
            tool_calls=[ToolCall(
                id=self._new_id(),
                name="get_workspace_assets",
                input={"collection_id": matched},
            )],
            _native=None,
        )

    def _generate(self) -> ChatResponse:
        self._phase = "advance"
        epic = self._current_epic
        spec = (
            self._build_cross_spec(epic, self._pending_assets)
            if self._is_cross(epic)
            else self._build_single_spec(epic, self._pending_assets)
        )
        return ChatResponse(
            text=None,
            tool_calls=[ToolCall(id=self._new_id(), name="generate_diagram", input=spec)],
            _native=None,
        )

    def _build_cross_spec(self, epic: dict, assets: dict) -> dict:
        workspaces = assets.get("workspaces", {})
        data_sources = [
            {"name": "AdventureWorks SQL Server", "type": "source"},
            {"name": "SharePoint Regional Targets", "type": "source"},
        ]
        bronze: list[dict] = []
        silver: list[dict] = []
        gold: list[dict] = []
        serving: list[dict] = []
        edges: list[dict] = []
        gold_ws_name = ""

        for cid, ws in workspaces.items():
            ws_name = ws.get("collection_name", cid)
            layer = "bronze" if "bronze" in cid else "silver" if "silver" in cid else "gold"
            target = bronze if layer == "bronze" else silver if layer == "silver" else gold
            for p in ws.get("pipelines", []):
                target.append({"name": p["name"], "type": "pipeline", "workspace": ws_name})
            for lh in ws.get("lakehouses", []):
                target.append({"name": lh["name"], "type": "lakehouse", "workspace": ws_name})
            for nb in ws.get("notebooks", []):
                target.append({"name": nb["name"], "type": "notebook", "workspace": ws_name})
            for wh in ws.get("warehouses", []):
                target.append({"name": wh["name"], "type": "warehouse", "workspace": ws_name})
            if layer == "gold":
                gold_ws_name = ws_name

        title = epic.get("title", "")
        serving += [
            {"name": f"{title} Semantic Model", "type": "semantic_model", "workspace": gold_ws_name},
            {"name": f"{title} Report", "type": "report", "workspace": gold_ws_name},
        ]
        _add_layer_edges(data_sources, bronze, silver, gold, serving, edges)
        algo, tradeoffs, unclear_steps = _SCRIPTED_TECH_SPECS.get(epic.get("id"), _DEFAULT_TECH_SPEC)
        return {
            "epic_id": epic["id"], "epic_title": title, "workspace_mode": "cross",
            "data_sources": data_sources, "bronze_nodes": bronze, "silver_nodes": silver,
            "gold_nodes": gold, "serving_nodes": serving, "edges": edges,
            "pseudoalgorithm": algo, "tradeoffs": tradeoffs, "unclear_steps": unclear_steps,
        }

    def _build_single_spec(self, epic: dict, assets: dict) -> dict:
        data_sources = assets.get("data_sources") or [{"name": "External Source", "type": "source"}]
        bronze: list[dict] = []
        silver: list[dict] = []
        gold: list[dict] = []
        edges: list[dict] = []

        for p in assets.get("pipelines", []):
            bronze.append({"name": p["name"], "type": "pipeline"})
        for lh in assets.get("lakehouses", []):
            n = lh["name"].lower()
            node = {"name": lh["name"], "type": "lakehouse"}
            (bronze if "bronze" in n else silver if "silver" in n else gold).append(node)
        for nb in assets.get("notebooks", []):
            n = nb["name"].lower()
            node = {"name": nb["name"], "type": "notebook"}
            (silver if "cleanse" in n else gold).append(node)
        for wh in assets.get("warehouses", []):
            gold.append({"name": wh["name"], "type": "warehouse"})

        title = epic.get("title", "")
        serving = [
            {"name": f"{title} Semantic Model", "type": "semantic_model"},
            {"name": f"{title} Report", "type": "report"},
        ]
        _add_layer_edges(data_sources, bronze, silver, gold, serving, edges)
        algo, tradeoffs, unclear_steps = _SCRIPTED_TECH_SPECS.get(epic.get("id"), _DEFAULT_TECH_SPEC)
        return {
            "epic_id": epic["id"], "epic_title": title, "workspace_mode": "single",
            "data_sources": data_sources, "bronze_nodes": bronze, "silver_nodes": silver,
            "gold_nodes": gold, "serving_nodes": serving, "edges": edges,
            "pseudoalgorithm": algo, "tradeoffs": tradeoffs, "unclear_steps": unclear_steps,
        }

    def pack_assistant(self, response: ChatResponse) -> list[dict]:
        content: list[dict] = []
        if response.text:
            content.append({"type": "text", "text": response.text})
        for tc in response.tool_calls:
            content.append({"type": "tool_use", "id": tc.id, "name": tc.name, "input": tc.input})
        return [{"role": "assistant", "content": content}]

    def pack_tool_results(self, calls: list[ToolCall], results: list[str]) -> list[dict]:
        return [{"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": tc.id, "content": result}
            for tc, result in zip(calls, results)
        ]}]
