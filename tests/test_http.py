import base64
import http.cookiejar
import json
import os
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from verity.server import DemoServer, allowed_hosts_from_env
from verity.service import Service
from verity.seeds import cases

class Client:
    def __init__(self,url):
        self.url=url;self.csrf='';self.opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        status,result,_=self.call('/api/bootstrap');self.csrf=result['csrf']
    def call(self,path,body=None,headers=None):
        head={} if body is None else {'Content-Type':'application/json','X-CSRF-Token':self.csrf}
        head.update(headers or {})
        req=urllib.request.Request(self.url+path,data=None if body is None else json.dumps(body).encode(),headers=head)
        try:response=self.opener.open(req,timeout=10)
        except urllib.error.HTTPError as error:response=error
        with response:
            raw=response.read();result=json.loads(raw) if 'application/json' in response.headers.get('Content-Type','') else raw
            return response.status,result,dict(response.headers)
    def login(self):
        status,result,_=self.call('/api/login',{'password':'local-test-passphrase'})
        if status==200:self.csrf=result['csrf']
        return status,result

class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['VERITY_QUIET']='1';cls.temp=tempfile.TemporaryDirectory();cls.service=Service(Path(cls.temp.name)/'http.db')
        cls.server=DemoServer(('127.0.0.1',0),cls.service,'local-test-passphrase')
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start();cls.url='http://127.0.0.1:'+str(cls.server.server_port)
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join();cls.temp.cleanup()
    def setUp(self):self.client=Client(self.url);self.cid=self.service.list_cases()[0]['id']
    def start(self):return self.client.call('/api/encounters',{'case_id':self.cid})[1]
    def test_health_and_no_stack_metadata(self):
        status,result,_=self.client.call('/api/health');self.assertEqual(200,status);self.assertTrue(result['synthetic_only'])
    def test_security_headers(self):
        _,_,headers=self.client.call('/');self.assertEqual('nosniff',headers['X-Content-Type-Options']);self.assertIn("object-src 'none'",headers['Content-Security-Policy'])
    def test_index_has_no_inline_script(self):
        _,html,_=self.client.call('/');self.assertNotIn(b'<script>',html);self.assertIn(b'/static/app.js',html)
    def test_unprivileged_faculty_list_denied(self):
        self.assertEqual(403,self.client.call('/api/faculty/cases')[0])
    def test_unprivileged_literature_denied(self):
        self.assertEqual(403,self.client.call('/api/faculty/literature')[0])
        self.assertEqual(403,self.client.call('/api/faculty/literature',{'query':'fatigue'})[0])
    def test_faculty_literature_library_starts_empty(self):
        self.client.login();status,result,_=self.client.call('/api/faculty/literature')
        self.assertEqual(200,status);self.assertEqual(0,result['stored']);self.assertEqual([],result['records'])
    def test_unprivileged_publish_denied(self):
        self.assertEqual(403,self.client.call('/api/faculty/cases/'+self.cid+'/approve',{'reviewer':'Impostor','revision':1})[0])
    def test_unprivileged_create_denied(self):
        self.assertEqual(403,self.client.call('/api/faculty/cases',{'case':cases()[0]})[0])
    def test_missing_csrf_rejected(self):
        self.assertEqual(403,self.client.call('/api/encounters',{'case_id':self.cid},{'X-CSRF-Token':''})[0])
    def test_cross_origin_rejected(self):
        self.assertEqual(403,self.client.call('/api/encounters',{'case_id':self.cid},{'Origin':'https://evil.example'})[0])
    def test_dns_rebinding_host_rejected(self):
        self.assertEqual(403,self.client.call('/api/health',headers={'Host':'evil.example'})[0])
    def test_login_rotates_csrf(self):
        old=self.client.csrf;self.assertEqual(200,self.client.login()[0]);self.assertNotEqual(old,self.client.csrf)
    def test_login_preserves_owned_encounters(self):
        e=self.start();self.client.login();self.assertEqual(200,self.client.call('/api/encounters/'+e['id'])[0])
    def test_logout_removes_privilege(self):
        self.client.login();status,context,_=self.client.call('/api/logout',{});self.client.csrf=context['csrf'];self.assertEqual(403,self.client.call('/api/faculty/cases')[0])
    def test_cross_user_encounter_not_found(self):
        e=self.start();other=Client(self.url);self.assertEqual(404,other.call('/api/encounters/'+e['id'])[0])
    def test_cross_user_turn_not_found(self):
        e=self.start();other=Client(self.url);self.assertEqual(404,other.call('/api/encounters/'+e['id']+'/turn',{'text':'allergies','idempotency_key':'test-key-001','revision':1})[0])
    def test_public_api_has_no_answers(self):
        _,result,_=self.client.call('/api/cases');self.assertNotIn('penicillin',json.dumps(result))
    def test_live_http_progressive_disclosure(self):
        e=self.start();self.assertEqual(1,len(e['chart']));status,result,_=self.client.call('/api/encounters/'+e['id']+'/turn',{'text':'allergies?','idempotency_key':'test-key-001','revision':1});self.assertEqual(200,status);self.assertEqual(2,len(result['chart']));self.assertIn('penicillin',json.dumps(result))
    def test_live_http_finish_and_redacted_export(self):
        e=self.start();self.assertEqual(409,self.client.call('/api/encounters/'+e['id']+'/export')[0]);self.client.call('/api/encounters/'+e['id']+'/finish',{'revision':1});status,result,_=self.client.call('/api/encounters/'+e['id']+'/export');self.assertEqual(200,status);self.assertNotIn('teaching_note',json.dumps(result))
    def test_faculty_new_case_can_run_without_code(self):
        self.client.login();case=cases()[1];case['title']='Live HTTP-created patient';case['patient']['name']='Completely New Fiction'
        status,created,_=self.client.call('/api/faculty/cases',{'case':case});self.assertEqual(201,status)
        status,_,_=self.client.call('/api/faculty/cases/'+created['id']+'/approve',{'revision':created['revision'],'reviewer':'Local demo reviewer'});self.assertEqual(200,status)
        status,e,_=self.client.call('/api/encounters',{'case_id':created['id']});self.assertEqual(201,status);self.assertEqual('Completely New Fiction',e['patient']['name'])
    def test_no_arbitrary_file_serving(self):
        self.assertEqual(404,self.client.call('/verity/service.py')[0]);self.assertEqual(404,self.client.call('/static/../run.py')[0])
    def test_malformed_draft_does_not_crash_http(self):
        self.client.login();status,result,_=self.client.call('/api/faculty/cases',{'case':{'facts':None}});self.assertEqual(422,status);self.assertIn('error',result)
    def test_typed_array_body_error(self):
        request=urllib.request.Request(self.url+'/api/login',data=b'[]',headers={'Content-Type':'application/json','X-CSRF-Token':self.client.csrf})
        with self.assertRaises(urllib.error.HTTPError):self.client.opener.open(request)
    def test_faculty_literature_empty_query_rejected(self):
        self.client.login();self.assertEqual(422,self.client.call('/api/faculty/literature',{'query':''})[0])
    def test_upload_is_download_not_executable_resource(self):
        self.client.login();case=self.service.get_case(self.cid,True)
        status,draft,_=self.client.call('/api/faculty/cases/'+self.cid+'/upload',{'fact_id':'cbc','name':'lab.txt','content_base64':base64.b64encode(b'synthetic test').decode(),'revision':case['revision']});self.assertEqual(200,status)
        aid=draft['artifacts'][-1]['id'];status,data,headers=self.client.call('/api/artifacts/'+aid);self.assertEqual(200,status);self.assertEqual('application/octet-stream',headers['Content-Type']);self.assertIn('attachment',headers['Content-Disposition'])

