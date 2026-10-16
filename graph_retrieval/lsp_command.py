from typing import List
from multilspy import SyncLanguageServer
from multilspy.multilspy_config import MultilspyConfig
from multilspy.multilspy_logger import MultilspyLogger
import os
import atexit
from contextlib import contextmanager, ExitStack
from contextvars import ContextVar
from urllib.parse import unquote, urlparse
from schema.common import Position, Location, Range

# Initialize logger and workspace
logger = MultilspyLogger()
workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

_workspace = ContextVar("acar_lsp_workspace", default=workspace_root)
_servers = {}
_server_lifetimes = ExitStack()
atexit.register(_server_lifetimes.close)


@contextmanager
def use_workspace(path):
    token = _workspace.set(os.path.abspath(path))
    try:
        yield
    finally:
        _workspace.reset(token)


@contextmanager
def _running_server(language=None):
    key = (language or "python", _workspace.get())
    if key not in _servers:
        server = get_lsp_server(key[0])
        _server_lifetimes.enter_context(server.start_server())
        _servers[key] = server
    yield _servers[key]


# Create LSP handler function
def get_lsp_server(language: str = "python") -> SyncLanguageServer:
    """
    Get a language server instance for the specified programming language.
    
    Args:
        language: The programming language to initialize the LSP for (default: "python")
        
    Returns:
        SyncLanguageServer: An initialized language server
    """
    config = MultilspyConfig.from_dict({"code_language": language})
    return SyncLanguageServer.create(config, logger, _workspace.get())


def _uri_to_file_path(uri: str) -> str:
    """Convert URI to file path."""
    # Simple conversion for file:// URIs
    if uri.startswith("file://"):
        return unquote(urlparse(uri).path)
    return uri

def _position_to_line_col(position: Position) -> tuple:
    """Convert Position to line, column tuple."""
    return position.line, position.character

async def get_definition_locations(uri: str, position: Position, language: str = None) -> List[Location]:
    file_path = _uri_to_file_path(uri)
    line, col = _position_to_line_col(position)

    try:
        # Use language-specific LSP if provided
        with _running_server(language) as current_lsp:
            definitions = current_lsp.request_definition(file_path, line, col)
        
        # Convert results to Location objects
        locations = []
        for def_loc in definitions or []:
            # Handle the actual multilspy response format
            loc = Location(
                uri=_uri_to_file_path(def_loc.get('uri', uri)),
                range=Range(
                    start=Position(line=def_loc.get('range', {}).get('start', {}).get('line', 0), 
                                character=def_loc.get('range', {}).get('start', {}).get('character', 0)),
                    end=Position(line=def_loc.get('range', {}).get('end', {}).get('line', 0), 
                                character=def_loc.get('range', {}).get('end', {}).get('character', 0))
                )
            )
            locations.append(loc)
        
        return locations
    except Exception as e:
        print(f"Error getting definition locations: {e}")
        return []
