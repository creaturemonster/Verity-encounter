"""Patient Encounter Performance Rubric.

The domain text is the faculty rubric. Scores use only transcript checks.
N/A means the case does not make that criterion observable. The total is a
discussion aid, not a pass/fail grade.
"""
from __future__ import annotations
import re
import unicodedata

RUBRIC = {
    'title': 'Patient Encounter Performance Rubric',
    'instructions': 'Rate the student’s performance as supported by the encounter. Rate only what the scenario makes possible to observe; use N/A when a criterion is not appropriate.',
    'rating_scale': [
        {'score': 4, 'label': 'Strong', 'meaning': 'Consistent, effective, appropriate'},
        {'score': 3, 'label': 'Competent', 'meaning': 'Usually effective; minor gaps'},
        {'score': 2, 'label': 'Developing', 'meaning': 'Partly effective; important gaps'},
        {'score': 1, 'label': 'Unsafe or absent', 'meaning': 'Not demonstrated, misleading, or harmful'},
    ],
    'allowed_scores': [4, 3, 2, 1, 'N/A'],
    'domains': [
        {
            'id': 1, 'key': 'opening_and_purpose', 'name': 'Opening and purpose',
            'triggers_review_if_score_1': False,
            'descriptors': {
                '4': 'Introduces self and role; establishes purpose and agenda; confirms the patient’s immediate concern; sets expectations.',
                '3': 'Opens clearly and establishes a workable focus.',
                '2': 'Opening is understandable but misses role, agenda, or patient priorities.',
                '1': 'Begins abruptly, creates confusion, or lacks a clinically appropriate purpose.',
            },
        },
        {
            'id': 2, 'key': 'rapport_respect_empathy', 'name': 'Rapport, respect, and empathy',
            'triggers_review_if_score_1': False,
            'descriptors': {
                '4': 'Uses attentive, nonjudgmental, culturally responsive language; acknowledges emotion and patient perspective; builds trust.',
                '3': 'Consistently respectful and responsive; patient appears heard.',
                '2': 'Generally respectful but responses feel formulaic, rushed, or insufficiently attuned.',
                '1': 'Dismissive, judgmental, confusing, or emotionally unsafe communication.',
            },
        },
        {
            'id': 3, 'key': 'information_gathering', 'name': 'Information gathering',
            'triggers_review_if_score_1': False,
            'descriptors': {
                '4': 'Uses open questions, focused follow-up, clarification, and appropriate sequencing; explores relevant history, context, risks, and goals.',
                '3': 'Gathers most relevant information with logical follow-up.',
                '2': 'Gathers some relevant information but is incomplete, disorganized, or overly leading.',
                '1': 'Misses essential information or cannot sustain a useful history.',
            },
        },
        {
            'id': 4, 'key': 'listening_and_response_to_cues', 'name': 'Listening and response to cues',
            'triggers_review_if_score_1': False,
            'descriptors': {
                '4': 'Recognizes verbal cues, uncertainty, concerns, questions, and changes in the patient’s story; avoids interrupting or ignoring information.',
                '3': 'Tracks the patient’s narrative and follows up appropriately.',
                '2': 'Responds to obvious cues but overlooks subtler concerns or inconsistencies.',
                '1': 'Ignores, contradicts, or prematurely redirects important information.',
            },
        },
        {
            'id': 5, 'key': 'explanation_and_shared_decisions', 'name': 'Explanation and shared decisions',
            'triggers_review_if_score_1': False,
            'descriptors': {
                '4': 'Explains findings or next steps clearly; checks understanding; invites questions; incorporates preferences and readiness when relevant.',
                '3': 'Provides clear, patient-centered explanations and checks understanding.',
                '2': 'Explanation is partly clear but uses jargon, gives limited rationale, or does not check understanding.',
                '1': 'Provides inaccurate, overly technical, coercive, or absent explanation when needed.',
            },
        },
        {
            'id': 6, 'key': 'clinical_reasoning_and_synthesis', 'name': 'Clinical reasoning and synthesis',
            'triggers_review_if_score_1': True,
            'descriptors': {
                '4': 'Identifies important findings; distinguishes relevant from irrelevant information; recognizes red flags or uncertainty; forms a plausible assessment or differential when appropriate.',
                '3': 'Reasoning is clinically coherent and appropriately cautious.',
                '2': 'Recognizes some key findings but misses connections, alternatives, or uncertainty.',
                '1': 'Reasoning is unsupported, unsafe, internally inconsistent, or absent when required.',
            },
        },
        {
            'id': 7, 'key': 'professionalism_safety_closure', 'name': 'Professionalism, safety, and closure',
            'triggers_review_if_score_1': True,
            'descriptors': {
                '4': 'Maintains boundaries; protects privacy; communicates limitations; summarizes; confirms next steps, follow-up, or escalation when relevant.',
                '3': 'Professional and safe throughout; closes with a clear shared plan.',
                '2': 'Mostly professional but closure, limitations, or safety-netting is incomplete.',
                '1': 'Creates safety risk, overstates certainty, breaches boundaries, or ends without an appropriate plan.',
            },
        },
    ],
    'scoring': {
        'max_total': 28,
        'interpretation': 'Use the total as a discussion aid, not a pass/fail grade. A score of 1 in professionalism, safety, or clinical reasoning should trigger review even when the total is high.',
        'review_trigger_domain_ids': [6, 7],
    },
    'evidence_fields': [
        'strength_demonstrated',
        'important_gap_or_missed_opportunity',
        'safety_or_accuracy_concern',
    ],
}

