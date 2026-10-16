"""Run a small lexical-retrieval and refinement example without a model or LSP."""

import argparse
import asyncio
import json
from pathlib import Path


def run(output_dir):
    from pipelines.post_process_jsonl import process_single_data
    from prompt.fim_utils import CodeQwen25PromptExtractor
    from schema.common import Document, Position
    from text_retrieval.jaccard_retriever import JaccardSimilarityRetriever

    base = Path("examples/repository")
    source = base / "shop/cart.py"
    prefix = (
        "from pricing import discounted_total\n\n\n"
        "def checkout(price, quantity, discount):\n"
        "    return "
    )
    suffix = "\n"
    # The fixture includes an extra function to exercise AST truncation.
    reference = "discounted_total(price, quantity, discount)"
    raw = reference + "\n\ndef unrelated():\n    pass"
    record = {
        "prefix": prefix,
        "suffix": suffix,
        "groundtruth": reference,
        "metadata": {
            "fpath_tuple": ["shop", "cart.py"],
            "line_no": 4,
            "context_start_characterno": 11,
        },
    }
    document = Document(
        uri=str(source), language_id="python", text=prefix + suffix,
        prefix=prefix, suffix=suffix, offset=len(prefix),
        position=Position(line=4, character=11),
    )
    retriever = JaccardSimilarityRetriever(base_dir=str(base))
    snippets = asyncio.run(retriever.retrieve(document, document.position, "shop"))
    if not snippets:
        raise RuntimeError("The example did not retrieve any context.")
    extractor = CodeQwen25PromptExtractor()
    intro = "\n".join(extractor.file_snippet_to_prompt_string(s.to_dict()) for s in snippets)
    prompt_record = {
        **record,
        "prompt": extractor.get_infilling_prompt("cart.py", intro, prefix, suffix),
        "contexts": [s.to_dict() for s in snippets],
    }
    raw_record = {**prompt_record, "choices": [{"text": raw}]}
    refined = process_single_data(str(base), raw_record)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    for name, data in [("prompts", prompt_record), ("raw", raw_record), ("refined", refined)]:
        path = output / (name + ".jsonl")
        if path.exists():
            raise FileExistsError(f"Choose a new --output-dir; {path} already exists.")
    for name, data in [("prompts", prompt_record), ("raw", raw_record), ("refined", refined)]:
        (output / (name + ".jsonl")).write_text(json.dumps(data) + "\n", encoding="utf-8")
    print("ACAR | lexical retrieval + syntax-aware refinement")
    print("Mode: CPU example with a fixed completion fixture")
    print("Target: shop/cart.py:5")
    print(f"Retrieved: {len(snippets)} snippet(s)")
    for snippet in snippets:
        print(f"  {Path(snippet.uri).relative_to(base)} | lines {snippet.start_line + 1}-{snippet.end_line + 1}")
    print("Prompt: Qwen2.5-Coder FIM with retrieved context")
    print("Raw fixture:")
    for line in raw.splitlines():
        print("  " + line if line else "")
    print("Refined:")
    for line in refined["choices"][0]["text"].splitlines():
        print("  " + line if line else "")
    print("Output: " + str(output))
    return refined


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default="result/demo", help="New directory for the three JSONL outputs")
    args = parser.parse_args()
    run(args.output_dir)


if __name__ == "__main__":
    main()
