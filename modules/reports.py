"""CSV report generation for the recruiting dashboard."""

from __future__ import annotations

import csv
from pathlib import Path


def generate_candidates_csv(candidates: list[dict], destination: str | Path) -> Path:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Posición", "Candidato", "Cargo", "Compatibilidad", "Estado", "Correo"])
        for index, candidate in enumerate(candidates, 1):
            writer.writerow([index, candidate["name"], candidate["title"], candidate["score"], candidate["status"], candidate["email"]])
    return path