_LABELS = {item['score']: item['label'] for item in RUBRIC['rating_scale']}
_PURPOSE = re.compile(r"\b(purpose of|reason for (?:this|our)|agenda|what i(?:'d| would) like to (?:cover|talk about)|plan for (?:this|our) (?:visit|conversation))\b", re.I)
_EXPECT = re.compile(r"\b(what to expect|this (?:visit|conversation) will|before we finish|i will ask|we will talk)\b", re.I)
_JUDGMENT = re.compile(r"\b(noncompliant|junkie|addict|lazy|stupid|disgusting|you people|just calm down|whatever)\b", re.I)
_CLARIFY = re.compile(r"\b(what do you mean|can you clarify|tell me more about|help me understand|say more about)\b", re.I)
_INVITE = re.compile(r"\b(what questions|any questions|questions do you have|questions for me)\b", re.I)
_PREFER = re.compile(r"\b(what (?:would you|do you) prefer|what matters to you|your goal|hoping for|ready to)\b", re.I)
_EXPLAIN = re.compile(r"\b(this means|the reason|because|so that you|in other words|next step)\b", re.I)
_UNCERTAIN = re.compile(r"\b(i(?:'m| am) not (?:sure|certain)|we (?:don't|do not) know|it (?:might|could|may) be|possible that|uncertain)\b", re.I)
_LIMITS = re.compile(r"\b(i(?:'m| am) a student|i can(?:not|'t) diagnose|i(?:'m| am) not able to diagnose|limitation of)\b", re.I)
_NEXT = re.compile(r"\b(next step|follow[- ]up|come back|plan is|we should)\b", re.I)
_UNSAFE = re.compile(r"\b(you (?:definitely|certainly) have|it is definitely|i(?:'m| am) sure you have)\b", re.I)
_CONTRADICT = re.compile(r"\b(that(?:'s| is) not true|you(?:'re| are) wrong|stop saying|you did not say)\b", re.I)
_CULTURE = re.compile(r"\b(race|ethnicity|culture|cultural|heritage|background)\b", re.I)
_STOP = set('about after again also been before could does from have here just like more some that their them then there these they this those what when where which while with would your'.split())


def _text(value: str) -> str:
    return unicodedata.normalize('NFKC', value or '').replace('’', "'")


def _learner(state: dict) -> list[dict]:
    return [m for m in state.get('messages', []) if m.get('role') == 'learner']


def _hit(pattern, turns: list[dict]):
    for message in turns:
        match = pattern.search(_text(message.get('text', '')))
        if match:
            return {'turn': message.get('turn'), 'quote': match.group(0), 'message': message.get('text', '')}
    return None


def _has(state, key: str) -> bool:
    return key in (state.get('signals') or {})


def _signal(state, key: str):
    item = (state.get('signals') or {}).get(key)
    if not item:
        return None
    return {'turn': item.get('turn'), 'quote': item.get('quote'), 'message': item.get('message')}


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z']{5,}", _text(text).lower()) if w not in _STOP}


def _followups(state: dict) -> int:
    previous = ''
    count = 0
    for message in state.get('messages', []):
        if message.get('role') in ('patient', 'record'):
            previous = message.get('text', '')
        elif message.get('role') == 'learner' and previous:
            if _words(previous) & _words(message.get('text', '')):
                count += 1
    return count


def _case_needs_explanation(case: dict) -> bool:
    for obj in case.get('objectives', []):
        if obj.get('signal') == 'teach_back':
            return True
        title = (obj.get('title') or '').lower()
        if any(word in title for word in ('explain', 'understanding', 'teach')):
            return True
    return False


def _case_needs_reasoning(case: dict) -> bool:
    for obj in case.get('objectives', []):
        if obj.get('signal') == 'summary':
            return True
        title = (obj.get('title') or '').lower()
        if any(word in title for word in ('assess', 'differential', 'synthes', 'reason')):
            return True
    return False


