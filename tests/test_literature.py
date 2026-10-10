import json
import unittest
from unittest.mock import MagicMock, patch
from verity.literature import search_pubmed
from verity.service import Problem

class LiteratureTests(unittest.TestCase):
    def test_empty_query_rejected(self):
        with self.assertRaises(Problem):
            search_pubmed('')

    @patch('verity.literature.urllib.request.urlopen')
    def test_returns_pubmed_records_not_invented_text(self, urlopen):
        search = {'esearchresult': {'idlist': ['12345678'], 'count': '1'}}
        summary = {'result': {'12345678': {
            'title': 'A real indexed title about fatigue',
            'fulljournalname': 'Example Medical Journal',
            'pubdate': '2024 Jan',
            'pubtype': ['Journal Article'],
        }}}
        first = MagicMock(); first.__enter__.return_value.read.return_value = json.dumps(search).encode()
        second = MagicMock(); second.__enter__.return_value.read.return_value = json.dumps(summary).encode()
        urlopen.side_effect = [first, second]
        result = search_pubmed('fatigue')
        self.assertEqual(1, len(result['records']))
        rec = result['records'][0]
        self.assertEqual('12345678', rec['pmid'])
        self.assertEqual('https://pubmed.ncbi.nlm.nih.gov/12345678/', rec['url'])
        self.assertIn('real indexed title', rec['title'])
        self.assertIn('not this synthetic', result['note'])
