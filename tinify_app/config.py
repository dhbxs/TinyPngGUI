from __future__ import annotations

import json
from pathlib import Path
from typing import Any


APP_NAME = "TinifyCompress"
CONFIG_DIR = Path.home() / "AppData" / "Roaming" / APP_NAME
CONFIG_PATH = CONFIG_DIR / "config.json"

DEFAULTS: dict[str, Any] = {
    "api_key": "",
    "output_mode": "suffix",  # suffix | overwrite | custom
    "output_dir": "",
    "suffix": "_tinified",
    "overwrite_confirm": True,
}


def load_config() -> dict[str, Any]:
    data = dict(DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data.update({k: loaded[k] for k in DEFAULTS if k in loaded})
        except (OSError, json.JSONDecodeError):
            pass
    return data


def save_config(config: dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    payload = {k: config.get(k, DEFAULTS[k]) for k in DEFAULTS}
    CONFIG_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
