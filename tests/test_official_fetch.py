from datetime import datetime
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import URLError, HTTPError

from numbers4_agent.official_fetch import (
    ResultFetchError, parse_mizuhobank, parse_rakuten, sync, _download,
)
from numbers4_agent.sources import JST, reconcile, corroborated_draws
from numbers4_agent.proof import prequential, run
from numbers4_agent.store import load


BANK_OCT = '''<!doctype html><h1>当せん番号案内(ナンバーズ4)</h1>
<table><tr><th>回別</th><td>第7103回</td></tr>
<tr><th>抽せん日</th><td>2026年10月29日</td></tr>
<tr><th>抽せん数字</th><td>2491</td></tr>
<tr><th>回別</th><td>第7104回</td></tr>
<tr><th>抽せん日</th><td>2026年10月30日</td></tr>
<tr><th>抽せん数字</th><td>5805</td></tr></table>'''
RAK_OCT = '''<h1>ナンバーズ4(NUMBERS4) 当せん番号案内</h1>
<table><tr><th>回号</th><td>第7103回</td></tr>
<tr><th>抽せん日</th><td>2026/10/29</td></tr>
<tr><th>当せん番号</th><td>2491</td></tr>
<tr><th>回号</th><td>第7104回</td></tr>
<tr><th>抽せん日</th><td>2026/10/30</td></tr>
<tr><th>当せん番号</th><td>5805</td></tr></table>'''
BANK_ARCHIVE = '''<h1>過去の当せん番号案内(ナンバーズ) </h1>
<table><tr><th>回別</th><th>抽せん日</th><th>ナンバーズ3 抽せん数字</th><th>ナンバーズ4 抽せん数字</th></tr>
<tr><td>第2027回</td><td>2007年2月28日</td><td>172</td><td>0666</td></tr>
<tr><td>第2028回</td><td>2007年3月1日</td><td>378</td><td>0497</td></tr></table>'''

class Response:
    class Headers:
        def get_content_charset(self):
            return 'utf-8'
    headers=Headers()
    def __init__(self, url, content):
        self.url=url
        self.content=content.encode()
    def read(self, maxlen):return self.content[:maxlen]
    def geturl(self):return self.url
    def __enter__(self):return self
    def __exit__(self, *_):return False


def open_mocks(bank=BANK_OCT, rak=RAK_OCT):
    def opener(request, timeout):
        url=request.full_url
        if 'year=2026&month=10' in url:
            return Response(url, bank)
        if '202610/' in url:
            return Response(url, rak)
        raise URLError('not published')
    return opener


class OfficialFetchTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        self.now=datetime(2026, 11, 2, 12, 0, tzinfo=JST)

    def test_website_parsers_preserve_zero_and_ignore_scripts(self):
        official=parse_mizuhobank(BANK_ARCHIVE)
        self.assertEqual(official[0]['winning_number'], '0666')
        self.assertEqual(official[1]['winning_number'], '0497')
        self.assertEqual(parse_mizuhobank(BANK_OCT)[-1]['winning_number'], '5805')
        self.assertEqual(parse_rakuten(RAK_OCT)[-1]['round'],7104)
        with self.assertRaises(ResultFetchError):
            parse_rakuten('<h1>not a lottery site</h1><script>第7104回</script>')
        with self.assertRaises(ResultFetchError):
            parse_mizuhobank('<h1>ナンバーズ4</h1><table><tr><th>回別</th></tr></table>')

    def test_automatic_bank_rakuten_match_is_reconciled_and_idempotent(self):
        summary=sync(self.root, now=self.now, months_back=2, opener=open_mocks())
        self.assertEqual(summary['status'],'verified')
        self.assertEqual(summary['new_verified_rows'],2)
        self.assertEqual(summary['bank_rows'],2)
        self.assertEqual(summary['rakuten_rows'],2)
        self.assertEqual([x['round'] for x in corroborated_draws(self.root)],[7103,7104])
        self.assertTrue(all(x['status']=='auto_verified_two_publishers' for x in corroborated_draws(self.root)))
        self.assertEqual(sync(self.root,now=self.now,months_back=2,opener=open_mocks())['new_verified_rows'],0)
        self.assertEqual(len(load(self.root/'data'/'auto_verified_draws.jsonl')),2)

    def test_single_publisher_is_not_officially_verified(self):
        bad_bank='<h1>ナンバーズ4抽せん数字一覧表</h1><p>JavaScript required</p>'
        status=sync(self.root,now=self.now,months_back=2,opener=open_mocks(bank=bad_bank))
        self.assertEqual(status['status'],'blocked_no_bank_verified_results')
        self.assertEqual(status['new_verified_rows'],0)
        self.assertEqual(corroborated_draws(self.root),[])
        cached=json.loads((self.root/'research'/'historical_unverified.json').read_text())
        self.assertFalse(cached['verified_official'])
        self.assertEqual(len(cached['rows']),2)
        self.assertFalse(run(self.root)['prospective_skill_confirmed'])

    def test_bank_browser_fallback_can_recover_only_explicit_bank_draws(self):
        empty_bank = '<h1>ナンバーズ4抽せん数字一覧表</h1><table><tr><td>回別</td><td></td></tr></table>'
        with patch('numbers4_agent.official_fetch._render_bank_page',
                   return_value=(BANK_OCT, 'a' * 64)) as render:
            summary = sync(self.root, now=self.now, months_back=2,
                           opener=open_mocks(bank=empty_bank), bank_browser_fallback=True)
        self.assertEqual(summary['status'], 'verified')
        self.assertEqual(summary['new_verified_rows'], 2)
        self.assertEqual(summary['bank_rows'], 2)
        self.assertTrue(summary['bank_browser_fallback_enabled'])
        # The browser is also tried when the other month's raw request fails.
        self.assertEqual(render.call_count, 2)
        recorded = load(self.root/'data'/'auto_verified_draws.jsonl')
        self.assertEqual(recorded[0]['bank_response_sha256'], 'a' * 64)

    def test_explicit_http_denial_never_uses_browser_or_retries_months(self):
        ordinary = open_mocks()
        for status in (401, 403, 429):
            with self.subTest(status=status):
                calls = []
                def blocked_raw_bank(request, timeout):
                    if 'www.mizuhobank.co.jp' in request.full_url:
                        calls.append(request.full_url)
                        raise HTTPError(request.full_url, status, 'Denied', None, None)
                    return ordinary(request, timeout)
                with patch('numbers4_agent.official_fetch._render_bank_page') as render:
                    summary = sync(self.root, now=self.now, months_back=2,
                                   opener=blocked_raw_bank, bank_browser_fallback=True)
                render.assert_not_called()
                self.assertEqual(len(calls), 1)
                self.assertEqual(summary['status'], 'blocked_no_bank_verified_results')
                self.assertEqual(summary['new_verified_rows'], 0)
                self.assertEqual(summary['rakuten_rows'], 2)
                self.assertEqual(summary['requests_skipped_after_access_denial'], 1)
                self.assertIn(f'HTTP {status}', summary['publisher_access_denials']['mizuhobank'])
                self.assertFalse((self.root/'data'/'auto_verified_draws.jsonl').exists())

    def test_browser_denial_stops_remaining_bank_months(self):
        ordinary = open_mocks()
        calls = []
        def empty_bank(request, timeout):
            if 'www.mizuhobank.co.jp' in request.full_url:
                calls.append(request.full_url)
                return Response(request.full_url, '<h1>ナンバーズ4</h1>')
            return ordinary(request, timeout)
        from numbers4_agent.official_fetch import PublisherAccessDenied
        with patch('numbers4_agent.official_fetch._render_bank_page',
                   side_effect=PublisherAccessDenied('bank browser request rejected: HTTP 403')) as render:
            summary = sync(self.root, now=self.now, months_back=2,
                           opener=empty_bank, bank_browser_fallback=True)
        self.assertEqual(len(calls), 1)
        render.assert_called_once()
        self.assertEqual(summary['bank_rows'], 0)
        self.assertEqual(summary['rakuten_rows'], 2)
        self.assertEqual(summary['requests_skipped_after_access_denial'], 1)
        self.assertEqual(summary['bank_errors'][0]['code'], 'publisher_access_denied')
        self.assertEqual(summary['bank_errors'][1]['code'], 'skipped_after_access_denial')
        self.assertFalse((self.root/'data'/'auto_verified_draws.jsonl').exists())

    def test_rakuten_denial_does_not_prevent_independent_bank_fetch(self):
        ordinary = open_mocks()
        calls = []
        def blocked_rakuten(request, timeout):
            if 'takarakuji.rakuten.co.jp' in request.full_url:
                calls.append(request.full_url)
                raise HTTPError(request.full_url, 429, 'Rate limited', None, None)
            return ordinary(request, timeout)
        summary = sync(self.root, now=self.now, months_back=2, opener=blocked_rakuten)
        self.assertEqual(len(calls), 1)
        self.assertEqual(summary['bank_rows'], 2)
        self.assertEqual(summary['rakuten_rows'], 0)
        self.assertEqual(summary['publisher_matched_rows'], 0)
        self.assertIn('rakuten', summary['publisher_access_denials'])
        self.assertFalse((self.root/'data'/'auto_verified_draws.jsonl').exists())

    def test_bank_browser_empty_result_stays_blocked_and_explains_error(self):
        empty_bank = '<h1>ナンバーズ4抽せん数字一覧表</h1>'
        with patch('numbers4_agent.official_fetch._render_bank_page',
                   return_value=(empty_bank, 'b' * 64)):
            summary = sync(self.root, now=self.now, months_back=2,
                           opener=open_mocks(bank=empty_bank), bank_browser_fallback=True)
        self.assertEqual(summary['status'], 'blocked_no_bank_verified_results')
        self.assertEqual(summary['new_verified_rows'], 0)
        self.assertTrue(any('browser fallback rejected' in item['reason']
                            for item in summary['bank_errors']))
        self.assertFalse((self.root/'data'/'auto_verified_draws.jsonl').exists())

    def test_mixed_month_bank_response_never_partially_verifies(self):
        mixed = BANK_OCT.replace("2026年10月30日", "2026年11月1日")
        result = sync(self.root, now=self.now, months_back=2,
                      opener=open_mocks(bank=mixed))
        self.assertEqual(result["bank_rows"], 0)
        self.assertEqual(result["publisher_matched_rows"], 0)
        self.assertEqual(result["status"], "blocked_no_bank_verified_results")
        self.assertTrue(any("month disagrees" in e["reason"] for e in result["bank_errors"]))
        self.assertFalse((self.root / "data" / "auto_verified_draws.jsonl").exists())

    def test_mixed_month_rakuten_response_never_partially_verifies(self):
        mixed = RAK_OCT.replace("2026/10/30", "2026/11/1")
        result = sync(self.root, now=self.now, months_back=2,
                      opener=open_mocks(rak=mixed))
        self.assertEqual(result["rakuten_rows"], 0)
        self.assertEqual(result["publisher_matched_rows"], 0)
        self.assertTrue(any("month disagrees" in e["reason"] for e in result["rakuten_errors"]))
        self.assertFalse((self.root / "research" / "historical_unverified.json").exists())

    def test_source_conflict_refuses_batch_without_partial_commit(self):
        faulty=RAK_OCT.replace('2491','2492')
        with self.assertRaisesRegex(ResultFetchError,'publisher disagreement'):
            sync(self.root,now=self.now,months_back=2,opener=open_mocks(rak=faulty))
        self.assertFalse((self.root/'data'/'auto_verified_draws.jsonl').exists())

    def test_corrupt_research_cache_blocks_all_official_ledger_writes(self):
        """Reject a stale or conflicting secondary cache before verified writes."""
        cache=self.root/'research'/'historical_unverified.json'
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({
            'version':'numbers4-research-source-v1',
            'verified_official':False,
            'rows':[{'round':7103,'draw_date':'2026-10-29',
                     'winning_number':'9999'}]
        }))
        with self.assertRaisesRegex(ResultFetchError,'revised an existing draw'):
            sync(self.root,now=self.now,months_back=2,opener=open_mocks())
        self.assertFalse((self.root/'data'/'auto_verified_draws.jsonl').exists())

    def test_invalid_research_provenance_blocks_verified_writes(self):
        cache=self.root/'research'/'historical_unverified.json'
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({
            'version':'unexpected-version', 'verified_official':False, 'rows':[]
        }))
        with self.assertRaisesRegex(ResultFetchError,'invalid provenance'):
            sync(self.root,now=self.now,months_back=2,opener=open_mocks())
        self.assertFalse((self.root/'data'/'auto_verified_draws.jsonl').exists())

    def test_network_host_strict_and_redirects_blocked(self):
        with self.assertRaisesRegex(ResultFetchError, 'unapproved'):
            _download('https://www.mizuhobank.co.jp.attacker.example', 'www.mizuhobank.co.jp',opener=open_mocks())
        with self.assertRaisesRegex(ResultFetchError, 'unapproved'):
            _download('http://www.mizuhobank.co.jp/', 'www.mizuhobank.co.jp',opener=open_mocks())
        with self.assertRaisesRegex(ResultFetchError, 'redirected'):
            _download('https://www.mizuhobank.co.jp/x','www.mizuhobank.co.jp',opener=lambda r,timeout:Response('https://attacker.example/',BANK_OCT))

    def test_autoverification_hash_chain_tampering_fail_closed(self):
        sync(self.root, now=self.now, months_back=2,opener=open_mocks())
        path=self.root/'data'/'auto_verified_draws.jsonl'
        path.write_text(path.read_text().replace('5805','5806'))
        with self.assertRaisesRegex(ValueError,'checksum'):
            reconcile(self.root)

    def test_research_declares_no_skill_with_only_two_real_observations(self):
        sync(self.root, now=self.now, months_back=2,opener=open_mocks())
        result=run(self.root)
        self.assertEqual(result['research_unverified_history']['evaluated_draws'],0)
        self.assertFalse(result['verified_history_exploratory']['prediction_skill_confirmed'])
        self.assertFalse(result['production_changed'])

    def test_chronological_histories_reject_leakage_and_bad_numbers(self):
        rows=[{'round':n,'draw_date':f'2026-10-{n:02d}', 'winning_number':f'{n:04d}'} for n in range(1,20)]
        with self.assertRaisesRegex(ValueError,'30'):
            prequential(rows,min_history=20)
        rows.append(dict(rows[0]))
        with self.assertRaisesRegex(ValueError,'duplicate'):
            prequential(rows)

if __name__=='__main__':unittest.main()

class ProofTests(unittest.TestCase):
    def test_research_evaluates_only_prior_draws_and_does_not_promote(self):
        from datetime import date, timedelta
        start=date(2026, 1, 1)
        data=[{'round':n, 'draw_date':(start+timedelta(days=n)).isoformat(),
               'winning_number':f'{(n*137+17)%10000:04d}'} for n in range(1, 37)]
        report=prequential(data,min_history=30,scope='synthetic_unit_test_only')
        self.assertEqual(report['evaluated_draws'],6)
        self.assertEqual(report['first_evaluated_round'],31)
        self.assertEqual(report['uniform_expected_top5_hit_draws'],6*5/10000)
        self.assertFalse(report['prediction_skill_confirmed'])
        self.assertFalse(report['production_promotion_allowed'])
        self.assertFalse(report['protocol_version_frozen_before_this_execution'])
        self.assertEqual(len(report['descriptive_moving_block_bootstrap_95pct']),2)
