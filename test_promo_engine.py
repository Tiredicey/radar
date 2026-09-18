import unittest
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


class RelevanceTests(unittest.TestCase):
    def test_unrelated_programs_excluded(self):
        for title in ['P330M Batangas facility to boost egg production', 'Egg producers get P66M for Batangas egg plant', 'DOST allots P300M for expansion of its AI data center']:
            self.assertEqual(engine.lead_category(title), 'out_of_scope')
    def test_budget_news_is_not_application(self):
        self.assertEqual(engine.lead_category('P8.67-B funding sought for DOST scholarships'), 'funding_news')
    def test_apply_signals(self):
        self.assertEqual(engine.lead_category('DOST urges Grade 12 students to apply'), 'application_lead')
        self.assertEqual(engine.lead_category('Scholarship applications closed'), 'funding_news')


if __name__ == '__main__':
    unittest.main()
