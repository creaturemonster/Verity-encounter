import copy
import tempfile
import unittest
from pathlib import Path
from verity.engine import rule_route
from verity.improve import add_approved_cases_from_table, improve_approved_cases, improve_case
from verity.seeds import cases
from verity.service import Service

class ImproveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.s=Service(Path(self.temp.name)/'improve.db');self.cid=self.s.list_cases()[0]['id'];self.owner='learner-a'
    def tearDown(self):self.temp.cleanup()

    def test_unmatched_question_gains_alias_without_rewriting_answer(self):
        case=copy.deepcopy(cases()[0])
        allergies=next(f for f in case['facts'] if f['id']=='allergies')
        original=allergies['answer']
        question='What drugs give you a rash?'
        self.assertFalse(rule_route(question, case['facts']))
        result=improve_case(case,[question],[])
        self.assertTrue(result['added'])
        updated=next(f for f in result['case']['facts'] if f['id']=='allergies')
        self.assertEqual(original, updated['answer'])
        self.assertTrue(rule_route(question, result['case']['facts']))

    def test_recursive_db_improve_republishes_alias_changes(self):
        rec={'pmid':'12345678','title':'Penicillin allergy testing in outpatient care','journal':'Example Journal','year':'2024','publication_types':['Practice Guideline'],'url':'https://pubmed.ncbi.nlm.nih.gov/12345678/'}
        self.s.remember_literature('penicillin allergy',[rec],'faculty')
        e=self.s.start(self.cid,self.owner)
        self.s.turn(e['id'],self.owner,'What drugs give you a rash?','improve-q-001',e['revision'])
        before=next(f for f in self.s.get_case(self.cid,True)['case']['facts'] if f['id']=='allergies')
        report=improve_approved_cases(self.s, publish=True, rounds=3)
        after=self.s.get_case(self.cid,True)
        allergies=next(f for f in after['case']['facts'] if f['id']=='allergies')
        self.assertEqual(before['answer'], allergies['answer'])
        self.assertGreaterEqual(len(allergies['aliases']), len(before['aliases']))
        self.assertEqual(after['revision'], after['published_revision'])
        self.assertTrue(any(item.get('cases_touched') for item in report['rounds']))

    def test_recursive_add_creates_synthetic_approved_case_from_literature_table(self):
        rec={'pmid':'87654321','title':'Fatigue assessment in primary care','journal':'Example Journal','year':'2023','publication_types':['Review'],'url':'https://pubmed.ncbi.nlm.nih.gov/87654321/'}
        self.s.remember_literature('fatigue hypothyroidism',[rec],'faculty')
        before=len(self.s.list_cases())
        report=add_approved_cases_from_table(self.s, publish=True, rounds=3)
        after=self.s.list_cases()
        self.assertEqual(1, report['created'])
        self.assertEqual(before+1, len(after))
        added=next(c for c in after if c['title'].startswith('Library topic:'))
        detail=self.s.get_case(added['id'], True)
        self.assertTrue(detail['case']['synthetic'])
        opening=next(f for f in detail['case']['facts'] if f['id']=='opening')
        self.assertNotIn('Fatigue assessment in primary care', opening['answer'])
        citation=next(f for f in detail['case']['facts'] if f['id']=='pmid87654321')
        self.assertEqual('record', citation['disclosure'])
        self.assertIn('87654321', citation['answer'])
        self.assertEqual(detail['revision'], detail['published_revision'])
