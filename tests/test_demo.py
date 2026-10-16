import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts.demo import run


class DemoTests(unittest.TestCase):
    def test_retrieval_and_ast_refinement_preserve_source_record(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
            refined = run(directory)
            raw = json.loads((Path(directory) / "raw.jsonl").read_text())
            prompt = json.loads((Path(directory) / "prompts.jsonl").read_text())
            self.assertEqual(refined["choices"][0]["text"], prompt["groundtruth"])
            self.assertNotEqual(raw["choices"][0]["text"], prompt["groundtruth"])
            self.assertEqual(refined["prefix"], prompt["prefix"])
            self.assertEqual(refined["suffix"], prompt["suffix"])
            self.assertEqual(refined["metadata"], prompt["metadata"])
            self.assertEqual(len(prompt["contexts"]), 1)
            self.assertTrue(prompt["contexts"][0]["uri"].endswith("shop/pricing.py"))
            self.assertIn("<|fim_middle|>", prompt["prompt"])
            before = (Path(directory) / "refined.jsonl").read_bytes()
            with self.assertRaises(FileExistsError):
                run(directory)
            self.assertEqual((Path(directory) / "refined.jsonl").read_bytes(), before)

    def test_generation_error_cannot_become_a_scored_completion(self):
        from pipelines.post_process_jsonl import process_single_data
        with self.assertRaises(ValueError):
            process_single_data(".", {"choices": [{"text": "ERROR: out of memory"}]})


if __name__ == "__main__":
    unittest.main()
