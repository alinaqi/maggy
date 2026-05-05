"""Identity broker — credential resolution (spec §7).

Resolves named identities to volume mounts and env overlays
for container provisioning.
"""

from __future__ import annotations

from .models import Identity


def resolve_identity(
    name: str,
    identities: list[Identity],
) -> Identity:
    """Find identity by name. Raises KeyError if missing."""
    for identity in identities:
        if identity.name == name:
            return identity
    raise KeyError(name)


def build_volume_mounts(
    identity: Identity,
    agent_type: str,
) -> list[str]:
    """Build Docker -v mount strings for an agent type."""
    path = identity.volumes.get(agent_type)
    if path is None:
        return []
    return [f"{path}:/home/worker/{path}:ro"]


def build_env_overlay(identity: Identity) -> dict[str, str]:
    """Build env vars from identity api_keys.

    api_keys maps logical name -> env var name.
    Returns {env_var_name: env_var_name} for docker --env pass-through.
    """
    if not identity.api_keys:
        return {}
    return {v: v for v in identity.api_keys.values()}


def validate_identity(identity: Identity) -> list[str]:
    """Return list of validation errors (empty = valid)."""
    errors: list[str] = []
    if not identity.name:
        errors.append("name is required")
    if not identity.volumes:
        errors.append("At least one volume is required")
    return errors
