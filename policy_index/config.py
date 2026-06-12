from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .paths import CONFIG_DIR


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_policy_sources() -> dict[str, Any]:
    return load_yaml(CONFIG_DIR / "policy_sources.yaml")


def load_industry_taxonomy() -> dict[str, Any]:
    return load_yaml(CONFIG_DIR / "industry_taxonomy.yaml")


def load_support_channels() -> dict[str, Any]:
    return load_yaml(CONFIG_DIR / "support_channels.yaml")


def load_scoring_weights() -> dict[str, Any]:
    return load_yaml(CONFIG_DIR / "scoring_weights.yaml")
