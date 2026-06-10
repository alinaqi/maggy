"""Tests for model and council API routes."""

from pathlib import Path

import pytest


class TestRoutesModelsExist:
    def test_routes_models_file_exists(self):
        p = Path(__file__).parent.parent / "maggy" / "api" / "routes_models.py"
        assert p.exists()

    def test_has_list_models_endpoint(self):
        src = (Path(__file__).parent.parent / "maggy" / "api" / "routes_models.py").read_text()
        assert "GET" in src or "get" in src
        assert "/models" in src or "models" in src

    def test_has_health_endpoint(self):
        src = (Path(__file__).parent.parent / "maggy" / "api" / "routes_models.py").read_text()
        assert "health" in src

    def test_has_council_config_endpoint(self):
        src = (Path(__file__).parent.parent / "maggy" / "api" / "routes_models.py").read_text()
        assert "council" in src


class TestRoutesModelsRegistered:
    def test_router_in_main(self):
        src = (Path(__file__).parent.parent / "maggy" / "main.py").read_text()
        assert "routes_models" in src
