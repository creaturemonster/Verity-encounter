import base64
import copy
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from verity.engine import digest
from verity.seeds import cases
from verity.service import Problem, Service

class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.s=Service(Path(self.temp.name)/'demo.db');self.cid=self.s.list_cases()[0]['id'];self.owner='learner-a'
    def tearDown(self):self.temp.cleanup()
    def start(self):return self.s.start(self.cid,self.owner)
    def upload(self):
        c=self.s.get_case(self.cid,True)
        return self.s.upload(self.cid,'cbc','synthetic.txt',base64.b64encode(b'Synthetic lab report only').decode(),c['revision'],'faculty')
    def test_three_demo_cases(self):self.assertEqual(3,len(self.s.list_cases()))
    def test_seeding_idempotent(self):self.s.seed();self.assertEqual(3,len(self.s.list_cases()))
    def test_unapproved_draft_not_in_student_library(self):
        self.s.create_case(cases()[0],'faculty');self.assertEqual(3,len(self.s.list_cases()));self.assertEqual(4,len(self.s.list_cases(True)))
    def test_unapproved_case_cannot_start(self):
        d=self.s.create_case(cases()[0],'faculty')
        with self.assertRaises(Problem) as c:self.s.start(d['id'],self.owner)
        self.assertEqual(409,c.exception.status)
    def test_public_case_projection_has_no_facts(self):
        text=json.dumps(self.s.get_case(self.cid));self.assertNotIn('penicillin',text);self.assertNotIn('facts',text)
    def test_patient_metadata_is_allowlisted(self):
        d=self.s.get_case(self.cid,True);d['case']['patient']['hidden_secret']='do not leak';d=self.s.save_case(self.cid,d['case'],d['revision'],'faculty');self.s.publish(self.cid,d['revision'],'Reviewer','faculty')
        self.assertNotIn('hidden_secret',json.dumps(self.s.get_case(self.cid)));self.assertNotIn('hidden_secret',json.dumps(self.start()))
    def test_learner_session_contains_only_opening(self):
        e=self.start();text=json.dumps(e);self.assertNotIn('penicillin',text);self.assertNotIn('cbc',text);self.assertNotIn('teaching_note',text)
    def test_encounter_isolated_between_users(self):
        e=self.start()
        with self.assertRaises(Problem) as c:self.s.get_encounter(e['id'],'learner-b')
        self.assertEqual(404,c.exception.status)
    def test_draft_edit_does_not_change_public_version(self):
        d=self.s.get_case(self.cid,True);next(f for f in d['case']['facts'] if f['id']=='allergies')['answer']='A changed answer.';self.s.save_case(self.cid,d['case'],d['revision'],'faculty')
        e=self.start();e=self.s.turn(e['id'],self.owner,'allergies?','question-001',e['revision']);self.assertIn('penicillin',e['messages'][-1]['text'])
    def test_reapproval_does_not_change_active_snapshot(self):
        old=self.start();d=self.s.get_case(self.cid,True);next(f for f in d['case']['facts'] if f['id']=='allergies')['answer']='New approved answer.';d=self.s.save_case(self.cid,d['case'],d['revision'],'faculty');self.s.publish(self.cid,d['revision'],'Reviewer','faculty')
        old=self.s.turn(old['id'],self.owner,'allergies?','question-001',old['revision']);self.assertIn('penicillin',old['messages'][-1]['text'])
        new=self.start();new=self.s.turn(new['id'],self.owner,'allergies?','question-002',new['revision']);self.assertEqual('New approved answer.',new['messages'][-1]['text']);self.assertNotEqual(old['case_hash'],new['case_hash'])
    def test_stale_draft_rejected(self):
        d=self.s.get_case(self.cid,True);self.s.save_case(self.cid,d['case'],d['revision'],'faculty')
        with self.assertRaises(Problem) as c:self.s.save_case(self.cid,d['case'],d['revision'],'faculty')
        self.assertEqual(409,c.exception.status)
    def test_stale_approval_rejected(self):
        d=self.s.get_case(self.cid,True);self.s.save_case(self.cid,d['case'],d['revision'],'faculty')
        with self.assertRaises(Problem):self.s.publish(self.cid,d['revision'],'Reviewer','faculty')
    def test_invalid_case_approval_rejected(self):
        case=cases()[0];case['facts'][0]['answer']='';d=self.s.create_case(case,'faculty')
        with self.assertRaises(Problem) as c:self.s.publish(d['id'],d['revision'],'Reviewer','faculty')
        self.assertEqual(422,c.exception.status)
    def test_duplicate_turn_is_idempotent(self):
        e=self.start();a=self.s.turn(e['id'],self.owner,'allergies?','question-001',1);b=self.s.turn(e['id'],self.owner,'allergies?','question-001',1);self.assertEqual(a,b);self.assertEqual(1,b['turn'])
    def test_same_key_different_question_rejected(self):
        e=self.start();self.s.turn(e['id'],self.owner,'allergies?','question-001',1)
        with self.assertRaises(Problem):self.s.turn(e['id'],self.owner,'sleep?','question-001',2)
    def test_stale_turn_rejected(self):
        e=self.start();self.s.turn(e['id'],self.owner,'allergies?','question-001',1)
        with self.assertRaises(Problem):self.s.turn(e['id'],self.owner,'sleep?','question-002',1)
    def test_concurrent_duplicate_one_turn(self):
        e=self.start()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(lambda _:self.s.turn(e['id'],self.owner,'allergies?','question-001',1),[1,2]))
        self.assertEqual(1,self.s.get_encounter(e['id'],self.owner)['turn']);self.assertEqual(results[0],results[1])
    def test_no_export_while_active(self):
        e=self.start()
        with self.assertRaises(Problem) as c:self.s.export(e['id'],self.owner)
        self.assertEqual(409,c.exception.status)
    def test_finished_export_hash_matches_snapshot(self):
        e=self.start();self.s.finish(e['id'],self.owner,e['revision']);x=self.s.export(e['id'],self.owner);self.assertEqual(x['export_snapshot_hash'],digest(x['case_snapshot']))
    def test_end_idempotent(self):
        e=self.start();a=self.s.finish(e['id'],self.owner,1);b=self.s.finish(e['id'],self.owner,1);self.assertEqual(a,b)
    def test_retry_same_hash_no_prior_disclosures(self):
        e=self.start();e=self.s.turn(e['id'],self.owner,'allergies?','question-001',1);self.s.finish(e['id'],self.owner,e['revision']);retry=self.s.retry(e['id'],self.owner)
        self.assertEqual(e['case_hash'],retry['case_hash']);self.assertEqual(0,retry['elicited_count']);self.assertNotEqual(e['id'],retry['id']);self.assertEqual(e['id'],retry['parent_id'])
    def test_no_retry_active(self):
        with self.assertRaises(Problem):self.s.retry(self.start()['id'],self.owner)
    def test_upload_changes_draft_only(self):
        d=self.upload();self.assertEqual(2,d['revision']);self.assertEqual(1,d['published_revision'])
    def test_unrevealed_asset_forbidden(self):
        d=self.upload();aid=d['artifacts'][0]['id'];self.s.publish(self.cid,d['revision'],'Reviewer','faculty');e=self.start()
        with self.assertRaises(Problem):self.s.artifact(aid,self.owner,e['id'])
    def test_revealed_asset_served_exactly(self):
        d=self.upload();aid=d['artifacts'][0]['id'];self.s.publish(self.cid,d['revision'],'Reviewer','faculty');e=self.start();self.s.turn(e['id'],self.owner,'CBC','question-001',1)
        self.assertEqual(b'Synthetic lab report only',self.s.artifact(aid,self.owner,e['id'])['content'])
    def test_asset_cannot_cross_case(self):
        d=self.upload();aid=d['artifacts'][0]['id'];other=cases()[1];other['facts'][1]['attachment_ids']=[aid]
        with self.assertRaises(Problem):self.s.create_case(other,'faculty')
    def test_asset_uploaded_later_not_added_to_existing_encounter(self):
        e=self.start();d=self.upload();aid=d['artifacts'][0]['id'];self.s.publish(self.cid,d['revision'],'Reviewer','faculty');self.s.turn(e['id'],self.owner,'CBC','question-001',1)
        with self.assertRaises(Problem):self.s.artifact(aid,self.owner,e['id'])
    def test_html_upload_rejected(self):
        with self.assertRaises(Problem):self.s.upload(self.cid,'cbc','attack.html',base64.b64encode(b'<script>bad</script>').decode(),1,'faculty')
    def test_signature_mismatch_rejected(self):
        with self.assertRaises(Problem):self.s.upload(self.cid,'cbc','attack.png',base64.b64encode(b'<html>').decode(),1,'faculty')
    def test_path_traversal_filename_rejected(self):
        with self.assertRaises(Problem):self.s.upload(self.cid,'cbc','../test.txt',base64.b64encode(b'text').decode(),1,'faculty')
    def test_pdf_file_signature_accepted(self):
        d=self.s.upload(self.cid,'cbc','teaching.pdf',base64.b64encode(b'%PDF-1.7\nSynthetic test fixture').decode(),1,'faculty');self.assertEqual('application/pdf',d['artifacts'][0]['mime'])
    def test_annotation_does_not_rewrite_transcript(self):
        e=self.start();ended=self.s.finish(e['id'],self.owner,1);reviewed=self.s.add_review(e['id'],'faculty','Reviewer','Checklist requires contextual interpretation.');self.assertEqual(ended['messages'],reviewed['messages']);self.assertIsNotNone(reviewed['review'])
    def test_review_active_rejected(self):
        with self.assertRaises(Problem):self.s.add_review(self.start()['id'],'faculty','Reviewer','Note')
    def test_clinician_question_uses_stored_literature_without_changing_patient_speech(self):
        rec={'pmid':'12345678','title':'Penicillin allergy testing in outpatient care','journal':'Example Journal','year':'2024','publication_types':['Practice Guideline'],'url':'https://pubmed.ncbi.nlm.nih.gov/12345678/'}
        self.s.remember_literature('penicillin allergy',[rec],'faculty')
        e=self.start();result=self.s.turn(e['id'],self.owner,'Do you have any penicillin allergies?','knowledge-turn-01',e['revision'])
        self.assertTrue(result['knowledge'])
        self.assertEqual('12345678', result['knowledge'][0]['pmid'])
        patient=[m for m in result['messages'] if m['role']=='patient' and m['turn']==result['turn']]
        self.assertTrue(patient)
        self.assertNotIn('Example Journal', patient[0]['text'])
        self.assertNotIn('outpatient care', patient[0]['text'])
    def test_literature_library_stores_pubmed_records(self):
        rec={'pmid':'12345678','title':'A real indexed title','journal':'Example Medical Journal','year':'2024','publication_types':['Practice Guideline'],'url':'https://pubmed.ncbi.nlm.nih.gov/12345678/'}
        first=self.s.remember_literature('fatigue', [rec], 'faculty')
        self.assertEqual(1, first['stored'])
        self.assertEqual('Guideline', first['records'][0]['kind'])
        again=self.s.remember_literature('hypothyroidism', [rec], 'faculty')
        self.assertEqual(1, again['stored'])
        self.assertEqual(['fatigue','hypothyroidism'], again['records'][0]['queries'])
        self.assertEqual(1, len(again['journals']))
    def test_analytics_unmatched_questions(self):
        e=self.start();self.s.turn(e['id'],self.owner,'What is your sodium?','question-001',1);self.assertEqual(1,len(self.s.analytics()['case_gaps']))
    def test_valid_audit_chain(self):self.start();self.assertTrue(self.s.verify_audit()['consistent'])
    def test_audit_mutation_detected(self):
        with self.s.db(True) as conn:conn.execute("UPDATE audit SET payload='{}' WHERE seq=1")
        self.assertFalse(self.s.verify_audit()['consistent'])
    def test_storage_survives_service_restart(self):
        e=self.start();second=Service(self.s.db_path);self.assertEqual(e,second.get_encounter(e['id'],self.owner))
    def test_malformed_draft_returns_structured_error(self):
        with self.assertRaises(Problem) as c:self.s.create_case({'facts':'not-list'},'faculty')
        self.assertEqual(422,c.exception.status)

    def test_student_export_keeps_faculty_only_notes_private(self):
        e=self.start();self.s.finish(e['id'],self.owner,1);x=self.s.export(e['id'],self.owner)
        self.assertNotIn('teaching_note',json.dumps(x));self.assertTrue(x['snapshot_redacted'])
    def test_faculty_export_has_complete_snapshot(self):
        e=self.start();self.s.finish(e['id'],self.owner,1);x=self.s.export(e['id'],'faculty',True)
        self.assertIn('teaching_note',json.dumps(x));self.assertEqual(x['case_hash'],x['export_snapshot_hash'])
