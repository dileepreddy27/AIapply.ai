from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import Profile


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing config file: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"YAML must be a mapping: {path}")
    return data


def load_profile(path: Path) -> Profile:
    raw = read_yaml(path)
    return Profile.from_dict(raw)
