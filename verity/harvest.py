"""Two bounded harvest agents: find PubMed citation metadata, then load it.

This does not ingest all published medical data. PubMed alone contains tens of
millions of records; full texts are copyrighted. Each run fetches a capped page
of citation metadata for configured topics, with NCBI-friendly pauses.
"""
from __future__ import annotations
import argparse
import os
import time
from pathlib import Path
from .literature import search_pubmed
from .server import ROOT, load_env_file
from .service import Service

DEFAULT_TOPICS = (
    'fatigue hypothyroidism',
    'penicillin allergy',
    'chest tightness smoking',
)
HARD_CAP = 100
PAGE_SIZE = 8
PAUSE_SECONDS = 0.4


def topic_list(raw: str | None = None) -> list[str]:
    text = raw if raw is not None else os.environ.get('HARVEST_TOPICS', '')
    topics = [part.strip() for part in text.replace('\n', ';').split(';') if part.strip()]
    return topics or list(DEFAULT_TOPICS)


def run_cap(raw: str | None = None) -> int:
    try:
        value = int(raw if raw is not None else os.environ.get('HARVEST_MAX_RECORDS', '40'))
    except (TypeError, ValueError):
        value = 40
    return max(1, min(value, HARD_CAP))


class FinderAgent:
    """Search PubMed for configured topics and queue citation metadata."""

    def __init__(self, service: Service, pause: float = PAUSE_SECONDS):
        self.service = service
        self.pause = pause

    def run(self, topics: list[str], limit: int) -> dict:
        self.service.ensure_topics(topics)
        queued, searches = 0, 0
        while queued < limit:
            topic = self.service.next_topic()
            if not topic:
                break
            remaining = limit - queued
            try:
                found = search_pubmed(topic['query'], retmax=min(PAGE_SIZE, remaining), retstart=topic['retstart'])
            except Exception as error:
                self.service.save_topic(topic['query'], topic['retstart'], topic['indexed_count'], 'error', str(error)[:300])
                break
            searches += 1
            records = found.get('records', [])[:remaining]
            added = self.service.enqueue_inbox(found['query'], records)
            queued += added
            retstart = topic['retstart'] + len(records)
            indexed = int(found.get('count') or 0)
            window = min(indexed, 400)
            status = 'caught_up' if (not found.get('records') or retstart >= window) else 'pending'
            self.service.save_topic(topic['query'], retstart, indexed, status)
            if self.pause:
                time.sleep(self.pause)
            if status != 'pending':
                continue
        return {'agent': 'finder', 'queued': queued, 'searches': searches, 'limit': limit}


class LoaderAgent:
    """Move queued citation metadata into the local literature table."""

    def __init__(self, service: Service):
        self.service = service

    def run(self, limit: int) -> dict:
        loaded, batches = 0, 0
        while loaded < limit:
            items = self.service.take_inbox(min(20, limit - loaded))
            if not items:
                break
            grouped = {}
            for item in items:
                grouped.setdefault(item['query'], []).append(item['record'])
            for query, records in grouped.items():
                self.service.remember_literature(query, records, 'literature-loader')
                loaded += len(records)
                batches += 1
        return {'agent': 'loader', 'loaded': loaded, 'batches': batches, 'limit': limit}


def run_once(service: Service, topics: list[str] | None = None, limit: int | None = None) -> dict:
    cap = limit if limit is not None else run_cap()
    finder = FinderAgent(service)
    loader = LoaderAgent(service)
    found = finder.run(topics or topic_list(), cap)
    stored = loader.run(cap)
    library = service.list_literature()
    return {
        'finder': found,
        'loader': stored,
        'stored': library['stored'],
        'limitation': 'Citation metadata for configured topics only. Not all journals, datasets, or full texts.',
    }


def main():
    load_env_file(ROOT / '.env')
    parser = argparse.ArgumentParser(description='Bounded PubMed citation harvest for Verity Encounter')
    parser.add_argument('--db', default=str(ROOT / 'data/verity.sqlite3'))
    parser.add_argument('--topics', default=None, help='Semicolon-separated PubMed queries')
    parser.add_argument('--max-records', type=int, default=None)
    args = parser.parse_args()
    service = Service(args.db, seed=True)
    result = run_once(service, topic_list(args.topics), run_cap(None if args.max_records is None else str(args.max_records)))
    print('Finder queued {queued} records in {searches} searches.'.format(**result['finder']), flush=True)
    print('Loader stored {loaded} records in {batches} batches.'.format(**result['loader']), flush=True)
    print(f"Library size: {result['stored']}", flush=True)
    print(result['limitation'], flush=True)


if __name__ == '__main__':
    main()
