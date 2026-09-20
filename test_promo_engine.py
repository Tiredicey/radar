import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile
import os
import io
import sqlite3
import urllib.error
import urllib.parse
import promo_engine as engine


class EvidenceTests(unittest.TestCase):
    def test_no_invented_institutional_awards(self):
        for text in ['DOST JLSS scholarship', 'CHED TES subsidy', 'DICT hackathon', 'Batangas scholarship']:
            with self.subTest(text=text):
                self.assertEqual(engine.extract_monetary_reward(text), 0)

    def test_explicit_peso_amounts(self):
        for text, amount in [('PHP 50,000', 50000), ('₱2.5 million budget', 2500000), ('P680-K', 680000), ('php 500', 500)]:
            with self.subTest(text=text):
                self.assertEqual(engine.extract_monetary_reward(text), amount)

    def test_unrelated_numbers_are_not_awards(self):
        for text in ['SCHOLARSHIP 80000', 'USD 50,000', '2026 scholarship announcement']:
            self.assertEqual(engine.extract_monetary_reward(text), 0)

    def test_ids_are_stable(self):
        self.assertEqual(engine.generate_entry_id(' Grant ', 'https://example.org'), engine.generate_entry_id('grant', 'https://example.org'))
        self.assertNotEqual(engine.generate_entry_id('grant', 'https://example.org/a'), engine.generate_entry_id('grant', 'https://example.org/b'))


class GatewayTests(unittest.TestCase):
    def test_acknowledgements(self):
        for body in ['Message sent', '<b>Message</b> has been successfully sent', 'Message queued']:
            self.assertEqual(engine.classify_callmebot_response(body), 'accepted')
    def test_unknown_is_not_success(self):
        for body in ['', 'OK', 'success statistics', '<html>maintenance</html>']:
            self.assertEqual(engine.classify_callmebot_response(body), 'unrecognized-response')
    def test_rejections(self):
        for body, result in [('Invalid API key', 'invalid-key'), ('Message too long', 'message-too-long'), ('Too many requests', 'rate-limited'), ('Account disabled', 'not-authorized'), ('ERROR: Message not sent', 'provider-error'), ('Message could not be sent', 'provider-error')]:
            self.assertEqual(engine.classify_callmebot_response(body), result)
    def test_nonvisible_error_not_failure(self):
        self.assertEqual(engine.classify_callmebot_response('<script>error: failed</script><p>Message sent</p>'), 'accepted')

    def test_examples_echoes_and_conditionals_are_not_acknowledgements(self):
        for body in ['Example response: Message sent', '<p>Requested text: Message sent</p><p>Maintenance</p>', 'If message sent, check your phone', 'Message sent? I cannot confirm this.']:
            with self.subTest(body=body):
                self.assertEqual(engine.classify_callmebot_response(body), 'unrecognized-response')

    def test_conflicting_response_is_not_a_definite_rejection(self):
        self.assertEqual(engine.classify_callmebot_response('Message sent, but delivery failed'), 'conflicting-response')


