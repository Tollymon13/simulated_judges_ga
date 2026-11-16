#!/usr/bin/env python3
"""Compare persona final credences with the paired human final credences.

A transcript matches when the personas' mean section-4 credence is within
5 points of the mean for the humans whose priors were injected. The section-1
gap is recorded only to show whether the anchor was followed.
"""

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOLERANCE = 5.0


def mean(values):
    if not values:
        return None
    return sum(values) / len(values)


def load_jsonl(path):
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def credence_at(record, section_number):
    for turn in record.get("turns") or []:
        if turn.get("section") == section_number and turn.get("parsed"):
            return turn["parsed"]["credence_debater_a"]
    return None


def paired_means(draws, judges, section_number, human_key):
    by_index = {record["judge_index"]: record for record in judges}
    human_values = []
    persona_values = []
    for draw in draws:
        record = by_index.get(draw["judge_index"])
        if record is None:
            continue
        persona = credence_at(record, section_number)
        if persona is None:
            continue
        human_values.append(draw[human_key])
        persona_values.append(persona)
    human_mean = mean(human_values)
    persona_mean = mean(persona_values)
    if human_mean is None:
        difference = None
    else:
        difference = persona_mean - human_mean
    return {
        "n_pairs": len(persona_values),
        "human_mean": human_mean,
        "persona_mean": persona_mean,
        "difference": difference,
    }


def compare(debate):
    directory = HERE / "results" / "persona_baseline" / debate
    priors = json.loads((directory / "human_priors.json").read_text(encoding="utf-8"))
    judges = load_jsonl(directory / "judges.jsonl")
    section_1 = paired_means(priors["draws"], judges, 1, "human_section_1")
    section_4 = paired_means(priors["draws"], judges, 4, "human_section_4")
    section_1["within_5_points"] = (
        section_1["difference"] is not None and abs(section_1["difference"]) <= TOLERANCE
    )
    section_4["within_5_points"] = (
        section_4["difference"] is not None and abs(section_4["difference"]) <= TOLERANCE
    )
    return {
        "debate": debate,
        "debate_name": priors["debate_name"],
        "tolerance_points": TOLERANCE,
        "matches_humans": section_4["within_5_points"],
        "section_1_anchor": section_1,
        "section_4": section_4,
    }


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--debate", choices=("v1", "v2"), required=True)
    args = parser.parse_args(argv)
    report = compare(args.debate)
    out_path = HERE / "results" / "persona_baseline" / args.debate / "comparison.json"
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    section_4 = report["section_4"]
    print(
        "%s section4 human=%.2f persona=%.2f diff=%.2f match=%s"
        % (
            args.debate,
            section_4["human_mean"],
            section_4["persona_mean"],
            section_4["difference"],
            report["matches_humans"],
        )
    )
    print("wrote %s" % out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
