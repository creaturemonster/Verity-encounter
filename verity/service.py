"""Persistent case workflow, disclosure-aware projections and encounter isolation."""
from __future__ import annotations
import base64
import copy
import hashlib
import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from .engine import advance, canonical, debrief, digest, new_state, now, normalize, validate_case, valid_text

class Problem(Exception):
    def __init__(self, status: int, message: str, details=None):
        super().__init__(message)
        self.status, self.message, self.details = status, message, details

class Service:
    def __init__(self, db_path: str | Path, router=None, seed=True):
        self.db_path, self.router = str(db_path), router
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self.db() as conn:
            conn.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS cases (
                    id TEXT PRIMARY KEY, draft TEXT NOT NULL, revision INTEGER NOT NULL,
                    published TEXT, published_revision INTEGER, content_hash TEXT,
                    approved_by TEXT, approved_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS encounters (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, case_id TEXT NOT NULL,
                    snapshot TEXT NOT NULL, case_hash TEXT NOT NULL, case_revision INTEGER NOT NULL,
                    state TEXT NOT NULL, revision INTEGER NOT NULL, created_at TEXT NOT NULL, parent_id TEXT
                );
                CREATE INDEX IF NOT EXISTS encounter_owner ON encounters(owner);
                CREATE TABLE IF NOT EXISTS artifacts (
                    id TEXT PRIMARY KEY, case_id TEXT NOT NULL, fact_id TEXT NOT NULL,
                    name TEXT NOT NULL, mime TEXT NOT NULL, sha256 TEXT NOT NULL, content BLOB NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT NOT NULL, actor TEXT NOT NULL,
                    kind TEXT NOT NULL, payload TEXT NOT NULL, previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS literature (
                    pmid TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    journal TEXT NOT NULL,
                    year TEXT NOT NULL,
                    publication_types TEXT NOT NULL,
                    url TEXT NOT NULL,
                    queries TEXT NOT NULL,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS literature_journal ON literature(journal);
                CREATE TABLE IF NOT EXISTS literature_topics (
                    query TEXT PRIMARY KEY,
                    retstart INTEGER NOT NULL DEFAULT 0,
                    indexed_count INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    last_error TEXT,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS literature_inbox (
                    pmid TEXT NOT NULL,
                    query TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    found_at TEXT NOT NULL,
                    PRIMARY KEY (pmid, query)
                );
            ''')
        if seed: self.seed()

    @contextmanager
    def db(self, write=False):
        conn = sqlite3.connect(self.db_path, timeout=15)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        try:
            if write: conn.execute('BEGIN IMMEDIATE')
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def audit(self, conn, actor, kind, payload):
        previous = conn.execute('SELECT event_hash FROM audit ORDER BY seq DESC LIMIT 1').fetchone()
        previous = previous[0] if previous else '0'*64
        timestamp = now()
        event = dict(at=timestamp, actor=actor, kind=kind, payload=payload, previous_hash=previous)
        conn.execute('INSERT INTO audit(at,actor,kind,payload,previous_hash,event_hash) VALUES(?,?,?,?,?,?)',
                     (timestamp, actor, kind, canonical(payload), previous, digest(event)))

    def verify_audit(self):
        with self.db() as conn: rows = conn.execute('SELECT * FROM audit ORDER BY seq').fetchall()
        previous = '0'*64
        for row in rows:
            event = dict(at=row['at'], actor=row['actor'], kind=row['kind'], payload=json.loads(row['payload']), previous_hash=row['previous_hash'])
            if row['previous_hash'] != previous or digest(event) != row['event_hash']:
                return {'consistent':False, 'events':len(rows), 'first_invalid_seq':row['seq']}
            previous = row['event_hash']
        return {'consistent':True, 'events':len(rows), 'head_hash':previous, 'limitation':'Local hash chain; not externally anchored or tamper-proof.'}

    def seed(self):
        from .seeds import cases
        with self.db() as conn:
            rows = conn.execute('SELECT draft, published FROM cases').fetchall()
        titles = set()
        for row in rows:
            for blob in (row['draft'], row['published']):
                if not blob:
                    continue
                titles.add(json.loads(blob).get('title'))
        for case in cases():
            if case.get('title') in titles:
                continue
            saved = self.create_case(case, 'fixture-loader')
            self.publish(saved['id'], saved['revision'], 'Demo fixture—not clinician reviewed', 'fixture-loader')
            titles.add(case['title'])

    def _case(self, conn, cid):
        row = conn.execute('SELECT * FROM cases WHERE id=?', (cid,)).fetchone()
        if not row: raise Problem(404, 'Case not found.')
        return row

    def _artifact_refs_valid(self, conn, cid, case):
        for fact in case.get('facts', []):
            if not isinstance(fact, dict): continue
            for aid in fact.get('attachment_ids', []):
                row = conn.execute('SELECT case_id, fact_id FROM artifacts WHERE id=?', (aid,)).fetchone()
                if not row or row['case_id'] != cid or row['fact_id'] != fact['id']:
                    raise Problem(422, 'An attachment is not owned by this case and fact.')

    def _draft_shape(self, case):
        # Incomplete text is allowed in drafts; malformed containers are not.
        if not isinstance(case, dict) or len(canonical(case)) > 200_000:
            raise Problem(422, 'Invalid case object.')
        if not all(isinstance(case.get(k, ''), str) for k in ('title','setting','author','description')):
            raise Problem(422, 'Case labels must be text.')
        if not isinstance(case.get('patient'), dict) or not isinstance(case.get('facts'), list) or not isinstance(case.get('objectives'), list):
            raise Problem(422, 'A case needs a patient object, facts array and objectives array.')
        if len(case['facts']) > 80 or len(case['objectives']) > 30:
            raise Problem(422, 'Case exceeds the fact or objective limit.')
        for fact in case['facts']:
            if not isinstance(fact, dict) or not all(isinstance(fact.get(k,''), str) for k in ('id','label','answer','group','disclosure')):
                raise Problem(422, 'Fact fields must be text.')
            for key in ('aliases','requires','attachment_ids'):
                if not isinstance(fact.get(key,[]),list) or not all(isinstance(x,str) for x in fact.get(key,[])):
                    raise Problem(422, 'Fact lists must contain strings.')
        for obj in case['objectives']:
            if not isinstance(obj,dict) or not all(isinstance(obj.get(k,''),str) for k in ('id','title','signal')):
                raise Problem(422, 'Objective fields must be text.')
            if not isinstance(obj.get('fact_ids',[]),list) or not all(isinstance(x,str) for x in obj.get('fact_ids',[])):
                raise Problem(422, 'Objective fact references must be strings.')

    def create_case(self, case: dict, actor: str):
        self._draft_shape(case)
        cid = 'case_' + uuid.uuid4().hex[:12]
        with self.db(True) as conn:
            self._artifact_refs_valid(conn, cid, case)
            conn.execute('INSERT INTO cases(id,draft,revision,created_at,updated_at) VALUES(?,?,?,?,?)',
                         (cid, canonical(case), 1, now(), now()))
            self.audit(conn, actor, 'case.created', {'case_id':cid,'revision':1})
        return self.get_case(cid, faculty=True)

    def save_case(self, cid, case: dict, revision: int, actor):
        self._draft_shape(case)
        with self.db(True) as conn:
            row = self._case(conn, cid)
            if row['revision'] != revision: raise Problem(409, 'The draft changed. Reload before saving.')
            self._artifact_refs_valid(conn, cid, case)
            conn.execute('UPDATE cases SET draft=?,revision=revision+1,updated_at=? WHERE id=?', (canonical(case),now(),cid))
            self.audit(conn, actor, 'case.draft_saved', {'case_id':cid,'revision':revision+1})
        return self.get_case(cid, faculty=True)

    def publish(self, cid, revision, reviewer, actor):
        if not valid_text(reviewer, 120): raise Problem(422, 'Enter the reviewing faculty member’s name.')
        with self.db(True) as conn:
            row = self._case(conn, cid)
            if row['revision'] != revision: raise Problem(409, 'The draft changed. Review the current revision.')
            case = json.loads(row['draft'])
            errors = validate_case(case)
            if errors: raise Problem(422, 'The case is not ready for approval.', errors)
            self._artifact_refs_valid(conn, cid, case)
            h = digest(case)
            conn.execute('UPDATE cases SET published=draft,published_revision=revision,content_hash=?,approved_by=?,approved_at=? WHERE id=?', (h,reviewer,now(),cid))
            self.audit(conn, actor, 'case.approved', {'case_id':cid,'revision':revision,'hash':h,'reviewer':reviewer})
        return self.get_case(cid, faculty=True)

    def _summary(self, row, faculty=False):
        case = json.loads(row['draft'] if faculty else row['published'])
        return {
            'id':row['id'], 'title':case.get('title','Untitled draft'), 'setting':case.get('setting',''),
            'description':case.get('description',''), 'patient':{k:case.get('patient',{}).get(k,'') for k in ('name','age','pronouns')},
            'revision':row['revision'] if faculty else row['published_revision'],
            'published_revision':row['published_revision'], 'hash':row['content_hash'],
            'approved_by':row['approved_by'], 'approved_at':row['approved_at'],
            'status':'Draft' if not row['published'] else ('Unpublished changes' if faculty and row['revision'] != row['published_revision'] else 'Approved'),
            'synthetic':True,
        }

    def list_cases(self, faculty=False):
        with self.db() as conn:
            rows = conn.execute('SELECT * FROM cases '+('' if faculty else 'WHERE published IS NOT NULL ')+'ORDER BY created_at').fetchall()
        return [self._summary(r,faculty) for r in rows]

    def get_case(self, cid, faculty=False):
        with self.db() as conn:
            row = self._case(conn,cid)
            if not faculty and row['published'] is None: raise Problem(404,'Approved case not found.')
            result = self._summary(row,faculty)
            if faculty:
                result['case'] = json.loads(row['draft'])
                result['validation_errors'] = validate_case(result['case'])
                result['artifacts'] = [dict(r) for r in conn.execute('SELECT id,fact_id,name,mime,sha256 FROM artifacts WHERE case_id=?',(cid,))]
            return result

    def start(self, cid, owner):
        with self.db(True) as conn:
            row = self._case(conn,cid)
            if not row['published']: raise Problem(409, 'A faculty-approved version is required.')
            case = json.loads(row['published'])
            eid = 'enc_' + uuid.uuid4().hex
            state = new_state(case)
            conn.execute('INSERT INTO encounters VALUES(?,?,?,?,?,?,?,?,?,?)',
                         (eid,owner,cid,row['published'],row['content_hash'],row['published_revision'],canonical(state),1,now(),None))
            self.audit(conn,owner,'encounter.started',{'encounter_id':eid,'case_id':cid,'hash':row['content_hash']})
        return self.get_encounter(eid,owner)

    def _encounter(self, conn, eid, owner, faculty=False):
        row = conn.execute('SELECT * FROM encounters WHERE id=?',(eid,)).fetchone()
        if not row or (row['owner'] != owner and not faculty): raise Problem(404,'Encounter not found.')
        return row

    def _projection(self, conn, row):
        case, state = json.loads(row['snapshot']), json.loads(row['state'])
        chart = []
        for fact in case['facts']:
            if fact['id'] not in state['revealed']: continue
            attachments = []
            for aid in fact.get('attachment_ids',[]):
                ar = conn.execute('SELECT id,name,mime,sha256 FROM artifacts WHERE id=?',(aid,)).fetchone()
                if ar: attachments.append(dict(ar))
            chart.append({'id':fact['id'],'label':fact['label'],'group':fact['group'],'answer':fact['answer'],
                          'turn':state['revealed'][fact['id']], 'elicited':fact['id'] in state['elicited'], 'attachments':attachments})
        result = {
            'id':row['id'],'case_id':row['case_id'],'title':case['title'],'setting':case['setting'],
            'patient':{k:case['patient'].get(k,'') for k in ('name','age','pronouns')},'case_hash':row['case_hash'],'case_revision':row['case_revision'],
            'status':state['status'],'revision':row['revision'],'turn':state['turn'],
            'messages':state['messages'],'chart':chart,'revealed_count':len(chart),
            'elicited_count':len(state['elicited']),'parent_id':row['parent_id'], 'review':state.get('review'),
            'router_mode':state['router_modes'][-1] if state['router_modes'] else ('model-id-router' if self.router else 'local-phrase-router'),
            'knowledge': next((item['records'] for item in reversed(state.get('knowledge') or []) if item.get('turn')==state['turn']), []),
            'knowledge_log': state.get('knowledge') or [],
        }
        if state['status']=='ended': result['debrief']=debrief(case,state)
        return result

    def get_encounter(self,eid,owner,faculty=False):
        with self.db() as conn:
            return self._projection(conn,self._encounter(conn,eid,owner,faculty))

    def turn(self,eid,owner,text,key,revision):
        if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9_-]{8,100}',key): raise Problem(422,'A valid idempotency key is required.')
        if not valid_text(text,1500): raise Problem(422,'Enter 1–1500 characters.')
        def check(row, state):
            if key in state['requests']:
                if state['requests'][key] != text: raise Problem(409,'Idempotency key was reused for another question.')
                return True
            if state['status']!='active': raise Problem(409,'This encounter has ended.')
            if row['revision'] != revision: raise Problem(409,'The encounter changed. Reload before sending.')
            if state['turn']>=100: raise Problem(422,'This local demo allows 100 turns per encounter.')
            return False
        with self.db() as conn:
            row=self._encounter(conn,eid,owner)
            original=json.loads(row['state'])
            if check(row,original): return self._projection(conn,row)
            snapshot=json.loads(row['snapshot'])
        # Never hold SQLite's write lock while waiting for an optional provider.
        state=advance(snapshot,original,text,self.router)
        state['requests'][key]=text
        hits=self.match_literature(text)
        if hits:
            state.setdefault('knowledge', []).append({'turn':state['turn'],'records':hits})
        with self.db(True) as conn:
            current=self._encounter(conn,eid,owner)
            current_state=json.loads(current['state'])
            if check(current,current_state): return self._projection(conn,current)
            conn.execute('UPDATE encounters SET state=?,revision=revision+1 WHERE id=?',(canonical(state),eid))
            self.audit(conn,owner,'encounter.turn',{'encounter_id':eid,'turn':state['turn'],'state_hash':digest(state)})
            return self._projection(conn,self._encounter(conn,eid,owner))

    def finish(self,eid,owner,revision):
        with self.db(True) as conn:
            row = self._encounter(conn,eid,owner)
            state=json.loads(row['state'])
            if state['status']=='ended': return self._projection(conn,row)
            if revision!=row['revision']: raise Problem(409,'The encounter changed. Reload before finishing.')
            state['status']='ended'
            state['ended_at']=now()
            conn.execute('UPDATE encounters SET state=?,revision=revision+1 WHERE id=?',(canonical(state),eid))
            self.audit(conn,owner,'encounter.ended',{'encounter_id':eid,'state_hash':digest(state)})
            return self._projection(conn,self._encounter(conn,eid,owner))

    def retry(self,eid,owner):
        with self.db(True) as conn:
            row=self._encounter(conn,eid,owner)
            if json.loads(row['state'])['status']!='ended': raise Problem(409,'Finish the encounter before retrying.')
            new_id='enc_'+uuid.uuid4().hex
            state=new_state(json.loads(row['snapshot']))
            conn.execute('INSERT INTO encounters VALUES(?,?,?,?,?,?,?,?,?,?)',
                         (new_id,owner,row['case_id'],row['snapshot'],row['case_hash'],row['case_revision'],canonical(state),1,now(),eid))
            self.audit(conn,owner,'encounter.retried',{'encounter_id':new_id,'parent_id':eid})
        return self.get_encounter(new_id,owner)

    def history(self,owner,faculty=False):
        with self.db() as conn:
            rows=conn.execute('SELECT * FROM encounters '+('' if faculty else 'WHERE owner=? ')+'ORDER BY created_at DESC',() if faculty else (owner,)).fetchall()
        results=[]
        for row in rows:
            case,state=json.loads(row['snapshot']),json.loads(row['state'])
            score=debrief(case,state)['coverage_percent'] if state['status']=='ended' else None
            results.append({'id':row['id'],'title':case['title'],'patient':case['patient']['name'],
                            'created_at':row['created_at'],'status':state['status'],'turns':state['turn'],
                            'coverage_percent':score,'case_hash':row['case_hash'],'parent_id':row['parent_id']})
        return results

    def export(self,eid,owner,faculty=False):
        with self.db() as conn:
            row=self._encounter(conn,eid,owner,faculty)
            state=json.loads(row['state'])
            if state['status']!='ended': raise Problem(409,'End the encounter before exporting its teaching record.')
            case=json.loads(row['snapshot'])
            if not faculty:
                case['facts']=[f for f in case['facts'] if f['disclosure']!='faculty_only']
                case['patient']={k:case['patient'].get(k,'') for k in ('name','age','pronouns')}
            return {'product':'Verity Encounter','synthetic':True,'exported_at':now(),
                    'encounter_id':eid,'case_revision':row['case_revision'],'case_hash':row['case_hash'],
                    'case_snapshot':case,'export_snapshot_hash':digest(case),'snapshot_redacted':not faculty,
                    'hash_note':'case_hash identifies the full approved snapshot; export_snapshot_hash verifies this exported view.',
                    'state':state,'debrief':debrief(case,state)}

    def add_review(self,eid,actor,reviewer,note):
        if not valid_text(reviewer,120) or not valid_text(note,3000): raise Problem(422,'Enter a reviewer and a note.')
        with self.db(True) as conn:
            row=self._encounter(conn,eid,actor,True)
            state=json.loads(row['state'])
            if state['status']!='ended': raise Problem(409,'Review is available after the encounter ends.')
            state['review']={'reviewer':reviewer,'note':note,'at':now(),'scope':'Faculty annotation; automated observations are not overwritten.'}
            conn.execute('UPDATE encounters SET state=?,revision=revision+1 WHERE id=?',(canonical(state),eid))
            self.audit(conn,actor,'encounter.reviewed',{'encounter_id':eid,'review':state['review']})
        return self.get_encounter(eid,actor,True)

    def upload(self,cid,fid,name,content_b64,revision,actor):
        if not valid_text(name,120) or '/' in name or '\\' in name or any(ord(c)<32 for c in name): raise Problem(422,'Use a plain filename.')
        if not isinstance(content_b64,str) or len(content_b64)>2_800_000: raise Problem(413,'Attachment limit is 2 MB.')
        try: content=base64.b64decode(content_b64,validate=True)
        except (ValueError,TypeError): raise Problem(422,'Invalid attachment encoding.')
        if not content or len(content)>2*1024*1024: raise Problem(413,'Attachment must contain 1 byte–2 MB.')
        suffix=Path(name).suffix.lower()
        mimes={'.pdf':('application/pdf',b'%PDF-'),'.png':('image/png',b'\x89PNG\r\n\x1a\n'),'.jpg':('image/jpeg',b'\xff\xd8\xff'),'.jpeg':('image/jpeg',b'\xff\xd8\xff'),'.txt':('text/plain',None)}
        if suffix not in mimes: raise Problem(422,'Only PDF, PNG, JPEG and UTF-8 text reports are accepted.')
        mime,magic=mimes[suffix]
        if magic and not content.startswith(magic): raise Problem(422,'File signature does not match its extension.')
        if suffix=='.txt':
            try: content.decode('utf-8')
            except UnicodeDecodeError: raise Problem(422,'Text reports must be UTF-8.')
        aid='asset_'+uuid.uuid4().hex
        sha=hashlib.sha256(content).hexdigest()
        with self.db(True) as conn:
            row=self._case(conn,cid)
            if revision!=row['revision']: raise Problem(409,'Draft changed. Reload before attaching.')
            case=json.loads(row['draft'])
            fact=next((f for f in case.get('facts',[]) if f.get('id')==fid),None)
            if not fact: raise Problem(422,'Choose a fact in this case.')
            if len(fact.get('attachment_ids',[]))>=8: raise Problem(422,'A fact can contain up to 8 attachments.')
            conn.execute('INSERT INTO artifacts VALUES(?,?,?,?,?,?,?)',(aid,cid,fid,name,mime,sha,content))
            fact.setdefault('attachment_ids',[]).append(aid)
            conn.execute('UPDATE cases SET draft=?,revision=revision+1,updated_at=? WHERE id=?',(canonical(case),now(),cid))
            self.audit(conn,actor,'artifact.attached',{'case_id':cid,'fact_id':fid,'id':aid,'sha256':sha})
        return self.get_case(cid,True)

    def artifact(self,aid,owner,eid=None,faculty=False):
        with self.db() as conn:
            artifact=conn.execute('SELECT * FROM artifacts WHERE id=?',(aid,)).fetchone()
            if not artifact: raise Problem(404,'Attachment not found.')
            if not faculty:
                if not eid: raise Problem(404,'Attachment not found.')
                row=self._encounter(conn,eid,owner)
                case,state=json.loads(row['snapshot']),json.loads(row['state'])
                allowed=any(f['id'] in state['revealed'] and aid in f.get('attachment_ids',[]) for f in case['facts'])
                if not allowed: raise Problem(404,'Attachment not found.')
            return dict(artifact)

    def ensure_topics(self, queries):
        stamp = now()
        with self.db(write=True) as conn:
            for query in queries:
                if not valid_text(query, 300):
                    continue
                conn.execute(
                    'INSERT OR IGNORE INTO literature_topics(query,retstart,indexed_count,status,last_error,updated_at) VALUES(?,?,?,?,?,?)',
                    (query.strip(), 0, 0, 'pending', None, stamp),
                )

    def next_topic(self):
        with self.db() as conn:
            row = conn.execute(
                "SELECT * FROM literature_topics WHERE status IN ('pending','active') ORDER BY updated_at, query LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    def save_topic(self, query, retstart, indexed_count, status, last_error=None):
        with self.db(write=True) as conn:
            conn.execute(
                'UPDATE literature_topics SET retstart=?, indexed_count=?, status=?, last_error=?, updated_at=? WHERE query=?',
                (retstart, indexed_count, status, last_error, now(), query),
            )

    def enqueue_inbox(self, query, records):
        stamp = now()
        added = 0
        with self.db(write=True) as conn:
            for rec in records:
                if not isinstance(rec, dict) or not str(rec.get('pmid', '')).isdigit():
                    continue
                conn.execute(
                    'INSERT OR IGNORE INTO literature_inbox(pmid,query,payload,found_at) VALUES(?,?,?,?)',
                    (str(rec['pmid']), query, canonical(rec), stamp),
                )
                if conn.execute('SELECT changes()').fetchone()[0]:
                    added += 1
        return added

    def take_inbox(self, limit=20):
        limit = max(1, min(int(limit), 50))
        with self.db(write=True) as conn:
            rows = conn.execute('SELECT pmid, query, payload FROM literature_inbox ORDER BY found_at LIMIT ?', (limit,)).fetchall()
            items = [{'pmid': r['pmid'], 'query': r['query'], 'record': json.loads(r['payload'])} for r in rows]
            conn.executemany('DELETE FROM literature_inbox WHERE pmid=? AND query=?', [(i['pmid'], i['query']) for i in items])
        return items

    def harvest_status(self):
        with self.db() as conn:
            inbox = conn.execute('SELECT COUNT(*) FROM literature_inbox').fetchone()[0]
            topics = [dict(r) for r in conn.execute('SELECT query, retstart, indexed_count, status, last_error, updated_at FROM literature_topics ORDER BY query').fetchall()]
        return {'inbox': inbox, 'topics': topics}

    def match_literature(self, question, limit=3):
        """Rank stored PubMed records against a clinician question. Does not author patient speech."""
        stop = {'what','when','where','which','that','this','with','from','have','does','your','about','tell','more','been','they','them','were','their','into','would','could','should','please'}
        tokens = {part for part in normalize(question).split() if len(part) > 3 and part not in stop}
        if not tokens:
            return []
        with self.db() as conn:
            rows = conn.execute('SELECT pmid,title,journal,year,url,publication_types,queries FROM literature').fetchall()
        ranked = []
        for row in rows:
            types = json.loads(row['publication_types'] or '[]')
            queries = json.loads(row['queries'] or '[]')
            blob = normalize(' '.join([row['title'], row['journal'] or '', ' '.join(queries), ' '.join(types)]))
            overlap = len(tokens & set(blob.split()))
            if not overlap:
                continue
            if any('guideline' in t.lower() for t in types):
                overlap += 0.5
            ranked.append((overlap, {
                'pmid': row['pmid'], 'title': row['title'], 'journal': row['journal'], 'year': row['year'],
                'url': row['url'],
                'kind': 'Guideline' if any('guideline' in t.lower() for t in types) else ('Review' if any('review' in t.lower() for t in types) else 'Publication'),
            }))
        ranked.sort(key=lambda item: (-item[0], item[1]['pmid']))
        return [item[1] for item in ranked[: max(1, min(int(limit), 5))]]

    def remember_literature(self, query, records, actor):
        if not isinstance(records, list):
            raise Problem(422, 'Literature records must be a list.')
        stamp = now()
        with self.db(write=True) as conn:
            stored = []
            for rec in records:
                if not isinstance(rec, dict) or not valid_text(str(rec.get('pmid', '')), 20):
                    continue
                pmid = str(rec['pmid']).strip()
                if not pmid.isdigit():
                    continue
                title = str(rec.get('title') or 'Untitled PubMed record')[:500]
                journal = str(rec.get('journal') or '')[:300]
                year = str(rec.get('year') or '')[:8]
                types = rec.get('publication_types') if isinstance(rec.get('publication_types'), list) else []
                types = [str(t)[:80] for t in types if isinstance(t, str)][:8]
                url = str(rec.get('url') or f'https://pubmed.ncbi.nlm.nih.gov/{pmid}/')[:300]
                row = conn.execute('SELECT queries FROM literature WHERE pmid=?', (pmid,)).fetchone()
                if row:
                    queries = json.loads(row['queries'])
                    if query not in queries:
                        queries.append(query)
                    conn.execute(
                        'UPDATE literature SET title=?, journal=?, year=?, publication_types=?, url=?, queries=?, last_seen=? WHERE pmid=?',
                        (title, journal, year, json.dumps(types), url, json.dumps(queries), stamp, pmid),
                    )
                else:
                    conn.execute(
                        'INSERT INTO literature(pmid,title,journal,year,publication_types,url,queries,first_seen,last_seen) VALUES(?,?,?,?,?,?,?,?,?)',
                        (pmid, title, journal, year, json.dumps(types), url, json.dumps([query]), stamp, stamp),
                    )
                stored.append(pmid)
            if stored:
                self.audit(conn, actor, 'literature_store', {'query': query, 'pmids': stored})
        return self.list_literature()

    def list_literature(self):
        with self.db() as conn:
            rows = conn.execute('SELECT * FROM literature ORDER BY last_seen DESC, pmid DESC LIMIT 500').fetchall()
            journals = conn.execute(
                'SELECT journal, COUNT(*) AS n FROM literature WHERE journal != "" GROUP BY journal ORDER BY n DESC, journal LIMIT 100'
            ).fetchall()
        records = []
        for row in rows:
            types = json.loads(row['publication_types'])
            records.append({
                'pmid': row['pmid'], 'title': row['title'], 'journal': row['journal'], 'year': row['year'],
                'publication_types': types, 'url': row['url'], 'queries': json.loads(row['queries']),
                'first_seen': row['first_seen'], 'last_seen': row['last_seen'],
                'kind': 'Guideline' if any('guideline' in t.lower() for t in types) else ('Review' if any('review' in t.lower() for t in types) else 'Publication'),
            })
        return {
            'records': records,
            'journals': [{'journal': r['journal'], 'count': r['n']} for r in journals],
            'stored': len(records),
            'limitation': 'Local store of PubMed records retrieved in this prototype. Not a complete corpus of journals, guidelines, or clinical data. Full article text is not stored.',
            'harvest': self.harvest_status(),
        }

    def analytics(self):
        with self.db() as conn: rows=conn.execute('SELECT snapshot,state,case_id FROM encounters').fetchall()
        gaps={}
        ended=0
        for row in rows:
            state=json.loads(row['state']); ended+=state['status']=='ended'
            for q in state['unknown_queries']:
                key=(row['case_id'],q['text'])
                gaps[key]=gaps.get(key,0)+1
        return {'encounters':len(rows),'completed':ended,
                'case_gaps':[{'case_id':key[0],'question':key[1],'count':value} for key,value in sorted(gaps.items(),key=lambda p:-p[1])],
                'note':'Unmatched questions may indicate router limitations, not missing clinical content.'}
