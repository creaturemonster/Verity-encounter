"""Teaching topics taken from the faculty sample courses.

Rows name the topic and the course. They do not copy the patient's approved
answer, so the knowledge table cannot reveal an unelicited fact.
"""
from __future__ import annotations
import hashlib
from .engine import normalize
from .faculty_samples import cases

STOP = {
    'what', 'when', 'where', 'which', 'that', 'this', 'with', 'from', 'have', 'does',
    'your', 'about', 'tell', 'more', 'been', 'they', 'them', 'were', 'their', 'into',
    'would', 'could', 'should', 'please', 'the', 'and', 'for', 'you', 'any', 'can',
    'how', 'who', 'are', 'was', 'not', 'but', 'his', 'her', 'she', 'him',
}


def _terms(fact: dict) -> list[str]:
    found, seen = [], set()
    sources = [fact.get('label') or '', *(fact.get('aliases') or [])]
    for source in sources:
        phrase = normalize(source)
        if phrase and phrase not in seen and phrase not in STOP:
            seen.add(phrase)
            found.append(phrase)
        for word in phrase.split():
            if len(word) >= 3 and word not in STOP and word not in seen:
                seen.add(word)
                found.append(word)
    return found[:40]


def _row_id(title: str, fact_id: str) -> str:
    prefix = hashlib.sha256(title.encode()).hexdigest()[:10]
    return f'course_{prefix}_{fact_id}'[:50]


def course_knowledge_rows() -> list[dict]:
    rows = []
    for case in cases():
        title = case.get('title') or 'Sample course'
        setting = case.get('setting') or 'Interview'
        for fact in case.get('facts') or []:
            if fact.get('disclosure') not in ('ask', 'record'):
                continue
            topic = fact.get('label') or fact.get('id') or 'Topic'
            rows.append({
                'id': _row_id(title, fact.get('id') or 'topic'),
                'case_title': title,
                'topic': topic,
                'summary': (
                    f'Sample course topic: {topic}. From “{title}” ({setting}). '
                    'This orients the clinician. It is not the patient’s spoken answer and not a published study.'
                )[:500],
                'terms': _terms(fact),
                'kind': 'Sample course',
            })
    return rows
