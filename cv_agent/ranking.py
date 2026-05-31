"""Decision module: builds rankings and applies automatic selection."""

from __future__ import annotations

from typing import Any


def rank_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(candidates, key=lambda item: (-item["score"], item["name"].lower()))
    for position, candidate in enumerate(ranked, start=1):
        candidate["position"] = position
    return ranked


def select_top_candidates(
    candidates: list[dict[str, Any]], limit: int = 3
) -> list[dict[str, Any]]:
    ranked = rank_candidates(candidates)
    selected_ids = {candidate["id"] for candidate in ranked[:limit]}
    for candidate in ranked:
        candidate["selected"] = candidate["id"] in selected_ids
        if candidate["selected"]:
            candidate["status"] = "PRESELECCIONADO"
    return ranked
