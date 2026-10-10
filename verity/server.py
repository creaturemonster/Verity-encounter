"""Demonstration server. Loopback by default; container bind and extra hosts are opt-in."""
from __future__ import annotations
import argparse
import hmac
import json
import mimetypes
import os
import re
import secrets
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, quote
from .engine import SIGNAL_LABELS, validate_case
from .literature import search_pubmed
from .service import Service, Problem

ROOT = Path(__file__).resolve().parents[1]


def load_env_file(path: Path) -> None:
    """Load KEY=value pairs from a local .env file without overriding the process environment."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in '"\'':
            value = value[1:-1]
        os.environ[key] = value

def host_name(value):
    value=(value or '').strip().lower()
    if value.startswith('['):
        end=value.find(']')
        return value[1:end] if end>1 else ''
    return value.split(':',1)[0]

def allowed_hosts_from_env():
    hosts={'127.0.0.1','localhost','::1'}
    for item in os.environ.get('VERITY_ALLOWED_HOSTS','').split(','):
        item=item.strip().lower()
        if item: hosts.add(item)
    return hosts

def env_int(name, default):
    raw=os.environ.get(name)
    if raw is None or not str(raw).strip(): return default
    try: return int(str(raw).strip())
    except ValueError: raise SystemExit(f'{name} must be an integer.')

class DemoServer(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self, address, service, faculty_password, allowed_hosts=None, behind_proxy=False, cookie_secure=False):
        self.service=service
        self.faculty_password=faculty_password
        self.sessions={}
        self.login_attempts={}
        self.lock=threading.RLock()
        self.allowed_hosts=set(allowed_hosts) if allowed_hosts is not None else {'127.0.0.1','localhost','::1'}
        self.behind_proxy=behind_proxy
        self.cookie_secure=cookie_secure
        super().__init__(address, Handler)

class Handler(BaseHTTPRequestHandler):
    server_version='VerityLocal/1.0'
    protocol_version='HTTP/1.1'

    def log_message(self, fmt, *args):
        # Log only methods/status, never question text, passwords or credentials.
        if os.environ.get('VERITY_QUIET')!='1': super().log_message(fmt,*args)

    def _session(self):
        cookie=SimpleCookie()
        try: cookie.load(self.headers.get('Cookie',''))
        except Exception: pass
        token=cookie.get('verity_session')
        token=token.value if token else ''
        with self.server.lock:
            session=self.server.sessions.get(token)
            if session and session['expires']>time.time():
                self.token=token; return session
            token=secrets.token_urlsafe(32)
            session={'owner':secrets.token_hex(16),'role':'learner','csrf':secrets.token_urlsafe(32),'expires':time.time()+12*3600}
            self.server.sessions[token]=session
            self.new_cookie=token
            self.token=token
            # Bound stale session growth in this single-machine demonstration.
            for key in list(self.server.sessions):
                if self.server.sessions[key]['expires']<time.time(): del self.server.sessions[key]
            return session

    def _send(self,status,payload,content_type='application/json; charset=utf-8',headers=None):
        if isinstance(payload,(dict,list)):
            payload=json.dumps(payload,ensure_ascii=False).encode('utf-8')
        elif isinstance(payload,str): payload=payload.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type',content_type)
        self.send_header('Content-Length',str(len(payload)))
        if self.close_connection: self.send_header('Connection','close')
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('X-Frame-Options','DENY')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        if getattr(self,'new_cookie',None):
            cookie=f'verity_session={self.new_cookie}; Path=/; HttpOnly; SameSite=Strict; Max-Age=43200'
            if self.server.cookie_secure: cookie+='; Secure'
            self.send_header('Set-Cookie',cookie)
            self.new_cookie=None
        for key,value in (headers or {}).items(): self.send_header(key,value)
        self.end_headers()
        if self.command!='HEAD': self.wfile.write(payload)

    def _body(self):
        try: length=int(self.headers.get('Content-Length','0'))
        except ValueError: raise Problem(400,'Invalid request length.')
        if not 0<=length<=3_000_000:
            self.close_connection=True
            raise Problem(413,'Request exceeds the 3 MB limit.')
        if self.headers.get_content_type()!='application/json': raise Problem(415,'Send application/json.')
        try: body=json.loads(self.rfile.read(length))
        except (ValueError,UnicodeDecodeError): raise Problem(400,'Request must contain valid JSON.')
        if not isinstance(body,dict): raise Problem(400,'JSON request must be an object.')
        return body

    def _faculty(self):
        if self.session['role']!='faculty': raise Problem(403,'Faculty access is required.')

    def _security(self):
        host=self.headers.get('Host','')
        name=host_name(host)
        path=urlparse(self.path).path.rstrip('/') or '/'
        health_probe=self.server.behind_proxy and self.command in ('GET','HEAD') and path=='/api/health'
        if not health_probe and '*' not in self.server.allowed_hosts and name not in self.server.allowed_hosts:
            raise Problem(403,'This host is not allowed.')
        if self.command not in ('GET','HEAD'):
            origin=self.headers.get('Origin')
            if origin and origin not in ('http://'+host,'https://'+host): raise Problem(403,'Cross-origin write rejected.')
            supplied=self.headers.get('X-CSRF-Token','')
            if not hmac.compare_digest(supplied,self.session['csrf']): raise Problem(403,'Refresh this page before retrying the action.')

    def _bootstrap(self):
        return {'role':self.session['role'],'csrf':self.session['csrf'],
                'engine':'ChatGPT selects topics, phrases a reply from permitted facts, then a separate call reviews grounding' if self.server.service.router else 'Local phrase router · no API key',
                'model_configured':bool(self.server.service.router),'signals':SIGNAL_LABELS,
                'synthetic_only':True,'version':'1.0.0'}

    def _handle(self):
        self.new_cookie=None
        self.session=self._session()
        self._security()
        url=urlparse(self.path)
        path=url.path.rstrip('/') or '/'
        query=parse_qs(url.query)
        svc=self.server.service
        actor=self.session['owner']
        faculty=self.session['role']=='faculty'
        if not path.startswith('/api/'):
            if self.command not in ('GET','HEAD'): raise Problem(405,'Method not allowed.')
            portrait=re.fullmatch(r'/static/patients/([a-z0-9-]+)\.jpg', path)
            if portrait:
                file=ROOT/'static'/'patients'/f'{portrait.group(1)}.jpg'
                if not file.is_file(): raise Problem(404,'Page not found.')
                return self._send(200, file.read_bytes(), 'image/jpeg')
            allowed={'/':ROOT/'static/index.html','/static/app.js':ROOT/'static/app.js','/static/style.css':ROOT/'static/style.css','/favicon.svg':ROOT/'static/favicon.svg'}
            file=allowed.get(path)
            if not file or not file.exists(): raise Problem(404,'Page not found.')
            mime=mimetypes.guess_type(str(file))[0] or 'application/octet-stream'
            return self._send(200,file.read_bytes(),mime+'; charset=utf-8')
        if self.command in ('GET','HEAD'):
            if path=='/api/bootstrap': return self._send(200,self._bootstrap())
            if path=='/api/health': return self._send(200,{'status':'ok','synthetic_only':True})
            if path=='/api/cases': return self._send(200,svc.list_cases(False))
            if path=='/api/history': return self._send(200,svc.history(actor))
            if path=='/api/faculty/cases':
                self._faculty(); return self._send(200,svc.list_cases(True))
            if path=='/api/faculty/history':
                self._faculty(); return self._send(200,svc.history(actor,True))
            if path=='/api/faculty/analytics':
                self._faculty(); return self._send(200,svc.analytics())
            if path=='/api/faculty/audit':
                self._faculty(); return self._send(200,svc.verify_audit())
            if path=='/api/faculty/literature':
                self._faculty(); return self._send(200,svc.list_literature())
            match=re.fullmatch(r'/api/faculty/cases/([\w-]+)',path)
            if match:
                self._faculty(); return self._send(200,svc.get_case(match[1],True))
            match=re.fullmatch(r'/api/encounters/([\w-]+)(/export)?',path)
            if match:
                if match[2]:
                    return self._send(200,svc.export(match[1],actor,faculty),headers={'Content-Disposition':f'attachment; filename="{match[1]}.json"'})
                return self._send(200,svc.get_encounter(match[1],actor,faculty))
            match=re.fullmatch(r'/api/artifacts/([\w-]+)',path)
            if match:
                asset=svc.artifact(match[1],actor,query.get('encounter',[None])[0],faculty)
                # Always download. A PDF/image upload is never an executable app resource.
                return self._send(200,asset['content'],'application/octet-stream',{'Content-Disposition':"attachment; filename*=UTF-8''"+quote(asset['name'])})
            raise Problem(404,'Endpoint not found.')
        if self.command!='POST': raise Problem(405,'Method not allowed.')
        body=self._body()
        if path=='/api/login':
            attempts=self.server.login_attempts.setdefault(self.client_address[0],[])
            attempts[:]=[t for t in attempts if time.time()-t<60]
            if len(attempts)>=5: raise Problem(429,'Too many attempts. Wait one minute.')
            password=body.get('password','')
            if not isinstance(password,str) or not hmac.compare_digest(password,self.server.faculty_password):
                attempts.append(time.time())
                raise Problem(403,'Faculty passphrase is not correct.')
            attempts.clear()
            with self.server.lock:
                self.server.sessions.pop(self.token,None)
                self.token=secrets.token_urlsafe(32)
                self.session={**self.session,'role':'faculty','csrf':secrets.token_urlsafe(32)}
                self.server.sessions[self.token]=self.session
                self.new_cookie=self.token
            return self._send(200,self._bootstrap())
        if path=='/api/logout':
            with self.server.lock:
                self.server.sessions.pop(self.token,None)
                self.token=secrets.token_urlsafe(32)
                self.session={**self.session,'role':'learner','csrf':secrets.token_urlsafe(32)}
                self.server.sessions[self.token]=self.session
                self.new_cookie=self.token
            return self._send(200,self._bootstrap())
        if path=='/api/faculty/validate':
            self._faculty(); return self._send(200,{'errors':validate_case(body.get('case',{}))})
        if path=='/api/faculty/literature':
            self._faculty()
            found=search_pubmed(body.get('query',''))
            found['library']=svc.remember_literature(found.get('query',''),found.get('records',[]),actor)
            return self._send(200,found)
        if path=='/api/faculty/improve':
            self._faculty()
            from .improve import add_approved_cases_from_table, improve_approved_cases
            publish=body.get('publish') is not False
            rounds=body.get('rounds') or 5
            if body.get('add_cases'):
                result=add_approved_cases_from_table(svc,publish=publish,rounds=rounds)
                result['improve']=improve_approved_cases(svc,publish=publish,rounds=rounds)
                return self._send(200,result)
            return self._send(200,improve_approved_cases(svc,publish=publish,rounds=rounds))
        if path=='/api/faculty/cases':
            self._faculty(); return self._send(201,svc.create_case(body.get('case',{}),actor))
        match=re.fullmatch(r'/api/faculty/cases/([\w-]+)(/(approve|upload))?',path)
        if match:
            self._faculty()
            if match[3]=='approve': result=svc.publish(match[1],body.get('revision'),body.get('reviewer',''),actor)
            elif match[3]=='upload': result=svc.upload(match[1],body.get('fact_id'),body.get('name'),body.get('content_base64'),body.get('revision'),actor)
            else: result=svc.save_case(match[1],body.get('case',{}),body.get('revision'),actor)
            return self._send(200,result)
        if path=='/api/encounters': return self._send(201,svc.start(body.get('case_id'),actor))
        match=re.fullmatch(r'/api/encounters/([\w-]+)/(turn|finish|retry|review)',path)
        if match:
            eid,action=match[1],match[2]
            if action=='turn': result=svc.turn(eid,actor,body.get('text'),body.get('idempotency_key'),body.get('revision'))
            elif action=='finish': result=svc.finish(eid,actor,body.get('revision'))
            elif action=='retry': result=svc.retry(eid,actor)
            else:
                self._faculty(); result=svc.add_review(eid,actor,body.get('reviewer',''),body.get('note',''))
            return self._send(200,result)
        raise Problem(404,'Endpoint not found.')

    def dispatch(self):
        try: self._handle()
        except Problem as error:
            if self.command not in ('GET', 'HEAD'): self.close_connection=True
            self._send(error.status,{'error':error.message,'details':error.details})
        except (BrokenPipeError,ConnectionResetError): pass
        except Exception:
            # No debug stack or sensitive values in the browser.
            import traceback
            traceback.print_exc()
            self._send(500,{'error':'Unexpected server error. See the local terminal for diagnostics.'})

    do_GET=dispatch
    do_HEAD=dispatch
    do_POST=dispatch
    do_PUT=dispatch
    do_DELETE=dispatch


def main():
    # Process environment wins, then .env, then the selected config file fills gaps.
    load_env_file(ROOT / '.env')
    pre=argparse.ArgumentParser(add_help=False)
    pre.add_argument('--config',default=os.environ.get('VERITY_CONFIG',''))
    known,_=pre.parse_known_args()
    if known.config:
        config_path=Path(known.config)
        if not config_path.is_file(): raise SystemExit(f'Config file not found: {config_path}')
        load_env_file(config_path)
    parser=argparse.ArgumentParser(description='Verity Encounter — synthetic teaching prototype')
    parser.add_argument('--config',default=known.config,help='Env file for unset variables. Process environment and .env take priority.')
    parser.add_argument('--host',default=os.environ.get('VERITY_HOST','127.0.0.1'),help='Bind address. Containers use 0.0.0.0.')
    parser.add_argument('--port',type=int,default=env_int('VERITY_PORT',8080))
    parser.add_argument('--db',default=os.environ.get('VERITY_DB',str(ROOT/'data/verity.sqlite3')))
    parser.add_argument('--semantic',action='store_true',default=os.environ.get('VERITY_SEMANTIC')=='1',help='Opt in to external model routing; requires OPENAI_API_KEY and OPENAI_MODEL.')
    parser.add_argument('--harvest',action='store_true',default=os.environ.get('VERITY_HARVEST')=='1',help='Run one bounded PubMed citation harvest (finder + loader) in a background thread.')
    args=parser.parse_args()
    router=None
    semantic_note=''
    if args.semantic:
        from .provider import OpenAIRouter, probe_provider
        api_key, model = os.environ.get('OPENAI_API_KEY',''), os.environ.get('OPENAI_MODEL','')
        semantic_note = probe_provider(api_key, model) or ''
        if not semantic_note:
            router=OpenAIRouter(api_key, model)
    supplied=os.environ.get('VERITY_FACULTY_PASSWORD') or ''
    password=supplied or secrets.token_urlsafe(12)
    if len(password)<10: parser.error('Faculty passphrase must be at least 10 characters.')
    if not 1 <= args.port <= 65535: parser.error('Port must be between 1 and 65535.')
    host=args.host.strip()
    if not host: parser.error('Host must not be empty.')
    service=Service(args.db,router)
    try:
        server=DemoServer((host,args.port),service,password,allowed_hosts_from_env(),os.environ.get('VERITY_BEHIND_PROXY')=='1',os.environ.get('VERITY_COOKIE_SECURE')=='1')
    except OSError as error:
        parser.exit(2, f'Cannot listen on {host}:{args.port}: {error}. Try --port 8090.\n')
    shown='127.0.0.1' if host in ('0.0.0.0','::') else host
    print('\nVERITY ENCOUNTER | synthetic demo',flush=True)
    if known.config: print(f'Config: {known.config}',flush=True)
    print(f'Listening: {host}:{args.port}',flush=True)
    print(f'Open: http://{shown}:{args.port}',flush=True)
    if supplied: print('Faculty passphrase: using VERITY_FACULTY_PASSWORD from the environment.',flush=True)
    else: print(f'Faculty passphrase: {password}',flush=True)
    if router:
        print('Mode: ChatGPT selects topics, phrases a reply from permitted facts, and a separate call reviews grounding. Failures keep the approved wording.',flush=True)
    elif semantic_note:
        print('Mode: offline phrase routing. ChatGPT was requested but is not usable yet.',flush=True)
        print(semantic_note,flush=True)
    else:
        print('Mode: offline phrase routing; no external calls',flush=True)
    print('Never enter real patient information. This is not a production server. Ctrl+C stops it.\n',flush=True)
    if args.harvest:
        from .harvest import run_once
        def _harvest():
            try:
                result=run_once(service)
                print(f"Harvest finished. Finder queued {result['finder']['queued']}; loader stored {result['loader']['loaded']}. {result['limitation']}",flush=True)
            except Exception as error:
                print(f'Harvest failed: {error}',flush=True)
        threading.Thread(target=_harvest,daemon=True,name='literature-harvest').start()
        print('Harvest agents started in the background (citation metadata for configured topics only).',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
