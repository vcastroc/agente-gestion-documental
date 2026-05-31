"""Enhanced candidate compatibility analysis with weighted scoring."""

import json
import re


def analyze_profile(profile: dict, vacancy: dict) -> dict:
    """
    Analyze candidate profile against vacancy requirements.
    Uses weighted scoring system for more accurate matching.
    """
    required_skills = vacancy.get("skills", [])
    if isinstance(required_skills, str):
        try:
            required_skills = json.loads(required_skills)
        except:
            required_skills = []

    text = profile["raw_text"].lower()

    # Extract experience level from text
    experience_years = extract_experience_years(text)

    # Skill matching with weights
    matched_skills = []
    for skill in required_skills:
        if skill.lower() in text:
            matched_skills.append(skill)

    missing_skills = [s for s in required_skills if s not in matched_skills]

    # Calculate weighted score
    skill_score = (len(matched_skills) / max(len(required_skills), 1)) * 100
    experience_required = float(vacancy.get("experience", 0))

    # Adjust score based on experience match
    experience_score = min(100, (experience_years / max(experience_required, 1)) * 100)
    
    # Weight distribution: 70% skills, 30% experience
    weighted_score = round((skill_score * 0.7) + (experience_score * 0.3), 1)

    # Generate detailed feedback
    feedback = generate_feedback(profile, matched_skills, missing_skills, experience_years)

    # Determine status based on thresholds
    if weighted_score >= 80:
        status = "Preseleccionado"
    elif weighted_score >= 60:
        status = "En evaluación"
    else:
        status = "No recomendado"

    return {
        "score": weighted_score,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "experience_years": experience_years,
        "experience_required": experience_required,
        "status": status,
        "summary": f"{len(matched_skills)} de {len(required_skills)} habilidades. {experience_years}+ años de experiencia.",
        "feedback": feedback,
        "skill_score": skill_score,
        "experience_score": experience_score,
    }


def extract_experience_years(text: str) -> int:
    """Extract years of experience from CV text."""
    patterns = [
        r"(\d+)\s*(?:años|years?)\s*(?:de\s*)?(?:experiencia|experience)",
        r"(\d+)\s*(?:años|y)\s*de\s*(?:experiencia|exp)",
        r"(?:experiencia|experience).*?(\d+)\s*(?:años|years?)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1))

    return 0


def generate_feedback(profile: dict, matched: list, missing: list, exp_years: int) -> str:
    """Generate personalized feedback for the candidate."""
    feedback_parts = []

    if len(matched) >= len(missing) * 2:
        feedback_parts.append("✅ Excelente alineación con los requisitos técnicos.")
    elif len(matched) > 0:
        feedback_parts.append(f"✅ Cumples con {len(matched)} competencias clave.")
    else:
        feedback_parts.append("⚠️ Tu perfil necesita desarrollar las competencias técnicas.")

    if missing:
        skills_str = ", ".join(missing[:3])
        if len(missing) > 3:
            skills_str += f" y {len(missing) - 3} más"
        feedback_parts.append(f"📚 Considera desarrollar: {skills_str}.")

    if exp_years > 0:
        feedback_parts.append(f"💼 Experiencia identificada: {exp_years}+ años.")
    else:
        feedback_parts.append("📌 Añade información sobre tu experiencia laboral.")

    return " ".join(feedback_parts)
