"""Reasoning module: evaluates candidate compatibility against a vacancy."""

from __future__ import annotations

from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from utils import normalize_text, unique


class CandidateAnalyzer:
    """Combines semantic text similarity, required skills and experience."""

    SIMILARITY_WEIGHT = 0.45
    SKILLS_WEIGHT = 0.40
    EXPERIENCE_WEIGHT = 0.15

    def analyze(self, vacancy: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
        required_skills = unique(vacancy["required_skills"])
        matched, missing = self._compare_skills(required_skills, profile["skills"], profile["raw_text"])
        skill_score = len(matched) / len(required_skills) if required_skills else 1.0
        experience_score = self._experience_score(
            float(vacancy["required_experience"]), float(profile["experience_years"])
        )
        similarity = self._text_similarity(self._vacancy_text(vacancy), profile["raw_text"])
        score = 100 * (
            similarity * self.SIMILARITY_WEIGHT
            + skill_score * self.SKILLS_WEIGHT
            + experience_score * self.EXPERIENCE_WEIGHT
        )
        return {
            "score": round(score, 2),
            "similarity_score": round(similarity * 100, 2),
            "skill_score": round(skill_score * 100, 2),
            "experience_score": round(experience_score * 100, 2),
            "matched_skills": matched,
            "missing_skills": missing,
            "status": self.status_for_score(score),
            "selected": False,
        }

    @staticmethod
    def status_for_score(score: float) -> str:
        if score >= 70:
            return "RECOMENDADO"
        if score >= 45:
            return "EN EVALUACION"
        return "NO RECOMENDADO"

    @staticmethod
    def _vacancy_text(vacancy: dict[str, Any]) -> str:
        return " ".join(
            [
                vacancy["title"],
                vacancy["area"],
                vacancy["description"],
                vacancy["requirements"],
                " ".join(vacancy["required_skills"]),
            ]
        )

    @staticmethod
    def _compare_skills(
        required_skills: list[str], candidate_skills: list[str], raw_text: str
    ) -> tuple[list[str], list[str]]:
        haystack = normalize_text(" ".join(candidate_skills) + " " + raw_text)
        matched = [skill for skill in required_skills if normalize_text(skill) in haystack]
        missing = [skill for skill in required_skills if skill not in matched]
        return matched, missing

    @staticmethod
    def _experience_score(required: float, actual: float) -> float:
        if required <= 0:
            return 1.0
        return min(actual / required, 1.0)

    @staticmethod
    def _text_similarity(vacancy_text: str, cv_text: str) -> float:
        vectorizer = TfidfVectorizer(
            strip_accents="unicode",
            lowercase=True,
            ngram_range=(1, 2),
            stop_words=None,
        )
        try:
            matrix = vectorizer.fit_transform([vacancy_text, cv_text])
        except ValueError:
            return 0.0
        return float(cosine_similarity(matrix[0:1], matrix[1:2])[0][0])
