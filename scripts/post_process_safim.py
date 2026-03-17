import argparse
import os


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Post-process SAFIM completions with ACAR structural refinement"
    )
    parser.add_argument(
        "--input",
        type=str,
        default=os.getenv("ACAR_SAFIM_INPUT", "result/qwen-safim-infillng.jsonl"),
    )
    parser.add_argument(
        "--output",
        type=str,
        default=os.getenv(
            "ACAR_SAFIM_OUTPUT", "result/qwen-safim-infillng-post_processed.jsonl"
        ),
    )
    args = parser.parse_args()

    from pipelines.safim_post_processing import process_jsonl_file

    process_jsonl_file(args.input, args.output)


if __name__ == "__main__":
    main()
