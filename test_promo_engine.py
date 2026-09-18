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


if __name__ == '__main__':
    unittest.main()
