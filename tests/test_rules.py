import unittest
from numbers4_agent.rules import four_digits, validate_play, permutation_count, theoretical_odds, grade_number


class Numbers4RulesTests(unittest.TestCase):
    def test_leading_zeroes_and_invalid(self):
        self.assertEqual(four_digits("0000"), "0000")
        self.assertEqual(four_digits("0012"), "0012")
        for bad in (1234, "123", "12345", "１２３４", "12a4", "-001", None):
            with self.assertRaises(ValueError):
                four_digits(bad)

    def test_repeated_digit_combinations(self):
        for number, count in [("1234", 24), ("1123", 12), ("1122", 6), ("1112", 4), ("0000", 1)]:
            self.assertEqual(permutation_count(number), count)
        with self.assertRaises(ValueError):
            validate_play("0000", "box")
        with self.assertRaises(ValueError):
            validate_play("1111", "set")
        self.assertEqual(validate_play("0000", "straight")[0], "0000")

    def test_grade_must_respect_order_mode_and_zeroes(self):
        self.assertEqual(grade_number("0123", "0123", "straight"), "straight")
        self.assertEqual(grade_number("0123", "3210", "straight"), "miss")
        self.assertEqual(grade_number("0123", "3210", "box"), "box")
        self.assertEqual(grade_number("0123", "0123", "box"), "box")
        self.assertEqual(grade_number("0123", "0123", "set"), "set_straight")
        self.assertEqual(grade_number("0123", "3210", "set"), "set_box")
        self.assertEqual(grade_number("1122", "2121", "set"), "set_box")
        self.assertEqual(grade_number("1111", "1111", "straight"), "straight")
        self.assertEqual(grade_number("0123", "0001", "set"), "miss")

    def test_exact_theoretical_probabilities(self):
        self.assertEqual(theoretical_odds("0123", "straight").any_win, 1/10000)
        self.assertEqual(theoretical_odds("0123", "box").any_win, 24/10000)
        self.assertEqual(theoretical_odds("0123", "set").box_only, 23/10000)
        self.assertEqual(theoretical_odds("1122", "set").any_win, 6/10000)
        self.assertEqual(theoretical_odds("1112", "box").combinations, 4)
