import base64
import httpx


class DevOpsClient:
    def __init__(self, org: str, project: str, pat: str):
        self.base = f"https://dev.azure.com/{org}/{project}/_apis"
        token = base64.b64encode(f":{pat}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
        }

    def list_epics(self, area_path: str | None = None, state: str | None = None) -> list[dict]:
        conditions = ["[System.WorkItemType] = 'Epic'"]
        if area_path:
            conditions.append(f"[System.AreaPath] UNDER '{area_path}'")
        if state:
            conditions.append(f"[System.State] = '{state}'")
        where = " AND ".join(conditions)
        wiql = {
            "query": (
                f"SELECT [System.Id], [System.Title], [System.State] "
                f"FROM WorkItems WHERE {where} ORDER BY [System.Id]"
            )
        }
        resp = httpx.post(
            f"{self.base}/wit/wiql?api-version=7.0",
            headers=self.headers,
            json=wiql,
            timeout=30,
        )
        resp.raise_for_status()
        items = resp.json().get("workItems", [])
        return [{"id": item["id"], "url": item["url"]} for item in items]

    def get_epic_details(self, epic_id: int) -> dict:
        resp = httpx.get(
            f"{self.base}/wit/workitems/{epic_id}?$expand=all&api-version=7.0",
            headers=self.headers,
            timeout=30,
        )
        resp.raise_for_status()
        fields = resp.json().get("fields", {})
        return {
            "id": epic_id,
            "title": fields.get("System.Title", ""),
            "state": fields.get("System.State", ""),
            "description": fields.get("System.Description", "") or "",
            "acceptance_criteria": fields.get("Microsoft.VSTS.Common.AcceptanceCriteria", "") or "",
            "tags": fields.get("System.Tags", "") or "",
            "area_path": fields.get("System.AreaPath", ""),
        }