class RelevanceTests(unittest.TestCase):
    def test_unrelated_programs_excluded(self):
        for title in ['P330M Batangas facility to boost egg production', 'Egg producers get P66M for Batangas egg plant', 'DOST allots P300M for expansion of its AI data center']:
            self.assertEqual(engine.lead_category(title), 'out_of_scope')
    def test_budget_news_is_not_application(self):
        self.assertEqual(engine.lead_category('P8.67-B funding sought for DOST scholarships'), 'funding_news')
    def test_apply_signals(self):
        self.assertEqual(engine.lead_category('DOST urges Grade 12 students to apply'), 'application_lead')
        self.assertEqual(engine.lead_category('Scholarship applications closed'), 'funding_news')


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = str(Path(tmp.name) / 'history.db')
        self.summary = str(Path(tmp.name) / 'summary.md')
        engine.init_db(self.db)
        self.report = {}
        p = patch.object(engine, 'send_messenger_callmebot', return_value=engine.GatewayResult('accepted', 'accepted', 200))
        self.send = p.start()
        self.addCleanup(p.stop)

    def seed(self, id='lead', flag=0, category='application_lead', link='https://example.org/apply'):
        title = 'Scholarship applications open' if category == 'application_lead' else 'Scholarship budget announced'
        with engine.get_db_connection(self.db) as conn:
            conn.execute('INSERT INTO vouchers(id,title,link,affiliate_link,category,discovered_at,alerted) VALUES(?,?,?,?,?,?,?)', (id,title,link,link,category,'2026-09-20',flag))

    def flags(self):
        with engine.get_db_connection(self.db) as conn:
            return dict(conn.execute('SELECT id,alerted FROM vouchers'))

    def run_dispatch(self, **kw):
        return engine.dispatch_alerts('fixture-key', self.db, report=self.report, **{'now':1800000000, **kw})

    def test_accepted_digest_is_not_repeated(self):
        self.seed()
        self.assertEqual(self.run_dispatch(), 1)
        self.assertEqual(self.flags(), {'lead':1})
        self.assertIn('https://example.org/apply', self.send.call_args.args[1])
        self.assertEqual(self.run_dispatch(now=1800003600), 0)
        self.send.assert_called_once()

    def test_news_only_sends_due_status_not_fake_application(self):
        self.seed(category='funding_news')
        self.report['new_records'] = 1
        self.run_dispatch()
        self.assertEqual(self.report['notification'], 'heartbeat-accepted')
        self.assertIn('Pending application-wording leads: 0', self.send.call_args.args[1])
        self.assertIn('not verified open applications', self.send.call_args.args[1])
        self.assertEqual(self.flags()['lead'], 0)

    def test_heartbeat_cadence_persists_across_database_reopen(self):
        self.run_dispatch()
        engine.init_db(self.db)
        self.run_dispatch(now=1800086399)
        self.send.assert_called_once()
        self.run_dispatch(now=1800086400)
        self.assertEqual(self.send.call_count, 2)

    def test_disable_status_keeps_application_alerts(self):
        self.run_dispatch(heartbeat_hours=0)
        self.send.assert_not_called()
        self.seed()
        self.assertEqual(self.run_dispatch(heartbeat_hours=0), 1)

    def test_rejected_digest_returns_to_pending_and_retries_next_run(self):
        self.seed()
        self.send.return_value = engine.GatewayResult('rejected','rate-limited',429)
        with self.assertRaises(RuntimeError): self.run_dispatch()
        self.assertEqual(self.flags()['lead'],0)
        self.send.return_value = engine.GatewayResult('accepted','accepted',200)
        self.assertEqual(self.run_dispatch(now=1800010800),1)

    def test_uncertain_attempt_is_not_blindly_retried(self):
        self.seed()
        self.send.return_value = engine.GatewayResult('uncertain','network-error')
        with self.assertRaises(RuntimeError): self.run_dispatch()
        self.assertEqual(self.flags()['lead'],2)
        with self.assertRaises(RuntimeError): self.run_dispatch(now=1800010800)
        self.send.assert_called_once()
        self.assertTrue(self.report['attention_required'])

    def test_explicit_recovery_preserves_accepted_baseline_and_news(self):
        for flag in range(4): self.seed(str(flag),flag=flag)
        self.seed('news',category='funding_news')
        self.assertEqual(self.run_dispatch(retry_uncertain=True),2)
        self.assertEqual(self.flags(),{'0':1,'1':1,'2':1,'3':3,'news':0})
        self.assertEqual(self.report['requeued'],1)

    def test_diagnostic_leaves_all_lead_flags_unchanged(self):
        for flag in range(4): self.seed(str(flag),flag=flag)
        before=self.flags()
        self.run_dispatch(test_message=True)
        self.assertEqual(self.flags(),before)
        self.assertEqual(self.report['notification'],'test-accepted')
        self.assertIn('connection test',self.send.call_args.args[1])

    def test_oversized_items_do_not_hide_later_valid_leads(self):
        for i in range(21): self.seed(str(i),link='https://example.org/'+'x'*2000)
        self.seed('valid')
        with self.assertRaises(RuntimeError): self.run_dispatch(heartbeat_hours=0)
        self.assertEqual(self.flags()['valid'],1)
        self.assertEqual(self.report['oversized_leads'],21)
        self.assertEqual(self.report['pending_applications'],21)
        self.assertTrue(engine.message_fits(self.send.call_args.args[1]))

    def test_budget_blocked_is_not_reported_as_empty_queue(self):
        self.seed(link='https://example.org/'+'x'*2000)
        with self.assertRaises(RuntimeError): self.run_dispatch(heartbeat_hours=0)
        self.assertEqual(self.report['notification'],'message-budget-blocked')
        self.assertEqual(self.flags()['lead'],0)
        self.send.assert_not_called()

    def test_bounded_digests_eventually_drain_queue(self):
        for i in range(12): self.seed(str(i),link='https://example.org/'+str(i)+'x'*400)
        for i in range(12): self.run_dispatch(now=1800000000+i*10800,heartbeat_hours=0)
        self.assertTrue(all(flag==1 for flag in self.flags().values()))
        for call in self.send.call_args_list: self.assertTrue(engine.message_fits(call.args[1]))
        self.assertFalse(engine.message_fits('₱'*1000))

    def test_crash_after_claim_remains_uncertain(self):
        self.seed()
        self.send.side_effect=KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt): self.run_dispatch()
        self.assertEqual(self.flags()['lead'],2)
        self.send.side_effect=None
        with self.assertRaises(RuntimeError): self.run_dispatch(now=1800000100)
        self.send.assert_called_once()

    def test_missing_key_invalid_interval_never_send(self):
        for key,hours in [('',24),(' ',24),('key',-1),('key',169)]:
            with self.assertRaises(ValueError): engine.dispatch_alerts(key,self.db,heartbeat_hours=hours)
        self.send.assert_not_called()

    def test_summary_does_not_expose_secrets_or_source_titles(self):
        self.seed()
        self.run_dispatch()
        with patch.dict(os.environ,{'GITHUB_STEP_SUMMARY':self.summary}): engine.write_run_summary(self.report,self.db)
        text=Path(self.summary).read_text()
        self.assertIn('Gateway acceptance is not a Messenger delivery',text)
        self.assertIn('| Pending applications | 0 |',text)
        for private in ['fixture-key','Scholarship applications open']: self.assertNotIn(private,text)

    def test_summary_describes_real_controls_and_unverified_delivery(self):
        self.run_dispatch(test_message=True)
        with patch.dict(os.environ,{'GITHUB_STEP_SUMMARY':self.summary}): engine.write_run_summary(self.report,self.db)
        text=Path(self.summary).read_text()
        self.assertIn('python3 promo_engine.py --test-notification',text)
        self.assertNotIn('Run workflow → test',text)
        self.assertIn('| Delivery status | unverified |',text)
        self.assertIn('runner attempt time',text)

    def test_migration_preserves_legacy_history(self):
        with engine.get_db_connection(self.db) as conn: conn.execute('DROP TABLE notification_state')
        for flag in range(4): self.seed(str(flag),flag=flag)
        engine.init_db(self.db)
        self.assertEqual(self.flags(),{str(i):i for i in range(4)})
        with engine.get_db_connection(self.db) as conn:
            self.assertEqual(conn.execute('SELECT initialized FROM notification_state').fetchone()[0],1)

    def test_context_closes_database_and_rolls_back(self):
        with self.assertRaises(RuntimeError):
            with engine.get_db_connection(self.db) as conn:
                conn.execute("UPDATE notification_state SET result='fixture'")
                raise RuntimeError('rollback')
        with self.assertRaises(sqlite3.ProgrammingError): conn.execute('SELECT 1')
        with engine.get_db_connection(self.db) as conn:
            self.assertEqual(conn.execute('SELECT result FROM notification_state').fetchone()[0],'never-attempted')

    def test_failed_status_does_not_become_silent_success(self):
        self.send.return_value=engine.GatewayResult('rejected','invalid-key',403)
        with self.assertRaises(RuntimeError): self.run_dispatch()
        with self.assertRaises(RuntimeError): self.run_dispatch(now=1800000100)
        self.send.assert_called_once()

    def run_main(self, argv, fail_feed=False):
        init,connect,dispatch,summary=engine.init_db,engine.get_db_connection,engine.dispatch_alerts,engine.write_run_summary
        def ingest():
            if fail_feed: raise RuntimeError('Feed unavailable')
            self.seed()
            return 1
        with patch.object(engine,'init_db',side_effect=lambda:init(self.db)), \
             patch.object(engine,'get_db_connection',side_effect=lambda db_path=self.db:connect(db_path)), \
             patch.object(engine,'ingest_feeds',side_effect=ingest) as feeds, \
             patch.object(engine,'dispatch_alerts',side_effect=lambda key,**kw:dispatch(key,self.db,**kw)), \
             patch.object(engine,'write_run_summary',side_effect=lambda report:summary(report,self.db)), \
             patch.object(engine,'list_records'), \
             patch.dict(os.environ,{'CALLMEBOT_KEY':'fixture-key','RADAR_BASELINE':'0','GITHUB_STEP_SUMMARY':self.summary}), \
             patch.object(engine.sys,'argv',['promo_engine.py',*argv]):
            engine.main()
        return feeds

    def test_cold_start_baselines_existing_leads_but_sends_status(self):
        self.run_main(['--auto'])
        self.assertEqual(self.flags()['lead'],3)
        self.assertIn('Radar status',self.send.call_args.args[1])

    def test_cold_diagnostic_does_not_bypass_next_scan_baseline(self):
        self.run_main(['--test-notification']).assert_not_called()
        self.run_main(['--auto'])
        self.assertEqual(self.flags()['lead'],3)
        self.send.assert_called_once()

    def test_feed_failure_does_not_send_false_healthy_status(self):
        with self.assertRaises(RuntimeError): self.run_main(['--auto'],fail_feed=True)
        self.send.assert_not_called()
        self.assertIn('| Run result | failed |',Path(self.summary).read_text())


