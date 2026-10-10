"""Case-independent interview engine. Clinical text is never model-generated.

A router selects IDs; the engine controls disclosure and renders exact approved
answers. Routing accuracy and educational validity are separate from provenance.
"""
from __future__ import annotations
import copy
import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from typing import Callable

_FEELING = r"(?:difficult|frustrating|scary|hard|worrying|stressful|overwhelming)"
_DEGREE = r"(?:very |really |so )?"
SIGNALS = {
    'introduction': r"\b(my name is|i am (?:a |your )?(?:medical |nursing |healthcare )?student|i'm (?:a |your )?(?:medical |nursing |healthcare )?student)\b",
    'permission': r"\b(is it (?:okay|ok)|may i|would it be (?:okay|ok)|do i have your permission)\b",
    'open_question': r"\b(tell me (?:more|about)|what (?:brings|matters|concerns)|how has .+ affected|walk me through|describe (?:what|how))\b",
    'empathy': (
        r"\b(?:that sounds " + _DEGREE + _FEELING
        + r"|it sounds " + _DEGREE + _FEELING
        + r"|i can (?:see|hear|understand)"
        + r"|thank you for (?:sharing|telling)"
        + r"|i'm sorry|i am sorry|i hear you"
        + r"|i understand (?:that|how|why)(?:\s+\w+){0,8}\s+" + _DEGREE + _FEELING
        + r"|(?:that|this|it) (?:can be|must be|must feel|has been) " + _DEGREE + _FEELING
        + r")\b"
    ),
    'summary': r"\b(let me (?:summarize|check|make sure)|what i(?:'ve| have) heard|to summarize|have i understood)\b",
    'teach_back': r"\b(in your own words|tell me what you understand|tell me how you would explain)\b",
}
SIGNAL_LABELS = {
    'introduction': 'Introduction', 'permission': 'Permission to interview',
    'open_question': 'Open invitation', 'empathy': 'Acknowledgment of feelings',
    'summary': 'Summary / understanding check', 'teach_back': 'Teach-back invitation',
}
INJECTION = re.compile(r"\b(ignore (?:all |the |your |previous )*(?:instructions|rules|profile)|system prompt|developer message|reveal (?:all|the hidden|the diagnosis|the answer key)|give me (?:all|the hidden|the answer key)|pretend (?:that )?(?:your|you have)|change (?:your|the) (?:history|allergies|diagnosis)|you are now|act as (?:the )?(?:system|developer))\b", re.I)
NEGATED_SIGNAL = re.compile(r"\b(not sorry|don't care|do not care|not difficult|not scary|not frustrating|not stressful|not overwhelming|do not understand|don't understand)\b", re.I)
UNKNOWN = 'This detail is not specified in the approved case. No clinical answer has been inferred.'


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def normalize(text: str) -> str:
    text = unicodedata.normalize('NFKC', text).lower().replace('’', "'")
    return re.sub(r'\s+', ' ', re.sub(r"[^\w\s']", ' ', text)).strip()


def valid_text(value, maximum=4000) -> bool:
    return isinstance(value, str) and 0 < len(value.strip()) <= maximum


