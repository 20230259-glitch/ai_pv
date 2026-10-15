from ai.embedding import create_embedding
from sklearn.metrics.pairwise import cosine_similarity


def calculate_text_similarity(text1, text2):
    """
    Tính độ tương đồng semantic giữa CV và JD.

    Kết quả:
        0 -> 100
    """

    if not text1 or not text2:
        return 0.0

    vector1 = create_embedding(text1)
    vector2 = create_embedding(text2)

    if vector1 is None or vector2 is None:
        return 0.0

    score = cosine_similarity(
        [vector1],
        [vector2]
    )[0][0]

    score = max(0.0, min(1.0, float(score)))

    return round(score * 100, 2)


def match_cv_jd(cv_text, jd_text):
    """
    Semantic Matching giữa toàn bộ CV và JD.
    """

    score = calculate_text_similarity(
        cv_text,
        jd_text
    )

    return {
        "matching_score": score,
        "cv_text": cv_text,
        "jd_text": jd_text
    }


def calculate_skill_matching(cv_skills, jd_skills):
    """
    So sánh skill sau khi đã được standardize.

    Matched Skills:
        CV ∩ JD

    Skill Gaps:
        JD - CV
    """

    cv_set = {
        skill.strip()
        for skill in (cv_skills or [])
        if skill and skill.strip()
    }

    jd_set = {
        skill.strip()
        for skill in (jd_skills or [])
        if skill and skill.strip()
    }

    matched_skills = [
        skill for skill in jd_skills
        if skill in cv_set
    ]

    skill_gaps = [
        skill for skill in jd_skills
        if skill not in cv_set
    ]

    return {
        "matched_skills": matched_skills,
        "skill_gaps": skill_gaps
    }