"""Tests for devops/client.py — Azure DevOps REST client."""

import base64
from unittest.mock import MagicMock, patch

import pytest

from devops.client import DevOpsClient


def _make_client() -> DevOpsClient:
    return DevOpsClient(org="myorg", project="myproject", pat="secret-pat")


def _mock_response(body: dict, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = body
    resp.raise_for_status = MagicMock()
    return resp


class TestDevOpsClientInit:
    def test_base_url(self):
        client = DevOpsClient(org="contoso", project="MyProj", pat="pat123")
        assert "contoso" in client.base
        assert "MyProj" in client.base

    def test_auth_header_basic(self):
        client = _make_client()
        assert client.headers["Authorization"].startswith("Basic ")

    def test_auth_header_encodes_pat(self):
        client = DevOpsClient(org="o", project="p", pat="mypat")
        expected_token = base64.b64encode(b":mypat").decode()
        assert client.headers["Authorization"] == f"Basic {expected_token}"

    def test_content_type_json(self):
        client = _make_client()
        assert client.headers["Content-Type"] == "application/json"


class TestListEpics:
    def test_returns_ids_and_urls(self):
        client = _make_client()
        body = {"workItems": [{"id": 1, "url": "http://a"}, {"id": 2, "url": "http://b"}]}
        with patch("httpx.post", return_value=_mock_response(body)):
            result = client.list_epics()
        assert result == [{"id": 1, "url": "http://a"}, {"id": 2, "url": "http://b"}]

    def test_empty_result(self):
        client = _make_client()
        with patch("httpx.post", return_value=_mock_response({"workItems": []})):
            result = client.list_epics()
        assert result == []

    def test_wiql_includes_epic_type(self):
        client = _make_client()
        posted_json = {}
        def capture_post(url, **kwargs):
            posted_json.update(kwargs.get("json", {}))
            return _mock_response({"workItems": []})
        with patch("httpx.post", side_effect=capture_post):
            client.list_epics()
        assert "Epic" in posted_json.get("query", "")

    def test_state_filter_included_in_wiql(self):
        client = _make_client()
        captured = {}
        def capture_post(url, **kwargs):
            captured.update(kwargs.get("json", {}))
            return _mock_response({"workItems": []})
        with patch("httpx.post", side_effect=capture_post):
            client.list_epics(state="Active")
        assert "Active" in captured["query"]

    def test_area_path_filter_included(self):
        client = _make_client()
        captured = {}
        def capture_post(url, **kwargs):
            captured.update(kwargs.get("json", {}))
            return _mock_response({"workItems": []})
        with patch("httpx.post", side_effect=capture_post):
            client.list_epics(area_path="MyProject\\Team A")
        assert "MyProject" in captured["query"]

    def test_raises_on_http_error(self):
        client = _make_client()
        resp = _mock_response({}, status=401)
        resp.raise_for_status.side_effect = Exception("401 Unauthorized")
        with patch("httpx.post", return_value=resp):
            with pytest.raises(Exception, match="401"):
                client.list_epics()


class TestGetEpicDetails:
    def _fields_response(self, **fields) -> dict:
        defaults = {
            "System.Title": "My Epic",
            "System.State": "Active",
            "System.Description": "Some description",
            "Microsoft.VSTS.Common.AcceptanceCriteria": "AC here",
            "System.Tags": "tag1; tag2",
            "System.AreaPath": "MyProject\\Team",
        }
        defaults.update(fields)
        return {"fields": defaults}

    def test_returns_expected_keys(self):
        client = _make_client()
        with patch("httpx.get", return_value=_mock_response(self._fields_response())):
            result = client.get_epic_details(42)
        assert set(result.keys()) == {"id", "title", "state", "description", "acceptance_criteria", "tags", "area_path"}

    def test_id_matches_input(self):
        client = _make_client()
        with patch("httpx.get", return_value=_mock_response(self._fields_response())):
            result = client.get_epic_details(99)
        assert result["id"] == 99

    def test_maps_fields_correctly(self):
        client = _make_client()
        with patch("httpx.get", return_value=_mock_response(self._fields_response(
            **{"System.Title": "Epic Title", "System.State": "Closed"}
        ))):
            result = client.get_epic_details(1)
        assert result["title"] == "Epic Title"
        assert result["state"] == "Closed"

    def test_none_fields_become_empty_string(self):
        client = _make_client()
        body = {"fields": {
            "System.Title": "T",
            "System.State": "Active",
            "System.Description": None,
            "Microsoft.VSTS.Common.AcceptanceCriteria": None,
            "System.Tags": None,
            "System.AreaPath": "P",
        }}
        with patch("httpx.get", return_value=_mock_response(body)):
            result = client.get_epic_details(1)
        assert result["description"] == ""
        assert result["acceptance_criteria"] == ""
        assert result["tags"] == ""

    def test_calls_correct_endpoint(self):
        client = _make_client()
        captured_url = {}
        def capture_get(url, **kwargs):
            captured_url["url"] = url
            return _mock_response(self._fields_response())
        with patch("httpx.get", side_effect=capture_get):
            client.get_epic_details(55)
        assert "55" in captured_url["url"]
        assert "$expand=all" in captured_url["url"]

    def test_raises_on_http_error(self):
        client = _make_client()
        resp = _mock_response({}, status=404)
        resp.raise_for_status.side_effect = Exception("404 Not Found")
        with patch("httpx.get", return_value=resp):
            with pytest.raises(Exception, match="404"):
                client.get_epic_details(999)
