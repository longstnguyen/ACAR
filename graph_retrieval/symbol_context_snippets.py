"""Resolve definitions to source bodies and follow nested calls to a bounded depth."""
from pathlib import Path
from urllib.parse import unquote, urlparse
from tree_sitter_languages import get_parser

from graph_retrieval.lsp_command import get_definition_locations
from graph_retrieval.identifiers import get_last_n_graph_context_identifiers_from_string
from schema.common import Position
from schema.lsp import LSPSymbolContextSnippet

NESTED_IDENTIFIERS_TO_RESOLVE = 5
_SYMBOL_NODES = {"function_definition", "class_definition", "method_declaration",
                 "class_declaration", "function_declaration", "method_definition"}


def _source_body(location, language):
    """Return complete source lines for the smallest enclosing symbol body."""
    uri = location.uri
    path = Path(unquote(urlparse(uri).path) if uri.startswith("file://") else uri).resolve()
    if any(part in {"site-packages", "dist-packages", ".venv", "venv"} for part in path.parts):
        return None
    source = path.read_text(encoding="utf-8")
    lines = source.split("\n")
    row = location.range.start.line
    if row >= len(lines):
        return None
    column = len(lines[row][:location.range.start.character].encode("utf-8"))
    tree = get_parser(language).parse(source.encode("utf-8"))
    node = tree.root_node.descendant_for_point_range((row, column), (row, column))
    while node is not None and node.type not in _SYMBOL_NODES:
        node = node.parent
    if node is None:
        start, end = row, location.range.end.line
        if end > start and location.range.end.character == 0:
            end -= 1
    else:
        # Include decorators that belong to the resolved definition.
        if node.parent and node.parent.type == "decorated_definition":
            node = node.parent
        start, end = node.start_point[0], node.end_point[0]
        if end > start and node.end_point[1] == 0:
            end -= 1
    end = min(end, len(lines) - 1)
    return str(path), start, end, "\n".join(lines[start:end + 1])


async def get_symbol_context_snippets(symbols_snippet_requests, recursion_limit):
    """Depth-first definition expansion with deduplication across sibling branches."""
    visited = set()
    snippets = []

    async def visit(requests, depth):
        if depth <= 0:
            return
        for request in requests:
            locations = await get_definition_locations(
                request.uri, request.position, language=request.language_id,
            )
            for location in locations:
                body = _source_body(location, request.language_id)
                if body is None:
                    continue
                uri, start, end, content = body
                identity = (uri, start, end)
                if identity in visited:
                    continue
                visited.add(identity)
                snippets.append(LSPSymbolContextSnippet(
                    identifier="LSPRetriever", uri=uri, start_line=start, end_line=end,
                    content=content, symbol=request.symbol_name,
                ))
                if depth == 1:
                    continue
                nested = get_last_n_graph_context_identifiers_from_string(
                    n=NESTED_IDENTIFIERS_TO_RESOLVE, uri=uri,
                    language_id=request.language_id, source=content, prioritize="head",
                )
                for child in nested:
                    child.position = Position(child.position.line + start, child.position.character)
                await visit(nested, depth - 1)
    await visit(symbols_snippet_requests, recursion_limit)
    return snippets
