"""Faculty PubMed lookup via NCBI E-utilities. Records are never used as patient speech."""
from __future__ import annotations
import json
import urllib.parse
import urllib.request
from .engine import valid_text
from .service import Problem

EUTILS = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'
TOOL = 'verity_encounter'


def _get(url: str, timeout: float) -> dict:
    request = urllib.request.Request(url, headers={'User-Agent': 'VerityEncounter/1.0'})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read(2 * 1024 * 1024))


def search_pubmed(query: str, timeout: float = 12.0, retmax: int = 8, retstart: int = 0) -> dict:
    if not valid_text(query, 300):
        raise Problem(422, 'Enter a PubMed search of 1–300 characters.')
    retmax = max(1, min(int(retmax), 20))
    retstart = max(0, min(int(retstart), 400))
    params = urllib.parse.urlencode({
        'db': 'pubmed', 'term': query.strip(), 'retmax': retmax, 'retstart': retstart,
        'retmode': 'json', 'sort': 'relevance', 'tool': TOOL,
    })
    try:
        found = _get(f'{EUTILS}esearch.fcgi?{params}', timeout)
    except Exception as error:
        raise Problem(502, f'PubMed search could not be completed: {error}') from error
    result = found.get('esearchresult') or {}
    ids = [str(x) for x in result.get('idlist', []) if str(x).isdigit()]
    if not ids:
        return {'query': query.strip(), 'source': 'PubMed / NCBI E-utilities', 'count': 0, 'records': []}
    summary_params = urllib.parse.urlencode({
        'db': 'pubmed', 'id': ','.join(ids), 'retmode': 'json', 'tool': TOOL,
    })
    try:
        summary = _get(f'{EUTILS}esummary.fcgi?{summary_params}', timeout)
    except Exception as error:
        raise Problem(502, f'PubMed summaries could not be loaded: {error}') from error
    records = []
    result_map = summary.get('result') or {}
    for pmid in ids:
        item = result_map.get(pmid) or {}
        if not isinstance(item, dict):
            continue
        records.append({
            'pmid': pmid,
            'title': item.get('title') or 'Untitled PubMed record',
            'journal': item.get('fulljournalname') or item.get('source') or '',
            'year': str(item.get('pubdate') or '')[:4],
            'publication_types': [t for t in item.get('pubtype', []) if isinstance(t, str)][:4],
            'url': f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/',
        })
    return {
        'query': query.strip(),
        'source': 'PubMed / NCBI E-utilities',
        'count': int(result.get('count') or len(records)),
        'records': records,
        'note': 'These are existing PubMed records for faculty review. They are not this synthetic patient’s answers and are not inserted into the encounter transcript.',
    }
