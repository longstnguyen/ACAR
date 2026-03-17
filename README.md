# ACAR: Adaptive Context-Aware Retrieval for Repository-Level Code Completion

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](#installation)
[![Status](https://img.shields.io/badge/Research-Active-success.svg)](#)

ACAR is a repository-level Fill-in-the-Middle (FIM) framework for code completion. It combines lexical retrieval, AST/LSP structural retrieval, line-level reciprocal-rank fusion, and syntax-aware post-processing to improve completion quality under multi-file context.

Practically, this repository gives you an end-to-end workflow: build retrieval-augmented FIM prompts, run model inference, then refine completions into structurally consistent insertions. The emphasis is on staying prompt-efficient while remaining usable for research and benchmarking.

---

## Why ACAR?

Most completion pipelines are file-centric. In real repositories, relevant evidence is often distributed across files and connected by symbol-level dependencies.

If you have ever seen a completion look “locally plausible” but fail because the right definition lives in another file, that is the gap ACAR is built to address.

ACAR is designed around the idea that “good context” is rarely one thing. Sometimes the best signal is lexical overlap; other times it is structural connectivity (definitions, references, imports, and symbol neighborhoods). In practice, you want both—combined, ranked, and formatted into prompts that a FIM model can reliably consume.

ACAR addresses this by combining complementary signals:

- **Lexical retrieval** for high-overlap local patterns.
- **Structural retrieval** from AST and LSP relations for cross-file evidence.
- **Line-level fusion (RRF)** to unify lexical and structural candidates.
- **Syntax-aware refinement** to reduce malformed or misaligned insertions.

---

## Core Features

ACAR is organized as small, composable modules (retrieval, fusion, prompt building, post-processing) with scripted entrypoints for common workflows. If you only need one piece—for example, graph retrieval or truncation—you can use the modules directly.

### Hybrid Retrieval

The retriever is intentionally hybrid: one branch captures near-duplicate patterns, the other follows symbol structure across files.

- Sliding-window text retrieval using Jaccard similarity.
- Graph-based retrieval from symbol/definition/reference context.
- Unified ranking across both sources via Reciprocal Rank Fusion.

### FIM Prompt Construction

Once context is retrieved and ranked, ACAR turns it into a prompt format that FIM-capable backbones can consume reliably.

- Converts fused snippets into model-ready infilling prompts.
- Keeps retrieval context ordered and budget-aware.

### Structural Post-Processing

Generation is only half the story. ACAR adds a structural cleanup step so the inserted code aligns with the surrounding prefix/suffix.

- AST-guided parse/truncate refinement.
- Overlap-aware insertion cleanup against existing suffix/prefix.

### Research-Friendly Workflow

For day-to-day use, the repository ships thin CLI wrappers that call into the pipeline implementations.

- Scripted entrypoints for prompt build and post-processing.
- Environment-variable support for reproducible pipeline execution.

---

## Method Overview

ACAR follows a compact, repository-level FIM pipeline designed to stay both **prompt-efficient** and **structurally faithful**. Conceptually, it has an indexing/preparation step (done once per repository snapshot) and an inference step (done per completion query).

The breakdown below is the mental model to keep in mind when reading the codebase.

1. **Repository pre-processing**

- Build a **lexical corpus** by sliding-window segmentation over repository files.
- Build a lightweight **structural space** using Tree-sitter AST signals plus LSP-resolved symbol relations.

2. **Context retrieval + line-level fusion**

- Lexical branch: retrieve windows by token-set overlap (Jaccard similarity).
- Structural branch: traverse symbol-linked neighborhoods with a bounded graph walk.
- Normalize candidates into **line identities** (`file_path:line_no`) and fuse rankings via **Reciprocal Rank Fusion (RRF)**.

3. **Prompt construction + generation**

- Serialize fused snippets in ranked order under a token budget.
- Insert the local target as a backbone-specific **FIM template** (prefix / middle / suffix).

4. **Syntax-aware post-processing**

- Parse-and-truncate using AST-guided, line-aligned ancestor selection.
- Repair common delimiter issues and trim overlaps against the existing prefix/suffix.

---

## Repository Structure

The codebase is intentionally split into (i) reusable modules and (ii) workflow glue. In general, `pipelines/` contains end-to-end “do the thing” logic, while `scripts/` provides stable CLI entrypoints that call into those pipelines.

```text
.
├── context_mixer.py               # Main retrieval orchestrator
├── text_retrieval/                # Lexical retrieval modules
├── graph_retrieval/               # LSP/graph retrieval modules
├── ranking/                       # Reciprocal rank fusion
├── post_processing/               # Parse/truncate/refinement logic
├── pipelines/                     # End-to-end data/prompt/postprocess workflows
├── scripts/                       # User-facing CLI entrypoints
├── inference/                     # Model inference scripts
├── schema/                        # Shared typed data structures
├── programming_language/          # Language-specific config helpers
└── requirements.txt
```

---

## Installation

The project is pure Python. A virtual environment is recommended to keep dependencies isolated.

```bash
git clone <REPO_URL>
cd <REPO_DIR>

python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

---

## Dataset Setup

You can bootstrap all benchmark datasets with one command:

```bash
bash scripts/download_datasets.sh
```

This script downloads and extracts data into:

- `datasets/RepoEval`
- `datasets/ReccEval` (includes `Source_Code/` and `metadata.jsonl`)
- `datasets/CrossCodeEval`

After successful extraction, downloaded archive files are removed automatically.

---

## Troubleshooting

If you are using the structural/LSP retrieval components, your environment may need additional tooling beyond Python packages.

In practice, most issues come down to “can the environment resolve symbols for this repo?” and “can the parser understand the file language?”. The checklist below covers the common failure modes.

- **LSP retrieval returns empty context**: ensure the relevant language server is available and the repository you query is accessible on disk.
- **Tree-sitter parsing issues**: confirm Tree-sitter dependencies are installed from `requirements.txt` and that language IDs match supported values.

If you only need lexical retrieval + post-processing, you can still run the pipeline without relying on LSP.

---

## Command-Line Interface

ACAR exposes lightweight CLI modules under `scripts/`.

If you just want to run the pipeline, these entrypoints are the intended interface.

These modules are designed to be safe to call with `--help` (they avoid eager heavy imports), and they delegate the real work to the implementations under `pipelines/`.

```text
python -m scripts.build_prompts      --base_dir ... --input ... --output ...
python -m scripts.post_process_jsonl --base_dir ... --input ... --output ...
python -m scripts.post_process_safim [--input ...] [--output ...]
```

Use `--help` on each command for details.

---

## Quickstart

At a high level, the workflow is: (1) build prompts with retrieval context, (2) run a FIM model to generate completions, (3) post-process to improve syntactic validity and insertion alignment, and (4) optionally run the SAFIM-specific post-processing step if you are using SAFIM-format outputs. The examples below mirror that flow.

### 1) Build prompts with retrieval context

This step reads the dataset JSONL, retrieves repository context, and writes a prompt JSONL ready for inference.

```bash
python -m scripts.build_prompts \
  --base_dir datasets/ReccEval/Source_Code \
  --input datasets/ReccEval/metadata.jsonl \
  --output result/prompts.jsonl
```

### 2) Run inference

Inference consumes the prompt file and writes model generations to a new JSONL.

```bash
export ACAR_QWEN_INPUT=result/prompts.jsonl
python inference/qwen_inference.py
```

### 3) Post-process completions

Post-processing re-parses model outputs and applies syntax-aware truncation/cleanup.

```bash
python -m scripts.post_process_jsonl \
  --base_dir datasets/ReccEval/Source_Code \
  --input result/prompts_Qwen2.5-Coder-0.5B.jsonl \
  --output result/prompts_Qwen2.5-Coder-0.5B_post.jsonl
```

### 4) SAFIM post-processing pipeline

If you are running SAFIM-format outputs, this step applies the SAFIM-specific refinement routine.

```bash
python -m scripts.post_process_safim \
  --input result/qwen-safim-infillng.jsonl \
  --output result/qwen-safim-infillng-post_processed.jsonl
```

---

## Outputs

Running the pipeline produces a small number of JSONL artifacts that are easy to track and diff.

Output naming is mostly convention-based: inference derives filenames from the input prompt file, while post-processing adds a suffix (e.g., `_post`).

- **Prompt file** (from `scripts.build_prompts`): e.g., `result/prompts.jsonl`
- **Model generations** (from `inference/qwen_inference.py`): the output name is derived from the input, e.g., `result/prompts_Qwen2.5-Coder-0.5B.jsonl`
- **Post-processed generations** (from `scripts.post_process_jsonl`): e.g., `result/prompts_Qwen2.5-Coder-0.5B_post.jsonl`
- **SAFIM post-processed output** (from `scripts.post_process_safim`): e.g., `result/qwen-safim-infillng-post_processed.jsonl`

---

## Input Data Expectations

ACAR expects JSONL records with enough information to (i) define the FIM target (prefix/suffix) and (ii) locate the insertion point in the repository (metadata fields). The fields below are the minimal set used by the provided pipeline scripts.

### Prompt building input (`scripts.build_prompts`)

JSONL records should include:

- `prefix`
- `suffix`
- `metadata.fpath_tuple`
- `metadata.line_no`
- `metadata.context_start_characterno`

### General post-processing input (`scripts.post_process_jsonl`)

JSONL records should include:

- `prefix`
- `suffix`
- `metadata.*` (same indexing fields)
- `choices[0].text`

---

## Core API Example

```python
import asyncio

from context_mixer import ContextMixer
from schema.common import Document, Position


async def demo() -> None:
    mixer = ContextMixer()
    document = Document(
        uri="test/test.py",
        language_id="python",
        text="def f():\n    pass\n",
        prefix="def f():\n    ",
        suffix="pass\n",
    )
    pos = Position(line=1, character=4)
    result = await mixer.get_context(document, pos, repo="test")
    print("retrieved:", len(result["context"]))


asyncio.run(demo())
```

---

## Environment Variables

Environment variables are optional, but they are convenient for scripting and reproducible runs.

- `ACAR_BASE_DIR`: default retrieval base directory (default: `datasets/ReccEval/Source_Code`).
- `ACAR_QWEN_INPUT`: input JSONL path for `inference/qwen_inference.py`.
- `ACAR_SAFIM_INPUT`: SAFIM input JSONL path.
- `ACAR_SAFIM_OUTPUT`: SAFIM post-processed output JSONL path.

---

## Results

Across repository-level benchmarks (RepoEval, ReccEval, CrossCodeEval), ACAR consistently improves completion quality over strong baselines.

The numbers below are meant as a quick reference; for careful comparison, keep backbone, decoding settings, and dataset version fixed.

**Key findings (high level):**

- Hybrid retrieval improves both exactness (EM) and edit similarity (ES) compared with strong repository-level baselines.
- Syntax-aware post-processing is not just cleanup; removing it typically degrades structural consistency.
- Prompt construction remains interactive (sub-100ms regime in reported settings).

Selected numbers:

- ReccEval (Qwen2.5-Coder-3B): **42.98 EM / 72.46 ES**.
- CrossCodeEval (Qwen2.5-Coder-3B): **32.86 EM / 74.34 ES**.

---

## Reproducibility Notes

To make runs comparable across machines and time, it helps to record a small set of configuration details alongside outputs.

- Keep dataset paths explicit in command scripts.
- Record model checkpoint names and seeds per run.
- Ensure language-server setup is consistent when evaluating graph retrieval.

---

## Citation

If you use ACAR in your research, please cite the ACAR paper.

If you are extending the pipeline or using it as a baseline in your experiments, adding a citation in the accompanying write-up helps others trace methodology and settings.

```bibtex
@inproceedings{acar2026,
  title={Fast and Focused: Interactive Repository-Level Fill-in-the-Middle Code Completion with Hybrid Structural Retrieval},
  author={Anonymous},
  year={2026},
  booktitle={ACL Submission}
}
```

---

## Ethics Statement

This project is intended for research and evaluation of repository-level code completion.

- **Data and licensing**: benchmark datasets are typically distributed under their own terms; users are responsible for complying with the licenses and policies of any repositories/datasets they evaluate on.
- **Model outputs**: generated code may be incorrect, insecure, or non-idiomatic. Use appropriate review and testing before applying outputs in real systems.

---

## License

This repository is intended for research use. Add your preferred license file (e.g., MIT/Apache-2.0) for redistribution terms.

---

## References

- RepoEval, ReccEval, CrossCodeEval (repository-level code completion benchmarks)
- Tree-sitter (AST parsing)
- Language Server Protocol (symbol resolution) and supporting tooling
- Qwen2.5-Coder (code LLM backbone used in example inference)
