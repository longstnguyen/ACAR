import asyncio
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from schema.common import Location, Position, Range
from schema.tree_sitter import SymbolRequest


@unittest.skipUnless(importlib.util.find_spec('multilspy'), 'Install full requirements for LSP tests')
class StructuralTests(unittest.TestCase):
    def test_full_bodies_sibling_calls_cycles_and_depth_bound(self):
        from graph_retrieval.symbol_context_snippets import get_symbol_context_snippets
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'functions.py'
            path.write_text('def root():\n    left()\n    right()\n\ndef left():\n    root()\n\ndef right():\n    leaf()\n\ndef leaf():\n    return 42\n')
            definitions = {'root': 0, 'left': 4, 'right': 7, 'leaf': 10}
            calls = {0: 'root', 1: 'left', 2: 'right', 5: 'root', 8: 'leaf'}
            async def resolve(uri, position, language):
                row = definitions[calls[position.line]]
                return [Location(str(path), Range(Position(row, 4), Position(row, 8)))]
            request = SymbolRequest(uri=str(path), language_id='python', node_type='call', symbol_name='root', position=Position(0, 4), capture_name='identifier')
            with patch('graph_retrieval.symbol_context_snippets.get_definition_locations', new=resolve):
                result = asyncio.run(get_symbol_context_snippets([request], 2))
                deep = asyncio.run(get_symbol_context_snippets([request], 3))
            self.assertEqual([s.symbol for s in result], ['root', 'left', 'right'])
            self.assertEqual([s.symbol for s in deep], ['root', 'left', 'right', 'leaf'])
            self.assertIn('    right()', result[0].content)
            self.assertEqual(result[0].end_line, 2)
            self.assertEqual(result[1].content, 'def left():\n    root()')

    def test_server_reused_per_language_and_workspace(self):
        from contextlib import ExitStack
        from graph_retrieval import lsp_command as commands
        with ExitStack() as lifetimes, patch.object(commands, '_servers', {}), \
             patch.object(commands, '_server_lifetimes', lifetimes), \
             patch.object(commands, 'get_lsp_server') as create:
            with commands.use_workspace('/tmp/acar-a'):
                with commands._running_server('python') as first:
                    pass
                with commands._running_server('python') as second:
                    self.assertIs(first, second)
            self.assertEqual(create.call_count, 1)
            with commands.use_workspace('/tmp/acar-b'):
                with commands._running_server('python'):
                    pass
            self.assertEqual(create.call_count, 2)

    def test_no_definitions_does_not_skip_later_requests(self):
        from graph_retrieval.symbol_context_snippets import get_symbol_context_snippets
        requests = [SymbolRequest(uri='sample.py', language_id='python', node_type='call', symbol_name=name, position=Position(i, 0), capture_name='identifier')
                    for i, name in enumerate(['missing', 'found'])]
        resolver = AsyncMock(return_value=[])
        with patch('graph_retrieval.symbol_context_snippets.get_definition_locations', resolver):
            self.assertEqual(asyncio.run(get_symbol_context_snippets(requests, 2)), [])
        self.assertEqual(resolver.await_count, 2)
