import unittest

from graph_retrieval.identifiers import get_last_n_graph_context_identifiers_from_string


class IdentifierTests(unittest.TestCase):
    def test_nested_source_resolves_calls_without_global_parser(self):
        requests = get_last_n_graph_context_identifiers_from_string(
            n=2, uri="pricing.py", language_id="python",
            source="def price():\n    return round(total())\n",
        )
        self.assertEqual({r.symbol_name for r in requests}, {"round", "total"})
        self.assertTrue(all(r.position.line == 1 for r in requests))

    def test_source_without_calls(self):
        self.assertEqual(get_last_n_graph_context_identifiers_from_string(
            n=2, uri="pricing.py", language_id="python", source="subtotal = 10\n",
        ), [])


if __name__ == "__main__":
    unittest.main()
