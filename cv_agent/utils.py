"""Shared utilities for text normalization and file handling."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Iterable


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.lower())
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", value).strip()


def unique(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        cleaned = item.strip()
        key = normalize_text(cleaned)
        if cleaned and key not in seen:
            seen.add(key)
            output.append(cleaned)
    return output


def split_items(value: str) -> list[str]:
    return unique(re.split(r"[,;\n|]+", value))


def safe_filename(filename: str) -> str:
    name = Path(filename).name
    return re.sub(r"[^A-Za-z0-9._-]", "_", name)
