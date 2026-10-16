"""Score saved completions using exact match and character-level edit similarity."""

import argparse
import json


def edit_distance(left, right):
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[j] + 1, previous[j - 1] + (a != b)))
        previous = current
    return previous[-1]


def score_records(records, reference_field="groundtruth"):
    count = matches = 0
    similarity = 0.0
    for number, record in enumerate(records, 1):
        if "error" in record:
            raise ValueError(f"Record {number} contains a pipeline error; resolve it before scoring.")
        try:
            prediction = record["choices"][0]["text"]
            reference = record[reference_field]
        except (KeyError, IndexError, TypeError) as error:
            raise ValueError(f"Record {number} needs choices[0].text and {reference_field!r}.") from error
        if not isinstance(prediction, str) or not isinstance(reference, str):
            raise ValueError(f"Record {number}: prediction and reference must be strings.")
        if prediction.startswith("ERROR: "):
            raise ValueError(f"Record {number} contains an inference error; resolve it before scoring.")
        count += 1
        matches += prediction == reference
        length = max(len(prediction), len(reference))
        similarity += 1 - edit_distance(prediction, reference) / length if length else 1.0
    if count == 0:
        raise ValueError("No records to evaluate.")
    return {"n": count, "EM": round(100 * matches / count, 4), "ES": round(100 * similarity / count, 4)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--reference-field", default="groundtruth")
    args = parser.parse_args()
    try:
        with open(args.input, encoding="utf-8") as stream:
            records = (json.loads(line) for line in stream if line.strip())
            scores = score_records(records, args.reference_field)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(scores, indent=2))


if __name__ == "__main__":
    main()
