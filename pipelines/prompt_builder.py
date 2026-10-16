from context_mixer import ContextMixer
from schema.common import Document, Position
import asyncio
import os
import jsonlines
from tqdm import tqdm
from functools import lru_cache
from pathlib import Path
from prompt.fim_utils import get_prompt_extractor

from prompt.budget import fit_local_context, select_context_lines, serialize_context, token_count



@lru_cache(maxsize=4)
def get_tokenizer(model_name):
    from transformers import AutoTokenizer
    return AutoTokenizer.from_pretrained(model_name)


def process_single_data(base_dir, data, context_mixer=None, tokenizer=None,
                        model_name="Qwen/Qwen2.5-Coder-0.5B", context_budget=2048, input_budget=8000,
                        prompt_template="qwen2.5"):
    context_mixer = context_mixer if context_mixer is not None else ContextMixer(base_dir=base_dir)
    prompt_extractor = get_prompt_extractor(prompt_template)
    language_id = "python"
    file_path = os.path.join(base_dir, *data["metadata"]["fpath_tuple"])

    document = Document(
        uri=file_path,
        language_id=language_id, 
        text=data["prefix"] + data["suffix"], 
        prefix=data["prefix"], 
        suffix=data["suffix"], 
        offset=len(data["prefix"]), 
        position=Position(line=data["metadata"]["line_no"], character=data["metadata"]["context_start_characterno"])
    )

    tokenizer = tokenizer if tokenizer is not None else get_tokenizer(model_name)
    filename = data["metadata"]["fpath_tuple"][-1]
    prefix, suffix = fit_local_context(tokenizer, prompt_extractor, filename,
                                       data["prefix"], data["suffix"], input_budget)
    def select(lines):
        return select_context_lines(lines, tokenizer, prompt_extractor, filename, prefix, suffix,
                                    context_budget, input_budget)
    repo = data["metadata"]["fpath_tuple"][0]
    contexts = asyncio.run(context_mixer.get_context(document, document.position, repo, select_lines=select))
    intro = serialize_context(prompt_extractor, contexts['context'])
    prompt = prompt_extractor.get_infilling_prompt(filename, intro, prefix, suffix)
    return {**data, 'prompt': prompt, 'contexts': [span.to_dict() for span in contexts['context']],
            'prompt_tokens': token_count(tokenizer, prompt),
            'context_tokens': token_count(tokenizer, intro), 'tokenizer': model_name,
            'prompt_template': prompt_template}



def process_jsonl_file(base_dir, input_file, output_file, model_name="Qwen/Qwen2.5-Coder-0.5B",
                       context_budget=2048, input_budget=8000, prompt_template="qwen2.5"):
    tokenizer = get_tokenizer(model_name)
    results = []
    context_mixer = ContextMixer(base_dir=base_dir)
    
    # Read input JSONL file
    with jsonlines.open(input_file) as reader:
        # Wrap with tqdm for progress bar
        for data in tqdm(reader, desc="Processing data"):
            try:
                result = process_single_data(base_dir, data, context_mixer=context_mixer, tokenizer=tokenizer,
                                             model_name=model_name, context_budget=context_budget, input_budget=input_budget,
                                             prompt_template=prompt_template)
                results.append(result)
            except Exception as e:
                print(f"Error processing data: {e}")
                # Add the original data with error information
                results.append({"error": str(e), "original": data})
    
    # Write results to output JSONL file
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    with jsonlines.open(output_file, mode='w') as writer:
        writer.write_all(results)
    
    print(f"Processed {len(results)} items. Results saved to {output_file}")

if __name__ == "__main__":
    from scripts.build_prompts import main
    main()
