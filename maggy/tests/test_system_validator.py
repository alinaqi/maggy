"""Tests for local system validator — hardware detection + model suggestions."""

from __future__ import annotations

from unittest.mock import patch

import pytest


class TestDetectHardware:
    def test_returns_ram_gb(self):
        from maggy.services.system_validator import detect_hardware
        hw = detect_hardware()
        assert "ram_gb" in hw
        assert isinstance(hw["ram_gb"], (int, float))
        assert hw["ram_gb"] > 0

    def test_returns_cpu_cores(self):
        from maggy.services.system_validator import detect_hardware
        hw = detect_hardware()
        assert "cpu_cores" in hw
        assert hw["cpu_cores"] > 0

    def test_returns_disk_free_gb(self):
        from maggy.services.system_validator import detect_hardware
        hw = detect_hardware()
        assert "disk_free_gb" in hw
        assert hw["disk_free_gb"] >= 0

    def test_returns_gpu_info(self):
        from maggy.services.system_validator import detect_hardware
        hw = detect_hardware()
        assert "gpu" in hw
        assert "type" in hw["gpu"]

    def test_returns_platform(self):
        from maggy.services.system_validator import detect_hardware
        hw = detect_hardware()
        assert "platform" in hw


class TestModelRequirements:
    def test_has_known_models(self):
        from maggy.services.system_validator import LOCAL_MODELS
        names = [m["id"] for m in LOCAL_MODELS]
        assert "qwen3-0.6b" in names
        assert "qwen3-32b" in names

    def test_each_model_has_ram_requirement(self):
        from maggy.services.system_validator import LOCAL_MODELS
        for m in LOCAL_MODELS:
            assert "min_ram_gb" in m, f"{m['id']} missing min_ram_gb"
            assert m["min_ram_gb"] > 0


class TestSuggestModels:
    def test_low_ram_gets_small_models(self):
        from maggy.services.system_validator import suggest_local_models
        hw = {"ram_gb": 4, "disk_free_gb": 20, "gpu": {"type": "none"}}
        suggestions = suggest_local_models(hw)
        ids = [s["id"] for s in suggestions]
        assert "qwen3-0.6b" in ids
        assert "qwen3-32b" not in ids

    def test_high_ram_gets_large_models(self):
        from maggy.services.system_validator import suggest_local_models
        hw = {"ram_gb": 64, "disk_free_gb": 100, "gpu": {"type": "metal", "vram_gb": 64}}
        suggestions = suggest_local_models(hw)
        ids = [s["id"] for s in suggestions]
        assert "qwen3-32b" in ids

    def test_suggestions_sorted_by_quality(self):
        from maggy.services.system_validator import suggest_local_models
        hw = {"ram_gb": 32, "disk_free_gb": 50, "gpu": {"type": "metal", "vram_gb": 32}}
        suggestions = suggest_local_models(hw)
        if len(suggestions) >= 2:
            qualities = [s.get("quality_rank", 0) for s in suggestions]
            assert qualities == sorted(qualities, reverse=True)

    def test_low_disk_filters_large(self):
        from maggy.services.system_validator import suggest_local_models
        hw = {"ram_gb": 64, "disk_free_gb": 2, "gpu": {"type": "metal", "vram_gb": 64}}
        suggestions = suggest_local_models(hw)
        for s in suggestions:
            assert s.get("disk_gb", 0) <= 2

    def test_returns_fit_status(self):
        from maggy.services.system_validator import suggest_local_models
        hw = {"ram_gb": 16, "disk_free_gb": 50, "gpu": {"type": "metal", "vram_gb": 16}}
        suggestions = suggest_local_models(hw)
        for s in suggestions:
            assert "fit" in s
            assert s["fit"] in ("comfortable", "tight", "too_large")