def validate_case(case: dict) -> list[str]:
    """Validate publishable structure, not clinical correctness."""
    errors = []
    if not isinstance(case, dict):
        return ['Case must be an object.']
    for key in ('title', 'setting', 'author'):
        if not valid_text(case.get(key), 200):
            errors.append(f'{key}: enter 1–200 characters.')
    if case.get('synthetic') is not True:
        errors.append('Only explicitly synthetic cases are supported.')
    patient = case.get('patient', {})
    if not isinstance(patient, dict):
        errors.append('patient: must be an object.')
        patient = {}
    if not valid_text(patient.get('name'), 100):
        errors.append('Patient name is required.')
    age = patient.get('age')
    if type(age) is not int or not 0 <= age <= 120:
        errors.append('Patient age must be an integer from 0 to 120.')
    facts = case.get('facts', [])
    objectives = case.get('objectives', [])
    if not isinstance(facts, list) or not 2 <= len(facts) <= 80:
        return errors + ['Provide 2–80 facts.']
    ids = set()
    initial = 0
    for i, fact in enumerate(facts):
        if not isinstance(fact, dict):
            errors.append(f'Fact {i + 1}: must be an object.'); continue
        fid = fact.get('id', '')
        if not isinstance(fid, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,49}', fid) or fid in ids:
            errors.append(f'Fact {i + 1}: ID must be valid and unique.')
        if isinstance(fid, str): ids.add(fid)
        for key in ('label', 'answer', 'group'):
            if not valid_text(fact.get(key), 2000 if key == 'answer' else 100):
                errors.append(f'Fact {i + 1}: {key} is required.')
        disclosure = fact.get('disclosure')
        if disclosure not in ('initial', 'ask', 'record', 'faculty_only'):
            errors.append(f'Fact {i + 1}: invalid disclosure rule.')
        if disclosure == 'initial': initial += 1
        if disclosure in ('ask', 'record'):
            aliases = fact.get('aliases')
            if not isinstance(aliases, list) or not aliases or len(aliases) > 30 or not all(valid_text(x, 120) and normalize(x) for x in aliases):
                errors.append(f'Fact {i + 1}: provide 1–30 question phrases.')
        if type(fact.get('requires_empathy', False)) is not bool:
            errors.append(f'Fact {i + 1}: empathy gate must be true/false.')
        deps = fact.get('requires', [])
        if not isinstance(deps, list) or not all(isinstance(x, str) for x in deps):
            errors.append(f'Fact {i + 1}: invalid prerequisites.')
        aids = fact.get('attachment_ids', [])
        if not isinstance(aids, list) or len(aids) > 8 or not all(isinstance(a, str) for a in aids):
            errors.append(f'Fact {i + 1}: invalid attachment list.')
    if initial != 1:
        errors.append('Use exactly one initial fact for the opening statement.')
    lookup = {f['id']: f for f in facts if isinstance(f, dict) and isinstance(f.get('id'), str)}
    for fact in lookup.values():
        for dep in fact.get('requires', []) if isinstance(fact.get('requires', []), list) else []:
            if not isinstance(dep, str) or dep not in lookup or dep == fact['id']:
                errors.append(f"{fact['id']}: prerequisite does not exist or refers to itself.")
            elif lookup[dep].get('disclosure') == 'faculty_only':
                errors.append(f"{fact['id']}: prerequisite is not accessible to learners.")
        if fact.get('disclosure') == 'initial' and (fact.get('requires') or fact.get('requires_empathy')):
            errors.append('Opening fact cannot be gated.')
    # Reject cycles: a cyclic gate could otherwise make objectives impossible.
    colors = {}
    def visit(fid):
        if colors.get(fid) == 1: return True
        if colors.get(fid) == 2: return False
        colors[fid] = 1
        deps = lookup.get(fid, {}).get('requires', [])
        if isinstance(deps, list):
            for dep in deps:
                if isinstance(dep, str) and dep in lookup and visit(dep): return True
        colors[fid] = 2
        return False
    if any(visit(fid) for fid in lookup):
        errors.append('Fact prerequisites contain a cycle.')
    if not isinstance(objectives, list) or not 1 <= len(objectives) <= 30:
        return errors + ['Provide 1–30 learning objectives.']
    oids = set()
    for i, obj in enumerate(objectives):
        if not isinstance(obj, dict):
            errors.append(f'Objective {i + 1}: must be an object.'); continue
        oid = obj.get('id')
        if not isinstance(oid, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,49}', oid) or oid in oids:
            errors.append(f'Objective {i + 1}: ID must be valid and unique.')
        if isinstance(oid, str): oids.add(oid)
        if not valid_text(obj.get('title'), 300): errors.append(f'Objective {i + 1}: title is required.')
        fids = obj.get('fact_ids', [])
        if not isinstance(fids, list) or not all(isinstance(x, str) and x in lookup for x in fids):
            errors.append(f'Objective {i + 1}: invalid fact references.')
            fids = []
        for fid in fids:
            if lookup[fid].get('disclosure') in ('initial', 'faculty_only'):
                errors.append(f'Objective {i + 1}: scored facts must be elicitable, not initial/faculty-only.')
        signal = obj.get('signal', '')
        if not isinstance(signal, str):
            errors.append(f'Objective {i + 1}: signal must be text.'); signal = ''
        if signal and signal not in SIGNALS: errors.append(f'Objective {i + 1}: invalid communication signal.')
        if not fids and not signal: errors.append(f'Objective {i + 1}: link facts or a communication signal.')
        if type(obj.get('weight', 1)) is not int or not 1 <= obj.get('weight', 1) <= 10:
            errors.append(f'Objective {i + 1}: weight must be 1–10.')
        if type(obj.get('critical', False)) is not bool:
            errors.append(f'Objective {i + 1}: critical must be true/false.')
    return errors