def _has_identity(case: dict) -> bool:
    return any(f.get('id') == 'identity' or f.get('group') == 'Identity' for f in case.get('facts', []))


def _row(domain: dict, score, quote, rationale: str) -> dict:
    applicable = score != 'N/A'
    return {
        'id': domain['id'], 'key': domain['key'], 'name': domain['name'],
        'score': score,
        'label': _LABELS[score] if applicable else 'Not applicable',
        'descriptor': domain['descriptors'][str(score)] if applicable else 'Not appropriate for this scenario. Rate only what the encounter makes possible to observe.',
        'descriptors': domain['descriptors'],
        'triggers_review_if_score_1': domain['triggers_review_if_score_1'],
        'review_triggered': bool(domain['triggers_review_if_score_1'] and score == 1),
        'evidence_quote': quote,
        'rationale': rationale,
    }


def _opening(state, turns) -> tuple:
    if not turns:
        return 1, None, 'No learner turn established a purpose.'
    intro, opened, permission = _signal(state, 'introduction'), _signal(state, 'open_question'), _signal(state, 'permission')
    purpose, expectations = _hit(_PURPOSE, turns), _hit(_EXPECT, turns)
    if intro and opened and (purpose or expectations):
        quote = purpose or expectations or intro
        return 4, quote, 'Introduction, an open invitation, and a purpose or expectation were each observed.'
    if intro or (opened and (permission or purpose)):
        return 3, intro or opened or permission, 'The opening establishes a focus and misses at least one of role, agenda, or expectations.'
    return 2, {'turn': turns[0]['turn'], 'quote': turns[0]['text'][:160], 'message': turns[0]['text']}, 'The learner spoke, without a role introduction and an open invitation.'


def _rapport(case, state, turns) -> tuple:
    judgment = _hit(_JUDGMENT, turns)
    if judgment:
        return 1, judgment, 'Judgmental wording was observed.'
    if not turns:
        return 1, None, 'No respectful or empathic response was observed.'
    empathy = _signal(state, 'empathy')
    culture_needed = _has_identity(case)
    culture = _hit(_CULTURE, turns)
    if empathy and (not culture_needed or culture):
        return 4, empathy, 'An acknowledgment was observed, and the wording checked was not judgmental.'
    if empathy or _followups(state):
        return 3, empathy, 'The learner responded to the patient without a full acknowledgment of emotion.'
    return 2, {'turn': turns[0]['turn'], 'quote': turns[0]['text'][:160], 'message': turns[0]['text']}, 'Questions stayed respectful, without an observed acknowledgment.'


def _gathering(case, state, turns) -> tuple:
    elicitable = [f['id'] for f in case.get('facts', []) if f.get('disclosure') in ('ask', 'record')]
    elicited = [fid for fid in elicitable if fid in state.get('elicited', {})]
    ratio = len(elicited) / len(elicitable) if elicitable else 0
    if ratio >= 0.75 and _has(state, 'open_question') and (_hit(_CLARIFY, turns) or len(elicited) > 1):
        return 4, _signal(state, 'open_question'), f'{len(elicited)} of {len(elicitable)} elicitable facts were disclosed, with an open question and follow-up.'
    if ratio >= 0.5:
        return 3, None, f'{len(elicited)} of {len(elicitable)} elicitable facts were disclosed.'
    if elicited:
        return 2, None, f'{len(elicited)} of {len(elicitable)} elicitable facts were disclosed.'
    return 1, None, 'No elicitable history or record was disclosed.'


def _listening(state, turns) -> tuple:
    contradict = _hit(_CONTRADICT, turns)
    if contradict:
        return 1, contradict, 'The learner contradicted the patient.'
    followed = _followups(state)
    if not turns:
        return 1, None, 'No learner turn responded to the patient.'
    if followed >= 2:
        return 4, None, f'{followed} questions used words from the preceding patient or record statement.'
    if followed or _signal(state, 'empathy'):
        return 3, _signal(state, 'empathy'), 'At least one response tracked the prior statement or acknowledged emotion.'
    return 2, {'turn': turns[0]['turn'], 'quote': turns[0]['text'][:160], 'message': turns[0]['text']}, 'Questions did not take up words from the preceding patient statement.'


