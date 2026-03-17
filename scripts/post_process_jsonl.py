import argparse


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Post-process model completions with ACAR structural refinement"
    )
    parser.add_argument("--base_dir", type=str, required=True)
    parser.add_argument("--input", type=str, required=True)
    parser.add_argument("--output", type=str, required=True)
    args = parser.parse_args()

    from pipelines.post_process_jsonl import process_jsonl_file

    process_jsonl_file(args.base_dir, args.input, args.output)


if __name__ == "__main__":
    main()
