#!/usr/bin/env python3
"""Compare the varied-persona section-4 credences with humans and the saved personas.

The check passes when the mean stays within 5 points of the paired humans, the
standard deviation moves toward the human spread, and the count above 50 moves
toward the human count.
"""

import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_jsonl(path):
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def mean(values):
    if not values:
        return None
    return sum(values) / len(values)


def spread(values):
    if len(values) < 2:
        return None
    return statistics.stdev(values)


def section_4(records, key):
    values = []
    for record in records:
        if record.get("status") != "ok":
            continue
        for turn in record.get("turns") or []:
            if turn.get("section") != 4:
                continue
            parsed = turn.get(key) or {}
            credence = parsed.get("credence_debater_a")
            if credence is not None:
                values.append(credence)
    return values


def side(name, values):
    return {
        "name": name,
        "n": len(values),
        "mean_section_4": mean(values),
        "stdev_section_4": spread(values),
        "n_above_50": sum(value > 50 for value in values),
    }


def closer(new, old, target):
    if None in (new, old, target):
        return None
    return abs(new - target) < abs(old - target)


def one_debate(debate):
    priors = json.loads(
        (ROOT / "results" / "persona_varied" / debate / "human_priors.json").read_text(
            encoding="utf-8"
        )
    )["draws"]
    humans = [draw["human_section_4"] for draw in priors]
    varied = section_4(load_jsonl(ROOT / "results" / "persona_varied" / debate / "judges.jsonl"), "parsed")
    saved = section_4(
        load_jsonl(ROOT / "results" / "persona_baseline" / debate / "judges.jsonl"), "parsed"
    )
    human_side = side("humans", humans)
    varied_side = side("varied", varied)
    saved_side = side("saved_persona", saved)
    mean_gap = None
    if varied_side["mean_section_4"] is not None:
        mean_gap = varied_side["mean_section_4"] - human_side["mean_section_4"]
    within_5 = None if mean_gap is None else abs(mean_gap) <= 5
    spread_closer = closer(
        varied_side["stdev_section_4"],
        saved_side["stdev_section_4"],
        human_side["stdev_section_4"],
    )
    above_closer = closer(
        varied_side["n_above_50"], saved_side["n_above_50"], human_side["n_above_50"]
    )
    passed = bool(within_5 and spread_closer and above_closer)
    return {
        "debate": debate,
        "humans": human_side,
        "varied": varied_side,
        "saved_persona": saved_side,
        "mean_minus_humans": mean_gap,
        "mean_within_5": within_5,
        "spread_closer_to_humans": spread_closer,
        "above_50_closer_to_humans": above_closer,
        "passed": passed,
    }


def main():
    report = {"v1": one_debate("v1"), "v2": one_debate("v2")}
    out_path = ROOT / "results" / "persona_varied" / "comparison.json"
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for debate, item in report.items():
        print(
            "%s varied_mean=%s human_mean=%s within_5=%s spread_closer=%s above_closer=%s passed=%s"
            % (
                debate,
                item["varied"]["mean_section_4"],
                item["humans"]["mean_section_4"],
                item["mean_within_5"],
                item["spread_closer_to_humans"],
                item["above_50_closer_to_humans"],
                item["passed"],
            )
        )
    print("wrote %s" % out_path)


if __name__ == "__main__":
    main()
