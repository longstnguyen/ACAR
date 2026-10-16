import unittest
from prompt.budget import fit_local_context, select_context_lines, serialize_context, token_count
from prompt.fim_utils import CodeQwen25PromptExtractor
from ranking.reciprocal_rank_fusion import FusedSnippet, merge_adjacent_lines


class CharacterTokenizer:
    def encode(self, text, add_special_tokens=False): return list(text)
    def decode(self, tokens): return ''.join(tokens)


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.tokenizer = CharacterTokenizer()
        self.extractor = CodeQwen25PromptExtractor()

    def test_long_local_context_retains_both_sides_of_hole(self):
        prefix, suffix = fit_local_context(self.tokenizer, self.extractor, 'a.py',
                                           'x' * 200 + 'return ', 'finish' + 'y' * 200, 120)
        self.assertTrue(prefix.endswith('return '))
        self.assertTrue(suffix.startswith('finish'))
        prompt = self.extractor.get_infilling_prompt('a.py', '', prefix, suffix)
        self.assertLessEqual(token_count(self.tokenizer, prompt), 120)
        self.assertTrue(prompt.endswith('<|fim_middle|>'))

    def test_budget_counts_headers_and_can_select_subspan(self):
        lines = [FusedSnippet('a.py', 0, 0, 'a' * 100, 2),
                 FusedSnippet('a.py', 1, 1, 'small', 1)]
        selected = select_context_lines(lines, self.tokenizer, self.extractor, 'target.py', '', '', 30, 150)
        self.assertEqual([line.start_line for line in selected], [1])
        intro = serialize_context(self.extractor, merge_adjacent_lines(selected))
        self.assertLessEqual(len(intro), 30)
        prompt = self.extractor.get_infilling_prompt('target.py', intro, '', '')
        self.assertLessEqual(len(prompt), 150)

    def test_zero_retrieval_budget_and_unfit_template(self):
        line = FusedSnippet('a.py', 0, 0, 'abc', 1)
        self.assertEqual(select_context_lines([line], self.tokenizer, self.extractor, 'a.py', '', '', 0, 100), [])
        with self.assertRaises(ValueError):
            fit_local_context(self.tokenizer, self.extractor, 'long-name.py', 'prefix', 'suffix', 2)
