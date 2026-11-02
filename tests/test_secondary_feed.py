import json
import tempfile
import unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from numbers4_agent.secondary_feed import refresh, audit_related, REPOS, RELATED,validate_pair,parse_csv,parse_json
from numbers4_agent.historical_archive import _git_blob_sha1

NOW=datetime(2026,11,2,13,30,tzinfo=timezone(timedelta(hours=9)))
REVS=['a'*40,'b'*40]
CSV_HEADER='draw_no,draw_date,winning_number,digit1,digit2,digit3,digit4\n'
ROWS=[('1994-10-07','1149'),('1994-10-14','7921'),('1994-10-21','0097'),('1994-10-28','0171')]

def primary(rows):
    return (CSV_HEADER+''.join(f'{i},{d},{v},{",".join(v)}\n' for i,(d,v) in enumerate(rows,1))).encode()

def secondary(rows):
    return json.dumps([[i,v] for i,(_,v) in enumerate(rows,1)]).encode()

def fake_fetch(rows1,rows2):
    def fetch(url):
        for i,(owner,repo,path) in enumerate(REPOS):
            if url==f'https://api.github.com/repos/{owner}/{repo}/commits/main':
                return json.dumps({'sha':REVS[i]}).encode()
            if url==f'https://raw.githubusercontent.com/{owner}/{repo}/{REVS[i]}/{path}':
                return primary(rows1) if i==0 else secondary(rows2)
        raise RuntimeError('unlisted URL: '+url)
    return fetch

class SecondaryFeedTests(unittest.TestCase):
    def fixture(self):
        temp=tempfile.TemporaryDirectory();root=Path(temp.name)
        (root/'data').mkdir()
        (root/'data/historical_results.csv').write_text('round,draw_date,winning_number\n'+
            ''.join(f'{i},{d},{v}\n' for i,(d,v) in enumerate(ROWS[:3],1)))
        raw=(root/'data/historical_results.csv').read_bytes()
        provenance={
          'version':'numbers4-historical-archive-v1',
          'status':'secondary_public_mirrors_agree_not_officially_verified',
          'officially_verified':False,'forecast_grading_authorized':False,
          'source_independence_not_established':True,
          'git_blob_sha1':_git_blob_sha1(raw),
          'record_count':3,'first_round':1,'last_round':3,
          'first_draw_date':'1994-10-07','last_draw_date':'1994-10-21',
          'latest_number':'0097',
          'public_source_revisions':[
            {'url':'https://github.com/hazimekom/numbers4-api',
             'commit_sha':'a'*40,'blob_sha':'c'*40},
            {'url':'https://github.com/kodai721229/kujilab',
             'commit_sha':'b'*40,'blob_sha':'d'*40}
          ],
        }
        (root/'data/historical_archive_provenance.json').write_text(json.dumps(provenance))
        return temp,root

    def test_append_only_public_mirror_agreement(self):
        tmp,root=self.fixture()
        with tmp:
            result=refresh(root,now=NOW,fetch=fake_fetch(ROWS,ROWS))
            self.assertEqual(result['status'],'appended_secondary_history_not_officially_verified')
            self.assertEqual(result['new_rows'],1)
            self.assertIn('4,1994-10-28,0171', (root/'data/historical_results.csv').read_text())
            meta=json.loads((root/'data/historical_archive_provenance.json').read_text())
            self.assertFalse(meta['officially_verified'])
            self.assertFalse(meta['forecast_grading_authorized'])
            self.assertTrue(meta['source_independence_not_established'])
            second=refresh(root,now=NOW,fetch=fake_fetch(ROWS,ROWS))
            self.assertEqual(second['status'],'validated_no_new_draws')
            self.assertEqual(second['new_rows'],0)

    def test_changing_1994_history_is_a_hard_error(self):
        tmp,root=self.fixture()
        with tmp:
            former=(root/'data/historical_results.csv').read_bytes()
            with self.assertRaisesRegex(ValueError,'rewritten'):
                refresh(root,now=NOW,fetch=fake_fetch(
                    [(ROWS[0][0],'1148'),*ROWS[1:]],[(ROWS[0][0],'1148'),*ROWS[1:]]))
            self.assertEqual((root/'data/historical_results.csv').read_bytes(),former)

    def test_missing_corresponding_number_rejected(self):
        tmp,root=self.fixture()
        with tmp:
            with self.assertRaisesRegex(ValueError,'disagree'):
                refresh(root,now=NOW,fetch=fake_fetch(ROWS, [*ROWS[:3],(ROWS[3][0],'9999')]))
            self.assertNotIn('\n4,', (root/'data/historical_results.csv').read_text())

    def test_mirror_outage_preserves_history(self):
        tmp,root=self.fixture()
        with tmp:
            current=(root/'data/historical_results.csv').read_bytes()
            r=refresh(root,now=NOW,fetch=lambda _: (_ for _ in ()).throw(ConnectionError('offline')))
            self.assertEqual(r['status'],'network_unavailable_old_archive_preserved')
            self.assertEqual((root/'data/historical_results.csv').read_bytes(),current)

    def test_malformed_number_and_future_date_are_rejected(self):
        broken=primary(ROWS).decode().replace('0097,0,0,9,7','0098,0,0,9,7')
        with self.assertRaisesRegex(ValueError,'digit columns mismatch'):
            parse_csv(broken.encode())
        with self.assertRaisesRegex(ValueError,'secondary mirrors disagree'):
            validate_pair(parse_csv(primary([('2026-11-03','0001')])),[(1,'0001')],NOW.date())
        with self.assertRaisesRegex(ValueError,'secondary source JSON invalid'):
            parse_json(b'[[1,"abc"]]')

    def test_safe_related_source_audit_no_execution_or_promotion(self):
        a=audit_related(now=NOW,fetch=lambda url: b'<html><body>'+b'read-only-'*15+b'</body></html>')
        self.assertEqual(len(a['topics']),len(RELATED))
        self.assertEqual(a['status'],'rule_change_requires_review')
        self.assertEqual(a['rule_sources_consistent'],0)
        self.assertEqual(a['rule_sources_changed'],3)
        self.assertFalse(a['official_draw_result_verified_by_this_audit'])
        self.assertFalse(a['official_payouts_verified_by_this_audit'])
        self.assertFalse(a['lottery_predictive_improvement_confirmed'])
        self.assertFalse(a['automatic_external_code_execution'])

if __name__=='__main__':unittest.main()
