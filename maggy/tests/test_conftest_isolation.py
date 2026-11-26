"""The suite must not see the developer's or CI runner's real config dirs."""

from __future__ import annotations

import os

import pytest

XDG_VARS = ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME")


@pytest.mark.parametrize("name", XDG_VARS)
def test_xdg_base_dirs_are_cleared(name: str) -> None:
    assert name not in os.environ
