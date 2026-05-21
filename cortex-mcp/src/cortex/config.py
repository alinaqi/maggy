"""Cortex configuration model."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field


class CortexConfig(BaseModel):
    max_db_size_mb: int = Field(default=500, ge=50, le=10000)
    max_file_size_kb: int = Field(default=500, ge=10, le=10000)
    eviction_threshold: float = Field(default=0.05, ge=0.0, le=1.0)
    checkpoint_retention: int = Field(default=10, ge=1, le=100)
    signals_max_entries: int = Field(default=10000, ge=100)
    pinned_patterns: list[str] = Field(
        default_factory=lambda: ['**/main.*', '**/app.*', '**/config.*']
    )
    ignored_patterns: list[str] = Field(
        default_factory=lambda: ['node_modules', 'dist', '.next', '*.lock']
    )

    @classmethod
    def load(cls, project_dir: Path) -> CortexConfig:
        config_path = project_dir / '.cortex' / 'config.json'
        if config_path.exists():
            data = json.loads(config_path.read_text(encoding='utf-8'))
            return cls.model_validate(data)
        return cls()

    def save(self, project_dir: Path) -> None:
        config_dir = project_dir / '.cortex'
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / 'config.json'
        config_path.write_text(
            self.model_dump_json(indent=2),
            encoding='utf-8',
        )
