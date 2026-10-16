import unittest

from scripts.evaluate import edit_distance, score_records


def row(prediction, reference):
    return {"choices": [{"text": prediction}], "groundtruth": reference}


class EvaluationTests(unittest.TestCase):
    def test_known_levenshtein_example(self):
        self.assertEqual(edit_distance("kitten", "sitting"), 3)

    def test_aggregation_and_empty_strings(self):
        self.assertEqual(score_records([row("abc", "abc"), row("abc", "adc"), row("", "")]),
                         {"n": 3, "EM": 66.6667, "ES": 88.8889})

    def test_whitespace_is_significant(self):
        self.assertEqual(score_records([row("x ", "x")]), {"n": 1, "EM": 0.0, "ES": 50.0})

    def test_failed_and_missing_records_are_not_silently_dropped(self):
        for records in [[], [{"error": "failed"}], [{}], [row("ERROR: failed", "x")], [row(None, "x")]]:
            with self.subTest(records=records), self.assertRaises(ValueError):
                score_records(records)


if __name__ == "__main__":
    unittest.main()