class TransportTests(unittest.TestCase):
    def request(self,body=b'Message sent',error=None,status=200):
        opener=MagicMock()
        if error: opener.open.side_effect=error
        else:
            response=opener.open.return_value.__enter__.return_value
            response.status=status
            response.read.return_value=body
        with patch.object(engine.urllib.request,'build_opener',return_value=opener) as build:
            with self.assertLogs(level='INFO') as logs:
                result=engine.send_messenger_callmebot('private-fixture-key','Research & scholarship ₱500')
        self.assertNotIn('private-fixture-key','\n'.join(logs.output))
        build.assert_called_once_with(engine.NoRedirect)
        url=opener.open.call_args.args[0].full_url
        self.assertEqual(urllib.parse.parse_qs(urllib.parse.urlparse(url).query)['text'],['Research & scholarship ₱500'])
        return result

    def test_acknowledgements_and_unknown_responses(self):
        self.assertEqual(self.request().outcome,'accepted')
        for body in [b'',b'OK',b'Maintenance',b'x'*65537]: self.assertEqual(self.request(body).outcome,'uncertain')
        for body in [b'Invalid API key',b'Too many requests',b'Account disabled',b'ERROR: not sent']:
            self.assertEqual(self.request(body).outcome,'rejected')

    def test_conflicting_and_example_responses_are_uncertain(self):
        for body in [b'Message sent, but delivery failed', b'Example response: Message sent']:
            self.assertEqual(self.request(body).outcome,'uncertain')

    def test_http_errors_do_not_leak_credentials(self):
        for status in [400,401,403,413,414,429,500,502,503,302]:
            error=urllib.error.HTTPError('https://example.org/?apikey=private-fixture-key',status,'private',{},io.BytesIO(b'private-fixture-key'))
            result=self.request(error=error)
            self.assertEqual(result.http_status,status)
            self.assertEqual(result.outcome,'rejected' if status in {400,401,403,413,414,429} else 'uncertain')

    def test_network_failure_is_uncertain(self):
        for error in [TimeoutError('private-fixture-key'),urllib.error.URLError('private-fixture-key'),ConnectionResetError()]:
            self.assertEqual(self.request(error=error).outcome,'uncertain')

    def test_status_and_redirect_guard(self):
        self.assertEqual(self.request(status=503).outcome,'uncertain')
        self.assertIsNone(engine.NoRedirect().redirect_request(None,None,302,'',{},'https://elsewhere.example'))


if __name__ == '__main__':
    unittest.main()
