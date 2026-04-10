"""Small environment configuration helpers for app startup."""

from __future__ import annotations

import os
from pathlib import Path


def load_env_file(env_path: str = ".env") -> bool:
    """Load environment variables from the first available .env candidate."""

    candidates = _env_candidates(env_path)
    loaded_any = False

    for env_file in candidates:
        if not env_file.exists():
            continue

        try:
            from dotenv import load_dotenv
        except ImportError:
            loaded_any = _load_env_file_fallback(env_file) or loaded_any
        else:
            loaded_any = bool(load_dotenv(dotenv_path=env_file, override=False)) or loaded_any

    return loaded_any


def _env_candidates(env_path: str) -> list[Path]:
    explicit_path = Path(env_path)
    if explicit_path.name != ".env":
        return [explicit_path]

    return [
        Path(".env"),
        Path("engine/.env"),
    ]


def _load_env_file_fallback(env_file: Path) -> bool:
    loaded_any = False
    for raw_line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if not key:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]

        os.environ.setdefault(key, value)
        loaded_any = True

    return loaded_any


__all__ = ["load_env_file"]
