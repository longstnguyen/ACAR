"""Retrieve ranked evidence and reconstruct selected source-line spans."""
import asyncio
import os
from pathlib import Path
from dataclasses import replace
from urllib.parse import unquote, urlparse

from ranking.reciprocal_rank_fusion import fuse_results, merge_adjacent_lines
from text_retrieval.jaccard_retriever import JaccardSimilarityRetriever

BASE_DIR = os.getenv("ACAR_BASE_DIR", "datasets/ReccEval/Source_Code")


class ContextMixer:
    def __init__(self, base_dir=None, retrievers=None, max_chars=10000):
        self.base_dir = base_dir if base_dir is not None else BASE_DIR
        if retrievers is None:
            from graph_retrieval.lsp import LsptRetriever
            retrievers = [JaccardSimilarityRetriever(base_dir=self.base_dir), LsptRetriever()]
        self.retrievers = retrievers
        self.maxChars = max_chars

    async def get_context(self, document, position, repo=None, select_lines=None):
        rankings = await asyncio.gather(*[
            retriever.retrieve(document, position, repo) for retriever in self.retrievers
        ])
        rankings = [[replace(snippet, uri=self._normalize_path(snippet.uri))
                     for snippet in ranking if isinstance(snippet.content, str)]
                    for ranking in rankings]
        lines = fuse_results(rankings, self._get_line_ids)
        if select_lines is not None:
            return {"context": merge_adjacent_lines(select_lines(lines))}
        remaining = max(0, self.maxChars - len(document.prefix or "") - len(document.suffix or ""))
        selected = []
        for line in lines:
            cost = len(line.content) + 1
            if cost <= remaining:
                selected.append(line)
                remaining -= cost
        return {"context": merge_adjacent_lines(selected)}

    @staticmethod
    def _normalize_path(uri):
        path = unquote(urlparse(uri).path) if uri.startswith("file://") else uri
        return str(Path(path).resolve())

    @staticmethod
    def _get_line_ids(snippet):
        return [(snippet.uri, line) for line in range(snippet.start_line, snippet.end_line + 1)]
