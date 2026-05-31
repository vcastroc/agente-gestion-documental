"""Ranking helpers for candidate decisions."""


def rank_candidates(candidates: list[dict]) -> list[dict]:
    ranked = sorted(candidates, key=lambda item: (-float(item["score"]), item["name"]))
    for index, candidate in enumerate(ranked, 1):
        candidate["position"] = index
    return ranked
