"""Tests for Polyphony identity broker (§7)."""

import pytest
from polyphony.models import Identity
from polyphony.identity import (
    resolve_identity,
    build_volume_mounts,
    build_env_overlay,
    validate_identity,
)


@pytest.fixture
def identities():
    return [
        Identity(
            name="protaige",
            volumes={"claude": "~/.claude", "codex": "~/.codex"},
            api_keys={"anthropic": "ANTHROPIC_API_KEY"},
        ),
        Identity(
            name="personal",
            volumes={"kimi": "~/.kimi"},
        ),
    ]


class TestResolveIdentity:
    def test_finds_by_name(self, identities):
        found = resolve_identity("protaige", identities)
        assert found.name == "protaige"

    def test_missing_raises(self, identities):
        with pytest.raises(KeyError, match="unknown"):
            resolve_identity("unknown", identities)


class TestBuildVolumeMounts:
    def test_mounts_for_claude(self, identities):
        mounts = build_volume_mounts(identities[0], "claude")
        assert len(mounts) == 1
        assert "~/.claude" in mounts[0]
        assert ":ro" in mounts[0]

    def test_no_mount_for_missing_agent(self, identities):
        mounts = build_volume_mounts(identities[1], "claude")
        assert mounts == []


class TestBuildEnvOverlay:
    def test_env_from_api_keys(self, identities):
        env = build_env_overlay(identities[0])
        assert "ANTHROPIC_API_KEY" in env

    def test_empty_when_no_keys(self, identities):
        env = build_env_overlay(identities[1])
        assert env == {}


class TestValidateIdentity:
    def test_valid(self, identities):
        errors = validate_identity(identities[0])
        assert errors == []

    def test_missing_name(self):
        i = Identity(name="", volumes={"claude": "~/.claude"})
        errors = validate_identity(i)
        assert any("name" in e for e in errors)

    def test_missing_volumes(self):
        i = Identity(name="test", volumes={})
        errors = validate_identity(i)
        assert any("volume" in e.lower() for e in errors)
