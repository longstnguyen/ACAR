import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from context_mixer import ContextMixer
from ranking.reciprocal_rank_fusion import fuse_results, merge_adjacent_lines
from schema.common import Document, Position
from schema.jaccard import JaccardMatchWithFilename
from text_retrieval.best_jaccard_match import best_jaccard_matches
from text_retrieval.jaccard_retriever import JaccardSimilarityRetriever


def snippet(uri, start, content):
    return JaccardMatchWithFilename(score=1, content=content, uri=uri,
                                   start_line=start, end_line=start + len(content.split('\n')) - 1)


def identities(item):
    return [(item.uri, n) for n in range(item.start_line, item.end_line + 1)]


class RetrievalTests(unittest.TestCase):
    def test_rrf_rewards_agreement_and_does_not_double_count_a_branch(self):
        first = snippet('a.py', 0, 'a\nb\nc')
        overlap = snippet('a.py', 1, 'b\nc')
        ranked = fuse_results([[first, overlap], [overlap]], identities)
        self.assertEqual([line.start_line for line in ranked], [1, 2, 0])
        self.assertAlmostEqual(ranked[0].score, 2 / 61)
        self.assertAlmostEqual(ranked[-1].score, 1 / 61)
        self.assertEqual(len(ranked), 3)

    def test_fusion_preserves_ties_and_rejects_unordered_input(self):
        a, b = snippet('z.py', 0, 'z'), snippet('a.py', 0, 'a')
        self.assertEqual([line.uri for line in fuse_results([[a], [b]], identities)], ['z.py', 'a.py'])
        with self.assertRaises(TypeError):
            fuse_results([{a, b}], identities)

    def test_reconstruction_keeps_gaps_and_file_boundaries(self):
        ranked = fuse_results([[snippet('x.py', 0, 'a\nb'), snippet('x.py', 4, 'e'),
                                snippet('y.py', 2, 'c')]], identities)
        merged = merge_adjacent_lines(ranked)
        self.assertEqual([(s.uri, s.start_line, s.end_line, s.content) for s in merged],
                         [('x.py', 0, 1, 'a\nb'), ('x.py', 4, 4, 'e'), ('y.py', 2, 2, 'c')])

    def test_jaccard_step_and_repeated_tokens_against_set_scores(self):
        # No normalization ambiguity: repeated tokens must not change set similarity.
        with patch('text_retrieval.best_jaccard_match.get_word_occurrences',
                   side_effect=lambda text: dict.fromkeys(text.split(), 1)):
            matches = best_jaccard_matches('a b', 'z z\nz\na a\nb b\na\nc', 2, 3, slide=2)
        self.assertEqual([m.start_line for m in matches], [2, 4, 0])
        self.assertEqual([m.score for m in matches], [1, 1 / 3, 0])
        for parameter in ('window_size', 'max_matches', 'slide'):
            options = dict(window_size=2, max_matches=3, slide=2)
            options[parameter] = 0
            with self.assertRaises(ValueError):
                best_jaccard_matches('a', 'b', **options)

    def test_global_top_k_and_active_file_exclusion(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            repo = base / 'repo'
            repo.mkdir()
            target = repo / 'target.py'
            target.write_text('price quantity discount')
            (repo / 'one.py').write_text('price quantity')
            (repo / 'two.py').write_text('price discount')
            doc = Document(str(repo / '..' / 'repo' / 'target.py'), 'python', target.read_text())
            matches = asyncio.run(JaccardSimilarityRetriever(base_dir=base, max_chunk_result=1).retrieve(doc, repo='repo'))
            self.assertEqual(len(matches), 1)
            self.assertNotEqual(Path(matches[0].uri).resolve(), target)

    def test_mixer_selects_shared_subspan_and_normalizes_file_uri(self):
        class Retriever:
            def __init__(self, ranking): self.ranking = ranking
            async def retrieve(self, *args): return self.ranking
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'a.py'
            mixer = ContextMixer(retrievers=[
                Retriever([snippet(str(path), 0, 'aaaa\nbbbb\ncccc')]),
                Retriever([snippet(path.as_uri(), 1, 'bbbb')]),
            ], max_chars=5)
            result = asyncio.run(mixer.get_context(Document(str(path), 'python', ''), Position(0, 0)))
            self.assertEqual([(s.start_line, s.end_line, s.content) for s in result['context']], [(1, 1, 'bbbb')])
