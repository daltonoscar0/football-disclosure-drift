"""Small shared helpers. Everything here exists to keep outputs deterministic."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SEED = 20260804


def jdump(obj, path: Path, *, indent: int = 2) -> None:
    """Write JSON with stable key ordering and a trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=indent, sort_keys=True, ensure_ascii=False) + "\n"
    )


def jload(path: Path):
    return json.loads(Path(path).read_text())


def club_years(parsed_dir: Path) -> list[tuple[str, str]]:
    """Every (club, year) pair with a parsed filing, in sorted order."""
    pairs = []
    for club_dir in sorted(p for p in parsed_dir.iterdir() if p.is_dir()):
        for f in sorted(club_dir.glob("*.json")):
            pairs.append((club_dir.name, f.stem))
    return pairs
