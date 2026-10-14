from pathlib import Path

import yaml

LOCAL_CONFIG_NAME = "config.local.yaml"


def merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(path: str | Path = "config.yaml") -> dict:
    path = Path(path)
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    local = path.with_name(LOCAL_CONFIG_NAME)
    if local.exists():
        config = merge(config, yaml.safe_load(local.read_text(encoding="utf-8")) or {})
    return config
