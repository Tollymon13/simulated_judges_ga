#!/usr/bin/env python3
"""Compare vanilla, reflection, and guardian credences on probability v2.

Help is movement toward Debater A, the correct side. At each section the
change is the revised credence minus the credence from before the revision.
The risk summary helped when the guardian's mean change is larger than the
reflection arm's. Section-4 means show where each arm finished. The ALLOW or
INTERVENE label is not part of this report.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECTIONS = (1, 2, 3, 4)


def load_jsonl(path):
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def credence_from_turn(turn, key):
    parsed = turn.get(key)
    if not parsed:
        return None
    return parsed["credence_debater_a"]


def mean(values):
    if not values:
        return None
    return sum(values) / len(values)


def final_credence(record, arm):
    turns = [turn for turn in record.get("turns") or [] if turn.get("section") == 4]
    if not turns:
        return None
    key = "parsed" if arm == "vanilla" else "revision_parsed"
    return credence_from_turn(turns[0], key)


def arm_summary(name, records, priors):
    by_index = {record["judge_index"]: record for record in records}
    finals = []
    for draw in priors:
        record = by_index.get(draw["judge_index"])
        if record is None or record.get("status") != "ok":
            continue
        credence = final_credence(record, name)
        if credence is None:
            continue
        finals.append(credence)
    return {
        "n": len(finals),
        "mean_section_4": mean(finals),
        "n_above_50": sum(value > 50 for value in finals),
    }


def revision_changes(records):
    by_section = {section: [] for section in SECTIONS}
    for record in records:
        if record.get("status") != "ok":
            continue
        for turn in record.get("turns") or []:
            section = turn.get("section")
            if section not in by_section:
                continue
            initial = credence_from_turn(turn, "initial_parsed")
            revised = credence_from_turn(turn, "revision_parsed")
            if initial is None or revised is None:
                continue
            by_section[section].append(revised - initial)
    pooled = [value for values in by_section.values() for value in values]
    return {
        "by_section": {
            str(section): {"n": len(by_section[section]), "mean_change": mean(by_section[section])}
            for section in SECTIONS
        },
        "mean_change": mean(pooled),
    }


def build_report(priors, vanilla, reflection, guardian):
    reflection_change = revision_changes(reflection)
    guardian_change = revision_changes(guardian)
    reflection_mean = reflection_change["mean_change"]
    guardian_mean = guardian_change["mean_change"]
    helped = None
    if reflection_mean is not None and guardian_mean is not None:
        helped = guardian_mean > reflection_mean
    return {
        "debate": "v2",
        "correct_side": "Debater A",
        "vanilla": arm_summary("vanilla", vanilla, priors),
        "reflection": arm_summary("reflection", reflection, priors),
        "guardian": arm_summary("guardian", guardian, priors),
        "reflection_revision_change": reflection_change,
        "guardian_revision_change": guardian_change,
        "guardian_minus_reflection": (
            None
            if reflection_mean is None or guardian_mean is None
            else guardian_mean - reflection_mean
        ),
        "risk_summary_helped": helped,
    }


def build_blind_report(priors, reflection, guardian, blind):
    reflection_change = revision_changes(reflection)
    guardian_change = revision_changes(guardian)
    blind_change = revision_changes(blind)
    guardian_mean = guardian_change["mean_change"]
    blind_mean = blind_change["mean_change"]
    smaller = None
    if guardian_mean is not None and blind_mean is not None:
        smaller = blind_mean < guardian_mean
    return {
        "debate": "v2",
        "correct_side": "Debater A",
        "reflection_revision_change": reflection_change,
        "guardian_revision_change": guardian_change,
        "blind_revision_change": blind_change,
        "blind_minus_guardian": (
            None if guardian_mean is None or blind_mean is None else blind_mean - guardian_mean
        ),
        "blind_change_smaller_than_guardian": smaller,
        "guardian": arm_summary("guardian", guardian, priors),
        "blind": arm_summary("guardian", blind, priors),
    }


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--debate", choices=("v1", "v2"), default="v2")
    parser.add_argument("--blind", action="store_true")
    args = parser.parse_args(argv)
    root = ROOT / "results" / "persona_baseline" / args.debate
    priors = json.loads((root / "human_priors.json").read_text(encoding="utf-8"))["draws"]
    if args.blind:
        report = build_blind_report(
            priors,
            load_jsonl(root / "reflection" / "judges.jsonl"),
            load_jsonl(root / "guardian" / "judges.jsonl"),
            load_jsonl(root / "guardian_blind" / "judges.jsonl"),
        )
        out_path = root / "blind_comparison.json"
        out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(
            "mean revision change reflection=%s guardian=%s blind=%s smaller=%s"
            % (
                report["reflection_revision_change"]["mean_change"],
                report["guardian_revision_change"]["mean_change"],
                report["blind_revision_change"]["mean_change"],
                report["blind_change_smaller_than_guardian"],
            )
        )
        print("wrote %s" % out_path)
        return
    report = build_report(
        priors,
        load_jsonl(root / "judges.jsonl"),
        load_jsonl(root / "reflection" / "judges.jsonl"),
        load_jsonl(root / "guardian" / "judges.jsonl"),
    )
    report["debate"] = args.debate
    out_path = root / "arm_comparison.json"
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for name in ("vanilla", "reflection", "guardian"):
        item = report[name]
        print(
            "%s n=%s mean_s4=%s above_50=%s"
            % (name, item["n"], item["mean_section_4"], item["n_above_50"])
        )
    print(
        "mean revision change reflection=%s guardian=%s helped=%s"
        % (
            report["reflection_revision_change"]["mean_change"],
            report["guardian_revision_change"]["mean_change"],
            report["risk_summary_helped"],
        )
    )
    print("wrote %s" % out_path)


if __name__ == "__main__":
    main()
