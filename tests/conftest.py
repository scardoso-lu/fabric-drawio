"""Shared fixtures for the fabric-drawio test suite."""

import json
from unittest.mock import MagicMock

import pytest


def make_httpx_response(status_code: int = 200, body: dict | list | None = None) -> MagicMock:
    """Return a MagicMock that behaves like an httpx.Response."""
    mock = MagicMock()
    mock.status_code = status_code
    mock.json.return_value = body if body is not None else {}
    mock.raise_for_status = MagicMock()
    if status_code >= 400:
        mock.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return mock


@pytest.fixture
def httpx_response():
    return make_httpx_response
