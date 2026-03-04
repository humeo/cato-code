"""Pytest configuration and shared fixtures."""
from __future__ import annotations

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "integration: requires Docker to be running")
    config.addinivalue_line("markers", "e2e: requires Docker + valid GITHUB_TOKEN")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip integration and e2e tests unless explicitly requested."""
    if config.getoption("-m", default=""):
        return  # User specified a marker filter — respect it

    skip_integration = pytest.mark.skip(reason="use -m integration to run (requires Docker)")
    skip_e2e = pytest.mark.skip(reason="use -m e2e to run (requires Docker + GITHUB_TOKEN)")

    for item in items:
        if "e2e" in item.keywords:
            item.add_marker(skip_e2e)
        elif "integration" in item.keywords:
            item.add_marker(skip_integration)
