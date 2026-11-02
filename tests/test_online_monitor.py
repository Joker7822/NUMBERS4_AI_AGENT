"""Online monitoring must fail closed. Fixtures make zero network requests."""
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from numbers4_agent.online_monitor import SOURCES, VERSION, audit, _semantic_text
from numbers4_agent.online_ops import snapshot as operation_status

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 11, 2, 15, 0, tzinfo=JST)
BODY = """<html><body><h1>ナンバーズ４</h1>
 ナンバーズ4は1口200円です。
 ストレートは並びの順序と4ケタの数字を一致させる。
 ボックスは数字が一致すれば並びの順序は問わない。
 ボックスの1111は購入できません。
 ストレート当せん確率は1 / 10,000です。
 ナンバーズ4 抽せん数字一覧表です。
 </body></html>"""


def content(url):
    if 'stat.uw.edu' in url:
        raise ConnectionError("optional research page offline")
    return BODY.encode('utf-8')


class OnlineMonitorTests(unittest.TestCase):
    def test_all_official_rule_markers_consistent_and_draws_not_verified(self):
        data = audit(now=NOW, fetch=content)
        self.assertEqual(data['version'], VERSION)
        self.assertEqual(data['status'], 'official_rule_anchors_consistent')
        self.assertEqual(data['rule_sources_consistent'], 3)
        self.assertEqual(data['rule_sources_unavailable'], 0)
        self.assertEqual(data['rule_sources_changed'], 0)
        self.assertEqual(data['result_page_status'], 'result_page_reachable_draws_not_verified')
        self.assertFalse(data['automatic_lottery_rules_adoption'])
        self.assertFalse(data['official_draw_result_verified_by_this_audit'])
        self.assertFalse(data['official_payouts_verified_by_this_audit'])
        self.assertEqual(len(data['topics']), len(SOURCES))

    def test_changed_ticket_price_needs_manual_review(self):
        def changed(url):
            html=content(url)
            if '/numbers4/howto.html' in url:
                return html.replace(b'200', b'300')
            return html
        data=audit(now=NOW,fetch=changed)
        self.assertEqual(data['status'],'rule_change_requires_review')
        bad=[p for p in data['topics'] if p['status']=='rule_change_requires_review']
        self.assertEqual(len(bad),1)
        self.assertIn('ticket_200',bad[0]['missing_markers'])

    def test_script_injection_does_not_make_rule_pass(self):
        script=b"<script>"+BODY.encode('utf-8')+b"</script><html><body>No game rules found</body></html>"
        self.assertNotIn("ナンバーズ4",_semantic_text(script))
        data=audit(now=NOW,fetch=lambda _:script)
        self.assertEqual(data['rule_sources_changed'],3)
        self.assertEqual(data['status'],'rule_change_requires_review')

    def test_official_network_error_is_unknown_not_rule_change(self):
        def partial(url):
            if 'mizuhobank.co.jp' in url:
                raise ConnectionError('offline')
            return content(url)
        data=audit(now=NOW,fetch=partial)
        self.assertEqual(data['status'],'degraded_official_rules_unverified')
        self.assertEqual(data['rule_sources_unavailable'],1)
        self.assertEqual(data['rule_sources_changed'],0)

    def test_fetched_bank_result_page_is_not_a_draw_verification(self):
        data=audit(now=NOW,fetch=content)
        bank=[x for x in data['topics'] if x['topic']=='mizuho_results_page'][0]
        self.assertEqual(bank['status'],'result_page_reachable_draws_not_verified')
        self.assertFalse(data['official_draw_result_verified_by_this_audit'])

    def _write(self,root,ref,feed):
        (root/'research').mkdir(exist_ok=True)
        (root/'research/online_reference_audit.json').write_text(json.dumps(ref),encoding='utf-8')
        (root/'research/online_source_audit.json').write_text(json.dumps(feed),encoding='utf-8')

    def _feed(self):
        return {
            'version':'numbers4-online-secondary-source-refresh-v1',
            'status':'validated_no_new_draws',
            'checked_at_jst':NOW.isoformat(),
            'official_bank_verified':False,
            'issued_forecast_grading_authorized':False,
            'automatic_model_promotion':False,
        }

    def test_monitor_status_operating_research_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            self._write(root,audit(now=NOW,fetch=content),self._feed())
            s=operation_status(root,NOW)
            self.assertEqual(s['state'],'online_monitoring_active_secondary_research_only')
            self.assertEqual(s['rule_sources_consistent'],3)
            self.assertFalse(s['bank_first_party_draws_verified_by_this_monitor'])
            self.assertFalse(s['model_auto_promotion'])
            self.assertFalse(s['real_purchases_enabled'])

    def test_stale_and_mismatch_become_clear_warnings(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            rules=audit(now=NOW,fetch=content)
            self._write(root,rules,self._feed())
            s=operation_status(root,NOW+timedelta(hours=97))
            self.assertEqual(s['state'],'stale')
            changed=audit(now=NOW,fetch=lambda url:
                content(url).replace(b'200',b'300') if 'numbers4/howto.html' in url else content(url))
            self._write(root,changed,self._feed())
            s=operation_status(root,NOW)
            self.assertEqual(s['state'],'manual_review_required')
            self.assertTrue(s['warnings'])

    def test_unsafe_claim_in_report_is_never_displayed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            report=audit(now=NOW,fetch=content)
            report['model_auto_promotion_authorized']=True
            self._write(root,report,self._feed())
            with self.assertRaisesRegex(ValueError,'unsafe'):
                operation_status(root,NOW)

    def test_no_reports_do_not_invent_success(self):
        with tempfile.TemporaryDirectory() as temp:
            s=operation_status(Path(temp),NOW)
            self.assertEqual(s['state'],'not_verified')
            self.assertIsNone(s['rule_checked_at_jst'])
            self.assertFalse(s['bank_first_party_draws_verified_by_this_monitor'])


if __name__ == "__main__":
    unittest.main()
