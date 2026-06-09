from __future__ import annotations

from functools import lru_cache
from pathlib import Path


CONTEXT_DIR = Path(__file__).resolve().parent / "context"


@lru_cache(maxsize=16)
def load_context_template(name: str) -> str:
    path = CONTEXT_DIR / name
    if not path.is_file():
        raise FileNotFoundError(f"DOBBY context template not found: {path}")
    return path.read_text(encoding="utf-8").strip()
