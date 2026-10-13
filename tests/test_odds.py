import sys
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from odds import OddsError, american_to_decimal, as_percent, implied_probability, no_vig_two_way, parse_american


class AmericanOddsTests(unittest.TestCase):
    def test_positive_and_negative_implied_probability(self):
        self.assertEqual(implied_probability("+280"), Decimal(100) / Decimal(380))
        self.assertEqual(implied_probability("-455"), Decimal(455) / Decimal(555))

    def test_novig_9z_aurora_example(self):
        result = no_vig_two_way("+280", "-455")
        self.assertEqual(as_percent(result["fair_a"]), Decimal("24.30"))
        self.assertEqual(as_percent(result["fair_b"]), Decimal("75.70"))
        self.assertGreater(result["overround"], 0)

    def test_novig_astralis_sashi_example(self):
        result = no_vig_two_way("-1250", "+530")
        self.assertEqual(as_percent(result["fair_a"]), Decimal("85.37"))
        self.assertEqual(as_percent(result["fair_b"]), Decimal("14.63"))

    def test_decimal_odds_conversion(self):
        self.assertEqual(american_to_decimal("+280"), Decimal("3.8"))
        self.assertEqual(american_to_decimal("-455"), Decimal(1) + Decimal(100) / Decimal(455))

    def test_unicode_minus_is_supported(self):
        self.assertEqual(parse_american("−455"), Decimal("-455"))

    def test_ambiguous_or_invalid_inputs_are_rejected(self):
        for value in (None, "", "280", "0", "+0", "-0", "even", True, "Infinity"):
            with self.subTest(value=value):
                with self.assertRaises(OddsError):
                    implied_probability(value)

    def test_two_way_fair_probabilities_sum_to_one(self):
        result = no_vig_two_way("+110", "-130")
        self.assertEqual(result["fair_a"] + result["fair_b"], Decimal(1))


if __name__ == "__main__":
    unittest.main()
