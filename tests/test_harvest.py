import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from verity.harvest import FinderAgent, LoaderAgent, run_once
from verity.service import Service

class HarvestAgentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.s=Service(Path(self.temp.name)/'harvest.db')
    def tearDown(self):self.temp.cleanup()

    def test_finder_queues_and_loader_stores(self):
        record={'pmid':'12345678','title':'Indexed guideline','journal':'Example Journal','year':'2024','publication_types':['Practice Guideline'],'url':'https://pubmed.ncbi.nlm.nih.gov/12345678/'}
        with patch('verity.harvest.search_pubmed', return_value={'query':'fatigue','count':1,'records':[record]}):
            found=FinderAgent(self.s, pause=0).run(['fatigue'], 8)
        self.assertEqual(1, found['queued'])
        self.assertEqual(1, self.s.harvest_status()['inbox'])
        loaded=LoaderAgent(self.s).run(8)
        self.assertEqual(1, loaded['loaded'])
        library=self.s.list_literature()
        self.assertEqual(1, library['stored'])
        self.assertEqual('12345678', library['records'][0]['pmid'])
        self.assertEqual(0, library['harvest']['inbox'])

    def test_run_once_uses_both_agents_and_keeps_a_cap(self):
        records=[{'pmid':str(10000000+i),'title':f'Title {i}','journal':'Journal','year':'2023','publication_types':['Journal Article'],'url':f'https://pubmed.ncbi.nlm.nih.gov/{10000000+i}/'} for i in range(3)]
        with patch('verity.harvest.search_pubmed', return_value={'query':'penicillin allergy','count':3,'records':records}):
            result=run_once(self.s, ['penicillin allergy'], 2)
        self.assertLessEqual(result['finder']['queued'], 2)
        self.assertLessEqual(result['loader']['loaded'], 2)
        self.assertIn('not all journals', result['limitation'].lower())