def signals_in(text: str) -> dict:
    n = unicodedata.normalize('NFKC', text).replace('’', "'")
    found = {}
    for key, pattern in SIGNALS.items():
        matches = list(re.finditer(pattern, n, re.I))
        if matches and not (key == 'empathy' and NEGATED_SIGNAL.search(n)):
            match = max(matches, key=lambda item: len(item.group(0)))
            found[key] = {'quote': match.group(0), 'message': text}
    return found


def rule_route(question: str, facts: list[dict]) -> list[str]:
    """Conservative whole-phrase matching; not semantic understanding."""
    q = ' ' + normalize(question) + ' '
    ranked, broad = [], []
    generic = {'tell me more','tell me about','what brings','walk me through'}
    broad_words = set('please can could would you tell me more about it this that your symptoms what brings in here today walk through happened experience feeling the problem how have been'.split())
    for index, fact in enumerate(facts):
        if fact['disclosure'] not in ('ask', 'record'): continue
        matches = [normalize(a) for a in fact.get('aliases', []) if normalize(a) and ' ' + normalize(a) + ' ' in q]
        specific = [m for m in matches if m not in generic]
        if specific:
            ranked.append((max(len(a.split()) * 10 + len(a) / 100 for a in specific), -index, fact['id']))
        elif matches and set(q.split()) <= broad_words:
            broad.append((1, -index, fact['id']))
    ranked = ranked or broad
    ranked.sort(reverse=True)
    return [r[2] for r in ranked[:2]]


def new_state(case: dict) -> dict:
    opening = next(f for f in case['facts'] if f['disclosure'] == 'initial')
    return {
        'status': 'active', 'turn': 0,
        'messages': [{'turn': 0, 'role': 'patient', 'text': opening['answer'], 'fact_ids': [opening['id']], 'source': 'approved-opening', 'at': now()}],
        'revealed': {opening['id']: 0}, 'elicited': {}, 'signals': {},
        'requests': {}, 'unknown_queries': [], 'blocked_queries': [],
        'router_modes': [], 'review': None, 'knowledge': [],
    }


