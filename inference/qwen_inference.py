import torch
import tqdm
import json
import gc
import os
from transformers import AutoModelForCausalLM, AutoTokenizer


class Tools:
    @staticmethod
    def load_jsonl(path):
        with open(path, "r") as f:
            return [json.loads(line) for line in f.readlines()]

    @staticmethod
    def dump_jsonl(obj, path):
        with open(path, "w") as f:
            for line in obj:
                f.write(json.dumps(line) + "\n")


class QwenInference:
    def __init__(self, model_name="Qwen/Qwen2.5-Coder-0.5B"):
        """
        Initialize the Qwen model for inference with individual record processing.

        Args:
            model_name (str): The model name or path
        """
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model_name = model_name

        # Initialize tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name,
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        # Initialize model
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name, device_map="auto"
        ).eval()
        print(f"Model loaded on device: {self.model.device}")

    def _clear_cuda_cache(self):
        """Clear CUDA cache to free up memory."""
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            gc.collect()

    def _generate_single(self, prompt, max_new_tokens=10, temperature=0.0, top_p=0.2):
        """Generate completion for a single prompt."""
        print("Processing prompt:", prompt[:50] + "..." if len(prompt) > 50 else prompt)

        try:
            # Clear cache before processing
            self._clear_cuda_cache()

            # Tokenize
            inputs = self.tokenizer(
                [prompt],
                return_tensors="pt",
            )

            # Move inputs to the same device as model
            input_ids = inputs["input_ids"].to(self.model.device)
            attention_mask = inputs["attention_mask"].to(self.model.device)

            # Generate
            with torch.no_grad():
                outputs = self.model.generate(
                    input_ids=input_ids,
                    max_new_tokens=max_new_tokens,
                    do_sample=False,
                )[0]

            # Decode and remove prompt from response
            gen_text = self.tokenizer.decode(
                outputs[len(inputs.input_ids[0]) :], skip_special_tokens=True
            )

            # Clear intermediate tensors
            del inputs, input_ids, attention_mask, outputs
            self._clear_cuda_cache()

            return gen_text

        except RuntimeError as e:
            if "out of memory" in str(e):
                self._clear_cuda_cache()
                raise RuntimeError(
                    "Out of memory error when processing. Try reducing max_new_tokens."
                )
            else:
                raise e

    def process_file(self, file_path, max_new_tokens=100, temperature=0.0, top_p=0.2):
        """Generate completions for all prompts in a JSONL file, processing one record at a time."""
        print(f"Generating from {file_path}")
        print(f"Model device: {self.model.device}")
        print(f"Max new tokens: {max_new_tokens}")

        # Load data
        lines = Tools.load_jsonl(file_path)
        new_lines = []

        # Process each record individually
        for i, line in enumerate(tqdm.tqdm(lines)):
            prompt = f"{line['prompt']}\n"
            try:
                generated_text = self._generate_single(
                    prompt,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature,
                    top_p=top_p,
                )

                output_line = dict(line)
                output_line["choices"] = [{"text": generated_text}]
                new_lines.append(output_line)

                # Log progress periodically
                if (i + 1) % 10 == 0:
                    print(f"Processed {i + 1}/{len(lines)} records")

            except Exception as e:
                print(f"Error processing record {i}: {str(e)}")
                # Add empty result to maintain order
                output_line = dict(line)
                output_line["choices"] = [{"text": "ERROR: " + str(e)}]
                new_lines.append(output_line)

        print(f"Generated {len(new_lines)} samples")

        # Save results
        output_path = file_path.replace(
            ".jsonl", f'_{self.model_name.split("/")[-1]}.jsonl'
        )
        Tools.dump_jsonl(new_lines, output_path)
        return output_path


def main():
    file_path = os.getenv("ACAR_QWEN_INPUT", "result/prompts.jsonl")

    print("file_path", file_path)

    qwen = QwenInference()
    qwen.process_file(file_path)


if __name__ == "__main__":
    main()
    # Local demo snippets removed to keep this file free of environment-specific sample data.
