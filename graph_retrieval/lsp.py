from typing import List, Dict, Any, Optional
from pathlib import Path
import logging
from .lsp_command import use_workspace
from .identifiers import get_last_n_graph_context_identifiers_from_document
from schema.common import Document, Position
from .symbol_context_snippets import get_symbol_context_snippets

SUPPORTED_LANGUAGES = {
    "python",
    "go",
    "javascript",
    "javascriptreact",
    "typescript",
    "typescriptreact",
    "java",
    "kotlin",
}

RECURSION_LIMIT = 3
IDENTIFIERS_TO_RESOLVE = 1


class LsptRetriever:
    def __init__(self, window=None, workspace=None):
        self.identifier = "LSPRetriever"
        self.disposables = []
        self.abort_last_request = lambda: None

        self.window = window if window else {}  # Simulate VSCode API
        self.workspace = workspace if workspace else {}  # Simulate VSCode API

    async def retrieve(
        self,
        document: Document,
        position: Optional[Position] = None,
        repo: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        symbol_requests = get_last_n_graph_context_identifiers_from_document(
            document=document, position=position, n=IDENTIFIERS_TO_RESOLVE
        )

        target = Path(document.uri).resolve()
        # Find the repository directory in the target's parents when a repo ID is supplied.
        root = next((parent for parent in target.parents if repo and parent.name == repo), target.parent)
        try:
            with use_workspace(root):
                result = await get_symbol_context_snippets(symbol_requests, 2)
            return result[:10]
        except (OSError, RuntimeError) as error:
            logging.getLogger(__name__).warning("Structural retrieval unavailable: %s", error)
            return []


if __name__ == "__main__":
    import asyncio

    retrieval = LsptRetriever()
    document = Document(
        uri="test/test.py",
        language_id="python",
        text="""
from .import_test import another_call
def example():
    print("Hello")
    another_call()
    """.strip(),
    )
    asyncio.run(
        retrieval.retrieve(
            document=document, position=Position(line=3, character=17), repo="test"
        )
    )