def advance(case: dict, state: dict, question: str, router: Callable | None = None) -> dict:
    if state['status'] != 'active': raise ValueError('This encounter has ended.')
    if not valid_text(question, 1500): raise ValueError('Enter a question of 1–1500 characters.')
    state = copy.deepcopy(state)
    question = question.strip()
    turn = state['turn'] + 1
    state['turn'] = turn
    state['messages'].append({'turn': turn, 'role': 'learner', 'text': question, 'fact_ids': [], 'at': now()})
    if INJECTION.search(unicodedata.normalize('NFKC', question)):
        state['blocked_queries'].append({'turn': turn, 'text': question})
        state['messages'].append({'turn': turn, 'role': 'system', 'text': 'Case boundaries remain in force. Ask the patient a question; hidden facts and teaching notes are not available on request.', 'fact_ids': [], 'source': 'boundary', 'at': now()})
        return state
    observed = signals_in(question)
    for sig, detail in observed.items():
        state['signals'].setdefault(sig, {**detail, 'turn': turn})
    ids = rule_route(question, case['facts'])
    source = 'local-phrase-router'
    if router is not None:
        try:
            selected = router(question, case['facts'], state['messages'][-7:-1])
            valid = {f['id'] for f in case['facts'] if f['disclosure'] in ('ask', 'record')}
            if not isinstance(selected, list) or len(selected) > 2 or len(set(selected)) != len(selected) or not all(isinstance(x, str) and x in valid for x in selected):
                raise ValueError('Router selected invalid IDs.')
            ids = selected
            source = 'model-id-router'
        except Exception:
            # An unavailable or malformed provider cannot author a clinical answer.
            source = 'local-fallback'
    state['router_modes'].append(source)
    lookup = {f['id']: f for f in case['facts']}
    allowed, gated = [], []
    for fid in ids:
        fact = lookup[fid]
        if fact.get('requires_empathy') and 'empathy' not in state['signals']:
            gated.append('This case requires an acknowledgment of the patient’s concern before this topic is disclosed.')
        elif any(dep not in state['revealed'] for dep in fact.get('requires', [])):
            gated.append('This topic has a faculty-defined prerequisite that has not yet been elicited.')
        else:
            allowed.append(fact)
    for fact in allowed:
        state['revealed'].setdefault(fact['id'], turn)
        state['elicited'].setdefault(fact['id'], turn)
        role = 'record' if fact['disclosure'] == 'record' else 'patient'
        state['messages'].append({'turn': turn, 'role': role, 'text': fact['answer'], 'fact_ids': [fact['id']], 'source': source, 'at': now()})
    if gated:
        state['messages'].append({'turn': turn, 'role': 'system', 'text': ' '.join(dict.fromkeys(gated)), 'fact_ids': [], 'source': 'disclosure-gate', 'at': now()})
    if not allowed and not gated:
        if observed:
            state['messages'].append({'turn': turn, 'role': 'system', 'text': 'Communication move recorded. Continue with a question about the patient’s experience.', 'fact_ids': [], 'source': 'communication', 'at': now()})
        else:
            state['unknown_queries'].append({'turn': turn, 'text': question})
            state['messages'].append({'turn': turn, 'role': 'system', 'text': UNKNOWN, 'fact_ids': [], 'source': 'abstention', 'at': now()})
    return state


def debrief(case: dict, state: dict) -> dict:
    if state['status'] != 'ended': raise ValueError('End the encounter before opening the debrief.')
    objectives, total, earned = [], 0, 0
    lookup = {f['id']: f for f in case['facts']}
    for obj in case['objectives']:
        fids = list(dict.fromkeys(obj.get('fact_ids', [])))
        signal = obj.get('signal', '')
        elements = len(fids) + bool(signal)
        matched = sum(fid in state['elicited'] for fid in fids) + bool(signal and signal in state['signals'])
        ratio = matched / elements if elements else 0
        weight = obj.get('weight', 1)
        earned += ratio * weight
        total += weight
        objectives.append({
            **obj, 'observed_elements': matched, 'expected_elements': elements,
            'complete': matched == elements, 'coverage_percent': round(100 * ratio),
            'evidence': [{'fact_id': fid, 'label': lookup[fid]['label'], 'turn': state['elicited'].get(fid), 'answer': lookup[fid]['answer'], 'example_question': lookup[fid].get('aliases', [''])[0]} for fid in fids],
            'signal_evidence': state['signals'].get(signal),
        })
    communication = [{'id': key, 'label': label, 'status': 'Pattern observed' if key in state['signals'] else 'Not observed by this text checklist', 'evidence': state['signals'].get(key)} for key, label in SIGNAL_LABELS.items()]
    quotes = [m for m in state['messages'] if m['role'] in ('patient', 'record')]
    exact = sum(m['text'] == lookup[m['fact_ids'][0]]['answer'] for m in quotes)
    return {
        'coverage_percent': round(earned / total * 100) if total else 0,
        'score_label': 'Weighted rubric-element coverage — not a competency score',
        'objectives': objectives, 'critical_missed': [o['title'] for o in objectives if o.get('critical') and not o['complete']],
        'communication': communication, 'elicited_count': len(state['elicited']),
        'elicitable_count': sum(f['disclosure'] in ('ask', 'record') for f in case['facts']),
        'grounding': {'exact_quote_messages': exact, 'clinical_messages': len(quotes), 'meaning': 'Text provenance only. This does not measure routing accuracy or clinical correctness.'},
        'unknown_queries': state['unknown_queries'], 'blocked_queries': state['blocked_queries'],
        'review': state.get('review'),
        'limitations': 'Text-pattern observations are not validated ratings of empathy. Tone, nonverbal communication, clinical reasoning and real-world competence are not assessed. Faculty review is required.',
    }