class DeploymentHostTests(unittest.TestCase):
    def setUp(self):
        self._saved={key:os.environ.get(key) for key in ('VERITY_ALLOWED_HOSTS','VERITY_BEHIND_PROXY','VERITY_COOKIE_SECURE')}
        self.temp=tempfile.TemporaryDirectory(); self.servers=[]
    def tearDown(self):
        for server,thread in self.servers:
            server.shutdown(); server.server_close(); thread.join()
        self.temp.cleanup()
        for key,value in self._saved.items():
            if value is None: os.environ.pop(key,None)
            else: os.environ[key]=value
    def _start(self):
        service=Service(Path(self.temp.name)/f'{len(self.servers)}.db')
        server=DemoServer(('127.0.0.1',0),service,'local-test-passphrase',allowed_hosts_from_env(),os.environ.get('VERITY_BEHIND_PROXY')=='1',os.environ.get('VERITY_COOKIE_SECURE')=='1')
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        self.servers.append((server,thread))
        return Client('http://127.0.0.1:'+str(server.server_port))
    def test_configured_host_is_accepted(self):
        os.environ['VERITY_ALLOWED_HOSTS']='demo.internal'
        self.assertEqual(200,self._start().call('/api/health',headers={'Host':'demo.internal'})[0])
    def test_unlisted_host_still_rejected(self):
        os.environ['VERITY_ALLOWED_HOSTS']='demo.internal'
        self.assertEqual(403,self._start().call('/api/health',headers={'Host':'evil.example'})[0])
    def test_proxy_health_check_allows_task_address(self):
        os.environ['VERITY_BEHIND_PROXY']='1'
        client=self._start()
        self.assertEqual(200,client.call('/api/health',headers={'Host':'10.0.1.8:8080'})[0])
        self.assertEqual(403,client.call('/',headers={'Host':'10.0.1.8:8080'})[0])
    def test_secure_cookie_is_opt_in(self):
        os.environ['VERITY_COOKIE_SECURE']='1'
        service=Service(Path(self.temp.name)/'cookie.db')
        server=DemoServer(('127.0.0.1',0),service,'local-test-passphrase',cookie_secure=True)
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        self.servers.append((server,thread))
        with urllib.request.urlopen('http://127.0.0.1:'+str(server.server_port)+'/api/bootstrap',timeout=10) as response:
            self.assertIn('Secure',response.headers['Set-Cookie'])
