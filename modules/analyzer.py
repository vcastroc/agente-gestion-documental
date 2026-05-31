from typing import Dict, List, Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def calculate_skill_match(candidate_skills: List[str], required_skills: List[str]) -> float:
    """Return the percentage of required skills found in the candidate skills list."""
    candidate_set = {skill.lower() for skill in candidate_skills}
    required_set = {skill.lower() for skill in required_skills}
    if not required_set:
        return 0.0

    matched = len(candidate_set & required_set)
    return round(matched / len(required_set) * 100, 2)


def calculate_compatibility(cv_text: str, vacancy_text: str) -> float:
    """Calculate TF-IDF cosine similarity between CV text and vacancy text."""
    if not cv_text or not vacancy_text:
        return 0.0

    vectorizer = TfidfVectorizer(
        stop_words='spanish',
        ngram_range=(1, 2),
        max_df=0.85,
    )
    matrix = vectorizer.fit_transform([cv_text, vacancy_text])
    similarity = cosine_similarity(matrix[0], matrix[1])[0][0]
    return round(float(similarity) * 100, 2)


def calculate_keyword_overlap(cv_keywords: List[str], job_keywords: List[str]) -> float:
    """Return the percentage of vacancy keywords covered by the CV keywords."""
    if not cv_keywords or not job_keywords:
        return 0.0

    cv_set = {k.lower() for k in cv_keywords}
    job_set = {k.lower() for k in job_keywords}
    if not job_set:
        return 0.0

    matched = len(cv_set & job_set)
    return round(matched / len(job_set) * 100, 2)


def analyze_cv_vs_job(cv_data: Dict[str, Any], job_data: Dict[str, Any]) -> Dict[str, Any]:
    """Return a basic analysis dict combining CV and job data."""
    cv_skills = cv_data.get('skills', [])
    job_skills = job_data.get('requirements', {}).get('required_skills', [])
    cv_text = cv_data.get('raw_text', '')
    job_text = job_data.get('raw_text', '')

    skill_score = calculate_skill_match(cv_skills, job_skills)
    text_score = calculate_compatibility(cv_text, job_text)
    cv_keywords = cv_data.get('keywords', [])
    job_keywords = job_data.get('keywords', [])
    keyword_score = calculate_keyword_overlap(cv_keywords, job_keywords)

    if job_skills and job_keywords:
        overall = round(skill_score * 0.4 + keyword_score * 0.3 + text_score * 0.3, 2)
    elif job_keywords:
        overall = round(keyword_score * 0.5 + text_score * 0.5, 2)
    else:
        overall = round(text_score, 2)

    job_skills_lower = {s.lower() for s in job_skills}
    cv_skills_lower = {s.lower() for s in cv_skills}

    return {
        'candidate_name': cv_data.get('personal_info', {}).get('name', ''),
        'skill_score': skill_score,
        'keyword_score': keyword_score,
        'text_score': text_score,
        'overall_score': overall,
        'matched_skills': [skill for skill in cv_skills if skill.lower() in job_skills_lower],
        'missing_skills': [skill for skill in job_skills if skill.lower() not in cv_skills_lower],
    }
