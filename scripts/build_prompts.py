import argparse


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate infilling prompts with retrieval context"
    )
    parser.add_argument("--base_dir", type=str, required=True)
    parser.add_argument("--input", type=str, required=True)
    parser.add_argument("--output", type=str, required=True)
    args = parser.parse_args()

    from pipelines.prompt_builder import process_jsonl_file

    process_jsonl_file(args.base_dir, args.input, args.output)


if __name__ == "__main__":
    main()
