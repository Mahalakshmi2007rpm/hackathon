from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


def ensure_dir(path: Path) -> Path:
	path.mkdir(parents=True, exist_ok=True)
	return path


def slugify(value: str) -> str:
	cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower())
	cleaned = re.sub(r"-+", "-", cleaned).strip("-")
	return cleaned or "untitled"


def now_slug() -> str:
	return datetime.now().strftime("%Y%m%d-%H%M%S")


def save_json(path: Path, data: dict[str, Any]) -> None:
	path.write_text(json.dumps(data, indent=2), encoding="utf-8")
