"""Generation contract tests: no checkpoint download is required."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock


@unittest.skipUnless(importlib.util.find_spec('torch') and importlib.util.find_spec('transformers'),
                     'Install full requirements for inference tests')
class InferenceTests(unittest.TestCase):
    def test_attention_mask_sampling_and_generated_slice(self):
        import torch
        from inference.qwen_inference import QwenInference
        engine = QwenInference.__new__(QwenInference)
        engine._clear_cuda_cache = Mock()
        engine.stop_token_ids = [99]
        class Inputs(dict):
            @property
            def input_ids(self): return self['input_ids']
        engine.tokenizer = Mock(return_value=Inputs(
            input_ids=torch.tensor([[1, 2, 3]]), attention_mask=torch.ones(1, 3, dtype=torch.long)))
        engine.tokenizer.decode.return_value = 'answer'
        engine.model = Mock(device=torch.device('cpu'))
        engine.model.generate.return_value = torch.tensor([[1, 2, 3, 4, 5, 99]])
        self.assertEqual(engine._generate_single('<|fim_middle|>'), 'answer')
        options = engine.model.generate.call_args.kwargs
        self.assertEqual((options['max_new_tokens'], options['temperature'], options['top_k']), (48, 0.2, 5))
        self.assertTrue(options['do_sample'])
        self.assertEqual(options['eos_token_id'], [99])
        self.assertTrue(torch.equal(options['attention_mask'], torch.ones(1, 3, dtype=torch.long)))
        self.assertEqual(engine.tokenizer.decode.call_args.args[0], [4, 5])
        engine._generate_single('<|fim_middle|>', temperature=0)
        options = engine.model.generate.call_args.kwargs
        self.assertFalse(options['do_sample'])
        self.assertNotIn('temperature', options)

    def test_batch_preserves_exact_fim_prompt_and_source_fields(self):
        from inference.qwen_inference import QwenInference
        engine = QwenInference.__new__(QwenInference)
        engine.model_name = 'test/model'
        engine.model = Mock(device='cpu')
        engine._generate_single = Mock(return_value='answer')
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'input.jsonl'
            original = dict(prompt='prefix<|fim_middle|>', prefix='prefix', suffix='suffix', groundtruth='answer')
            source.write_text(json.dumps(original) + '\n')
            result = Path(engine.process_file(str(source)))
            output = json.loads(result.read_text())
        self.assertEqual(engine._generate_single.call_args.args[0], original['prompt'])
        self.assertEqual(output, {**original, 'choices': [{'text': 'answer'}]})
