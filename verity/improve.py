"""Recursively improve approved cases using local DB evidence.

Adds routing phrases from unmatched learner questions and stored PubMed
metadata. Does not invent patient answers or overwrite unpublished faculty drafts.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from .engine import digest, normalize, rule_route, valid_text, validate_case
from .server import ROOT, load_env_file
from .service import Service

GENERIC = {'tell me more', 'tell me about', 'what brings', 'walk me through'}
STOP = {
    'what', 'when', 'where', 'which', 'that', 'this', 'with', 'from', 'have', 'does', 'your', 'about',
    'tell', 'more', 'been', 'they', 'them', 'were', 'their', 'into', 'would', 'could', 'should',
    'please', 'there', 'here', 'just', 'like', 'some', 'any', 'the', 'and', 'for', 'are', 'was',
}
MAX_ROUNDS = 5
MAX_ALIASES = 30
LOG_ID = 'improve_log'
MAX_NEW_CASES = 12
RECORDS_PER_CASE = 6
GIVEN = ['Avery', 'Blake', 'Casey', 'Drew', 'Eden', 'Finley', 'Gray', 'Harper']
FAMILY = ['Nolan', 'Patel', 'Reed', 'Solis', 'Trent', 'Voss', 'Wade', 'Young']


def phrases_from(text: str) -> list[str]:
    words = [w for w in normalize(text).split() if w]
    out, seen = [], set()
    candidates = []
    if 2 <= len(words) <= 10:
        candidates.append(' '.join(words))
    for n in (3, 2):
        for i in range(0, max(0, len(words) - n + 1)):
            candidates.append(' '.join(words[i:i + n]))
    for phrase in candidates:
        if phrase in seen or phrase in GENERIC or len(phrase) > 120:
            continue
        parts = phrase.split()
        if not any(len(p) > 3 and p not in STOP for p in parts):
            continue
        if not valid_text(phrase, 120) or not normalize(phrase):
            continue
        seen.add(phrase)
        out.append(phrase)
    return out


def fact_tokens(fact: dict) -> set[str]:
    blob = ' '.join([fact.get('label', ''), fact.get('answer', ''), ' '.join(fact.get('aliases') or [])])
    return {w for w in normalize(blob).split() if len(w) > 2}


def add_alias(fact: dict, phrase: str) -> bool:
    if fact.get('disclosure') not in ('ask', 'record'):
        return False
    aliases = list(fact.get('aliases') or [])
    key = normalize(phrase)
    if not key or any(normalize(a) == key for a in aliases) or len(aliases) >= MAX_ALIASES:
        return False
    aliases.append(phrase)
    fact['aliases'] = aliases
    return True


def best_fact(facts: list[dict], question: str) -> dict | None:
    tokens = {w for w in normalize(question).split() if len(w) > 3 and w not in STOP}
    ranked = []
    for fact in facts:
        if fact.get('disclosure') not in ('ask', 'record'):
            continue
        overlap = len(tokens & fact_tokens(fact))
        if overlap:
            ranked.append((overlap, -len(fact.get('aliases') or []), fact))
    if not ranked:
        return None
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return ranked[0][2]


def literature_phrases(records: list[dict]) -> list[str]:
    phrases = []
    for rec in records:
        phrases.extend(phrases_from(rec.get('title') or ''))
        for query in rec.get('queries') or []:
            phrases.extend(phrases_from(query))
    return phrases


def update_faculty_log(case: dict, notes: list[str]) -> bool:
    text = 'Recursive improvement log (not patient speech).\n' + '\n'.join(notes[:12])
    text = text[:2000]
    for fact in case['facts']:
        if fact.get('id') == LOG_ID:
            if fact.get('answer') == text:
                return False
            fact['answer'] = text
            fact['label'] = 'Recursive improvement log'
            fact['disclosure'] = 'faculty_only'
            fact['group'] = 'Faculty only'
            return True
    if len(case['facts']) >= 80:
        return False
    case['facts'].append({
        'id': LOG_ID, 'label': 'Recursive improvement log', 'answer': text, 'aliases': [],
        'group': 'Faculty only', 'disclosure': 'faculty_only', 'requires': [],
        'requires_empathy': False, 'attachment_ids': [],
    })
    return True


def improve_case(case: dict, questions: list[str], literature: list[dict]) -> dict:
    """Return a new case plus counts. Patient answers are copied, not rewritten."""
    updated = copy.deepcopy(case)
    added, residual = 0, []
    lookup = {f['id']: f for f in updated['facts']}
    for question in questions:
        if not valid_text(question, 1500):
            continue
        matched = rule_route(question, updated['facts'])
        target = lookup.get(matched[0]) if matched else best_fact(updated['facts'], question)
        if not target:
            residual.append(question)
            continue
        if matched:
            extras = phrases_from(question)[:2]
        else:
            extras = phrases_from(question)[:3]
        changed = False
        for phrase in extras:
            if add_alias(target, phrase):
                added += 1
                changed = True
        if not matched and not changed:
            residual.append(question)
        elif not matched and rule_route(question, updated['facts']):
            pass
        elif not matched:
            residual.append(question)
    for phrase in literature_phrases(literature):
        target = best_fact(updated['facts'], phrase)
        if target and (fact_tokens(target) & set(phrase.split())):
            if add_alias(target, phrase):
                added += 1
    notes = []
    if added:
        notes.append(f'Added {added} routing phrase(s) from unmatched questions and local literature metadata.')
    if residual:
        notes.append('Still unmatched (no overlapping approved fact): ' + '; '.join(residual[:8]))
    related = [f"PMID {r.get('pmid')} · {r.get('title')}" for r in literature[:6] if r.get('pmid')]
    if related:
        notes.append('Local library used: ' + ' | '.join(related))
    log_changed = update_faculty_log(updated, notes) if notes else False
    return {'case': updated, 'added': added, 'changed': added > 0 or log_changed, 'residual': residual}


def related_literature(case: dict, records: list[dict], limit=8) -> list[dict]:
    tokens = set()
    for fact in case.get('facts') or []:
        tokens |= fact_tokens(fact)
    tokens |= {w for w in normalize(case.get('title', '') + ' ' + case.get('description', '')).split() if len(w) > 3}
    scored = []
    for rec in records:
        blob = set(normalize((rec.get('title') or '') + ' ' + ' '.join(rec.get('queries') or [])).split())
        overlap = len(tokens & blob)
        if overlap:
            scored.append((overlap, rec))
    scored.sort(key=lambda item: (-item[0], item[1].get('pmid', '')))
    return [item[1] for item in scored[:limit]]


def topic_title(query: str) -> str:
    label = query.strip()[:180] or 'untagged library topic'
    return f'Library topic: {label}'


def library_topic(case: dict) -> str:
    if isinstance(case.get('library_topic'), str) and case['library_topic'].strip():
        return case['library_topic'].strip()
    title = case.get('title') or ''
    if title.startswith('Library topic: '):
        return title[len('Library topic: '):].strip()
    return ''


def used_pmids(cases: list[dict]) -> set[str]:
    found = set()
    for case in cases:
        for fact in case.get('facts') or []:
            fid = fact.get('id') or ''
            if fid.startswith('pmid') and fid[4:].isdigit():
                found.add(fid[4:])
    return found


def group_records(records: list[dict]) -> dict[str, list[dict]]:
    grouped = {}
    for rec in records:
        queries = [q.strip() for q in (rec.get('queries') or []) if isinstance(q, str) and q.strip()]
        key = queries[0] if queries else 'untagged library topic'
        grouped.setdefault(key, []).append(rec)
    return grouped


def fictional_patient(query: str) -> dict:
    digest_bytes = hashlib.sha256(query.encode()).digest()
    return {
        'name': f'{GIVEN[digest_bytes[0] % len(GIVEN)]} {FAMILY[digest_bytes[1] % len(FAMILY)]}',
        'age': 28 + digest_bytes[2] % 45,
        'pronouns': 'they/them',
    }


def pmid_fact(rec: dict) -> dict:
    pmid = str(rec.get('pmid') or '')
    title = (rec.get('title') or 'Untitled PubMed record')[:240]
    aliases = ['publication', 'paper', 'pmid', 'citation', 'journal']
    words = [w for w in normalize(title).split() if len(w) > 3][:4]
    for word in words:
        if word not in aliases:
            aliases.append(word)
    answer = (
        f'Synthetic teaching citation from the local PubMed library. PMID {pmid}. {title} '
        f"{rec.get('journal') or ''} ({rec.get('year') or ''}). "
        'This is indexed metadata, not a result from this fictional patient.'
    )[:2000]
    return {
        'id': f'pmid{pmid}'[:50], 'label': f'Published record {pmid}', 'answer': answer,
        'aliases': aliases[:30], 'group': 'Investigations', 'disclosure': 'record',
        'requires': [], 'requires_empathy': False, 'attachment_ids': [],
    }


def build_library_case(query: str, records: list[dict]) -> dict:
    patient = fictional_patient(query)
    title = topic_title(query)
    recs = records[:RECORDS_PER_CASE]
    facts = [
        {
            'id': 'opening', 'label': 'Presenting concern',
            'answer': 'I came in because something has been on my mind, and I would like to talk it through.',
            'aliases': [], 'group': 'Presenting concern', 'disclosure': 'initial',
            'requires': [], 'requires_empathy': False, 'attachment_ids': [],
        },
        {
            'id': 'concern', 'label': 'Why now',
            'answer': f'This is a synthetic interview for the library topic “{query}”. I can describe what I have noticed. I do not have a real chart.',
            'aliases': ['what brings', 'tell me more', 'tell me about', 'concern', 'worried', 'bothering'],
            'group': 'History', 'disclosure': 'ask', 'requires': [], 'requires_empathy': False, 'attachment_ids': [],
        },
        {
            'id': 'timeline', 'label': 'Timeline',
            'answer': 'It has been going on long enough that I wanted someone to ask me about it in an interview.',
            'aliases': ['when did', 'how long', 'started', 'onset', 'timeline'],
            'group': 'History', 'disclosure': 'ask', 'requires': [], 'requires_empathy': False, 'attachment_ids': [],
        },
    ]
    facts.extend(pmid_fact(rec) for rec in recs if str(rec.get('pmid') or '').isdigit())
    facts.append({
        'id': LOG_ID, 'label': 'Recursive improvement log',
        'answer': 'Created from the local literature table. Patient answers are synthetic. Citation facts quote PubMed metadata only.',
        'aliases': [], 'group': 'Faculty only', 'disclosure': 'faculty_only',
        'requires': [], 'requires_empathy': False, 'attachment_ids': [],
    })
    record_ids = [f['id'] for f in facts if f['disclosure'] == 'record'][:3]
    objectives = [
        {'id': 'concern', 'title': 'Explore the synthetic presenting concern', 'fact_ids': ['concern'], 'signal': '', 'weight': 2, 'critical': False},
        {'id': 'timeline', 'title': 'Establish a timeline', 'fact_ids': ['timeline'], 'signal': '', 'weight': 1, 'critical': False},
        {'id': 'records', 'title': 'Request a stored publication', 'fact_ids': record_ids or ['timeline'], 'signal': '', 'weight': 2, 'critical': False},
        {'id': 'empathy', 'title': 'Acknowledge the patient’s concern', 'fact_ids': [], 'signal': 'empathy', 'weight': 1, 'critical': False},
    ]
    return {
        'title': title, 'setting': 'Outpatient interview',
        'description': f'Library topic: {query}. Synthetic teaching case generated from local PubMed citation metadata.',
        'author': 'Literature table importer — synthetic', 'synthetic': True,
        'library_topic': query, 'patient': patient, 'facts': facts, 'objectives': objectives,
    }


def published_cases(service: Service) -> list[tuple[str, dict, int]]:
    with service.db() as conn:
        rows = conn.execute('SELECT id, published, revision FROM cases WHERE published IS NOT NULL').fetchall()
    return [(row['id'], json.loads(row['published']), row['revision']) for row in rows]


def add_approved_cases_from_table(service: Service, publish: bool = True, rounds: int = MAX_ROUNDS) -> dict:
    """Create and fill synthetic approved cases from the literature table, topic by topic."""
    rounds = max(1, min(int(rounds), MAX_ROUNDS))
    history = []
    created_total = 0
    for round_no in range(1, rounds + 1):
        records = service.list_literature().get('records', [])
        existing = published_cases(service)
        topics = {library_topic(case): cid for cid, case, _rev in existing if library_topic(case)}
        claimed = used_pmids([case for _cid, case, _rev in existing])
        grouped = group_records(records)
        created, filled = 0, 0
        for query, group in grouped.items():
            unused = [rec for rec in group if rec.get('pmid') not in claimed]
            if not unused:
                continue
            if query not in topics:
                if created_total >= MAX_NEW_CASES:
                    continue
                case = build_library_case(query, unused)
                errors = validate_case(case)
                if errors:
                    history.append({'round': round_no, 'query': query, 'skipped': 'validation', 'errors': errors[:5]})
                    continue
                saved = service.create_case(case, 'case-importer')
                if publish:
                    service.publish(saved['id'], saved['revision'], 'Literature table importer — synthetic; not clinician reviewed', 'case-importer')
                for rec in unused[:RECORDS_PER_CASE]:
                    claimed.add(rec.get('pmid'))
                topics[query] = saved['id']
                created += 1
                created_total += 1
                history.append({'round': round_no, 'created': saved['id'], 'title': case['title'], 'records': min(len(unused), RECORDS_PER_CASE)})
                continue
            cid = topics[query]
            row = next((item for item in existing if item[0] == cid), None)
            if not row:
                continue
            case = copy.deepcopy(row[1])
            added_here = 0
            for rec in unused:
                if len(case['facts']) >= 80 or added_here >= RECORDS_PER_CASE:
                    break
                fact = pmid_fact(rec)
                if any(f.get('id') == fact['id'] for f in case['facts']):
                    continue
                case['facts'].append(fact)
                objs = [o for o in case['objectives'] if o.get('id') == 'records']
                if objs and fact['id'] not in objs[0]['fact_ids'] and len(objs[0]['fact_ids']) < 12:
                    objs[0]['fact_ids'].append(fact['id'])
                claimed.add(rec.get('pmid'))
                added_here += 1
            if not added_here:
                continue
            errors = validate_case(case)
            if errors:
                history.append({'round': round_no, 'case_id': cid, 'skipped': 'validation', 'errors': errors[:5]})
                continue
            current = service.get_case(cid, True)
            if digest(current['case']) != digest(row[1]):
                history.append({'round': round_no, 'case_id': cid, 'skipped': 'unpublished faculty edits'})
                continue
            saved = service.save_case(cid, case, current['revision'], 'case-importer')
            if publish:
                service.publish(saved['id'], saved['revision'], 'Literature table importer — synthetic; not clinician reviewed', 'case-importer')
            filled += 1
            history.append({'round': round_no, 'filled': cid, 'added_records': added_here})
        history.append({'round': round_no, 'created': created, 'filled': filled})
        if created == 0 and filled == 0:
            break
        existing = published_cases(service)
    return {
        'rounds': history,
        'created': created_total,
        'limitation': 'Adds synthetic teaching cases from local PubMed citation rows. Journal text is not used as the patient’s spoken history.',
    }


def improve_approved_cases(service: Service, publish: bool = True, rounds: int = MAX_ROUNDS) -> dict:
    rounds = max(1, min(int(rounds), MAX_ROUNDS))
    history = []
    for round_no in range(1, rounds + 1):
        gaps_by_case = {}
        for gap in service.analytics().get('case_gaps', []):
            gaps_by_case.setdefault(gap['case_id'], []).append(gap['question'])
        records = service.list_literature().get('records', [])
        round_added, touched = 0, 0
        with service.db() as conn:
            rows = conn.execute('SELECT * FROM cases WHERE published IS NOT NULL').fetchall()
        for row in rows:
            published = json.loads(row['published'])
            draft = json.loads(row['draft'])
            if digest(published) != digest(draft):
                history.append({'round': round_no, 'case_id': row['id'], 'skipped': 'unpublished faculty edits'})
                continue
            questions = gaps_by_case.get(row['id'], [])
            lit = related_literature(published, records)
            result = improve_case(published, questions, lit)
            if not result['changed']:
                continue
            errors = validate_case(result['case'])
            if errors:
                history.append({'round': round_no, 'case_id': row['id'], 'skipped': 'validation', 'errors': errors[:5]})
                continue
            saved = service.save_case(row['id'], result['case'], row['revision'], 'case-improver')
            published_ok = False
            if publish:
                service.publish(saved['id'], saved['revision'], 'Recursive improver — aliases and faculty log only; not clinician reviewed', 'case-improver')
                published_ok = True
            touched += 1
            round_added += result['added']
            history.append({
                'round': round_no, 'case_id': row['id'], 'title': published.get('title'),
                'added': result['added'], 'published': published_ok, 'residual': result['residual'][:5],
            })
        history.append({'round': round_no, 'added': round_added, 'cases_touched': touched})
        if not round_added and not touched:
            break
    return {
        'rounds': history,
        'limitation': 'Improves routing phrases and a faculty-only log from local tables. Does not rewrite approved patient answers or import journal text as speech.',
    }


def main():
    load_env_file(ROOT / '.env')
    parser = argparse.ArgumentParser(description='Recursively improve approved Verity cases from local DB tables')
    parser.add_argument('--db', default=str(ROOT / 'data/verity.sqlite3'))
    parser.add_argument('--draft-only', action='store_true', help='Save drafts without republishing')
    parser.add_argument('--add-cases', action='store_true', help='Create approved synthetic cases from the literature table')
    parser.add_argument('--rounds', type=int, default=MAX_ROUNDS)
    args = parser.parse_args()
    service = Service(args.db, seed=True)
    if args.add_cases:
        result = add_approved_cases_from_table(service, publish=not args.draft_only, rounds=args.rounds)
    else:
        result = improve_approved_cases(service, publish=not args.draft_only, rounds=args.rounds)
    print(result['limitation'], flush=True)
    for item in result.get('rounds', []):
        print(item, flush=True)


if __name__ == '__main__':
    main()
