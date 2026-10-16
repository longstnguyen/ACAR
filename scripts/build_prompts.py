import argparse


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate infilling prompts with retrieval context"
    )
    parser.add_argument("--base_dir", type=str, required=True)
    parser.add_argument("--input", type=str, required=True)
    parser.add_argument("--output", type=str, required=True)
    parser.add_argument("--model", default="Qwen/Qwen2.5-Coder-0.5B", help="Tokenizer checkpoint")
    parser.add_argument("--context-budget", type=int, default=2048)
    parser.add_argument("--input-budget", type=int, default=8000)
    args = parser.parse_args()
    if args.context_budget < 0 or args.input_budget <= 0:
        parser.error("Token budgets must be nonnegative, with a positive input budget")

    from pipelines.prompt_builder import process_jsonl_file

    process_jsonl_file(args.base_dir, args.input, args.output, model_name=args.model,
                       context_budget=args.context_budget, input_budget=args.input_budget)


if __name__ == "__main__":
    main()