def _explanation(case, state, turns) -> tuple:
    needed = _case_needs_explanation(case)
    unsafe = _hit(_UNSAFE, turns)
    if unsafe:
        return 1, unsafe, 'A statement of certainty was not supported by the approved case.'
    explained = _hit(_EXPLAIN, turns)
    checked = _signal(state, 'teach_back')
    invited = _hit(_INVITE, turns) or _hit(_PREFER, turns)
    if checked and explained and invited:
        return 4, checked, 'An explanation, a teach-back, and an invitation or preference check were observed.'
    if checked and (explained or _signal(state, 'summary')):
        return 3, checked, 'Understanding was checked after an explanation or summary.'
    if explained or checked:
        return 2, explained or checked, 'An explanation or teach-back was partial.'
    if needed:
        return 1, None, 'This case asks for an explanation or teach-back, and none was observed.'
    return 'N/A', None, 'This case does not ask the learner to explain a finding or check understanding.'


def _reasoning(case, state, turns) -> tuple:
    unsafe = _hit(_UNSAFE, turns)
    if unsafe:
        return 1, unsafe, 'Certainty was stated beyond the approved case.'
    if not _case_needs_reasoning(case):
        return 'N/A', None, 'This case does not ask for an assessment, differential, or summary.'
    summary = _signal(state, 'summary')
    uncertain = _hit(_UNCERTAIN, turns)
    if summary and uncertain:
        return 4, summary or uncertain, 'A summary named uncertainty instead of an unsupported conclusion.'
    if summary:
        return 3, summary, 'A summary was observed without an explicit statement of uncertainty.'
    if state.get('elicited'):
        return 2, None, 'Findings were elicited, without a summary that connects them.'
    return 1, None, 'This case asks for synthesis, and none was observed.'


def _closure(state, turns) -> tuple:
    unsafe = _hit(_UNSAFE, turns)
    if state.get('blocked_queries'):
        quote = state['blocked_queries'][0]
        return 1, {'turn': quote.get('turn'), 'quote': quote.get('text', '')[:160], 'message': quote.get('text', '')}, 'A boundary breach was blocked.'
    if unsafe:
        return 1, unsafe, 'Certainty was overstated.'
    if _hit(_CONTRADICT, turns):
        return 1, _hit(_CONTRADICT, turns), 'The learner contradicted the patient.'
    if not turns:
        return 1, None, 'The encounter ended without a plan.'
    summary, limits, nxt = _signal(state, 'summary'), _hit(_LIMITS, turns), _hit(_NEXT, turns)
    intro = _signal(state, 'introduction')
    student = bool(intro and re.search(r'\bstudent\b', intro.get('message') or '', re.I))
    if summary and (limits or student) and nxt:
        return 4, summary, 'A summary, a stated limitation or student role, and a next step were observed.'
    if summary or nxt:
        return 3, summary or nxt, 'A summary or next step was observed.'
    return 2, {'turn': turns[-1]['turn'], 'quote': turns[-1]['text'][:160], 'message': turns[-1]['text']}, 'No summary or next step was observed.'


def performance_review(case: dict, state: dict) -> dict:
    turns = _learner(state)
    scored = [
        _opening(state, turns),
        _rapport(case, state, turns),
        _gathering(case, state, turns),
        _listening(state, turns),
        _explanation(case, state, turns),
        _reasoning(case, state, turns),
        _closure(state, turns),
    ]
    domains = [_row(spec, score, quote, why) for spec, (score, quote, why) in zip(RUBRIC['domains'], scored)]
    numeric = [item for item in domains if item['score'] != 'N/A']
    best = max(numeric, key=lambda item: item['score'])
    worst = min(numeric, key=lambda item: item['score'])
    triggered = [item for item in domains if item['review_triggered']]
    if best['score'] == 1:
        strength = 'No domain scored above Unsafe or absent.'
    else:
        strength = f"{best['name']}: {best['label']}. {best['rationale']}"
    safety = ' '.join(f"{item['name']}: {item['rationale']}" for item in triggered) or 'None observed in the transcript.'
    return {
        'title': RUBRIC['title'],
        'instructions': RUBRIC['instructions'],
        'rating_scale': RUBRIC['rating_scale'],
        'domains': domains,
        'total': sum(item['score'] for item in numeric),
        'applicable_max': 4 * len(numeric),
        'max_total': RUBRIC['scoring']['max_total'],
        'na_count': len(domains) - len(numeric),
        'interpretation': RUBRIC['scoring']['interpretation'],
        'review_required': bool(triggered),
        'review_reason': safety if triggered else '',
        'evidence': {
            'strength_demonstrated': strength,
            'important_gap_or_missed_opportunity': f"{worst['name']}: {worst['label']}. {worst['rationale']}",
            'safety_or_accuracy_concern': safety,
        },
        'limitation': 'Transcript checks apply the faculty rubric. The total is a discussion aid, not a pass/fail grade. Tone, nonverbal communication, and clinical correctness are not measured.',
    }
