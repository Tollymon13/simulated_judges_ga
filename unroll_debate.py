#!/usr/bin/env python3
"""Flatten a DC-Debates claim tree into the four sections a human judge saw.

The walk is recursive. Protocol nodes ("Therefore, you should reject ...")
are hidden, and their children are still visited. Speaker labels in the
section text are Debater A and Debater B. The role map is stored in the JSON
for analysis and is omitted from the markdown a persona judge should read.
"""

import argparse
import json
import os
import re
import sys

META_PREFIX = "Therefore, you should reject"
XDEF_RE = re.compile(r'<a\s+xdef="[^"]*"\s*>(.*?)</a>', re.DOTALL)
DEF_RE = re.compile(r'<def\s+id="([^"]+)"\s*>(.*?)</def>', re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")

REACTION_TEXT = {
    "Yes": "fully agrees",
    "No": "objects",
    "Yes but omits key info": "agrees but thinks this omits key info",
}

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INPUTS = [
    os.path.join(HERE, "Probability_-_expected_number_of_rolls.json"),
    os.path.join(HERE, "Probability_-_expected_number_of_rolls_v2.json"),
]


def clean_text(text):
    text = XDEF_RE.sub(r"\1", text or "")
    text = TAG_RE.sub("", text)
    return text.strip()


def is_meta(text):
    return clean_text(text).startswith(META_PREFIX)


def parse_definitions(raw):
    definitions = []
    for def_id, body in DEF_RE.findall(raw or ""):
        definitions.append({"id": def_id, "text": clean_text(body)})
    return definitions


def section_for_level(level):
    if level <= 1:
        return 1
    if level > 7:
        raise ValueError("unexpected claim level %s" % level)
    return (level // 2) + 1


def collect_claims(node, sibling_index, found):
    """Depth-first walk. Meta nodes are omitted and their children kept."""
    if not is_meta(node.get("text", "")):
        found.append((node, sibling_index))
    for index, child in enumerate(node.get("children") or []):
        collect_claims(child, index, found)


def speaker_label(role, swap_order):
    if role == "questioner":
        return None
    honest_is_a = not swap_order
    if role == "honest":
        return "Debater A" if honest_is_a else "Debater B"
    if role == "dishonest":
        return "Debater B" if honest_is_a else "Debater A"
    raise ValueError("unknown debater role %r" % role)


def opponent_role(role):
    if role == "honest":
        return "dishonest"
    if role == "dishonest":
        return "honest"
    raise ValueError("no opponent for role %r" % role)


def reaction_for(node, swap_order):
    role = node["debater"]
    other = opponent_role(role)
    raw = (node.get(other + "_response") or "").strip()
    if not raw:
        return None
    phrase = REACTION_TEXT.get(raw)
    if phrase is None:
        raise ValueError("unknown reaction %r on claim %s" % (raw, node.get("id")))
    return {"speaker": speaker_label(other, swap_order), "text": phrase}


def unroll(data, source_name, swap_order):
    found = []
    collect_claims(data["root"], 0, found)

    question = None
    turns_by_section = {1: [], 2: [], 3: [], 4: []}
    for node, sibling_index in found:
        level = node["level"]
        if level == 0 or node["debater"] == "questioner":
            question = clean_text(node["text"])
            continue
        label = speaker_label(node["debater"], swap_order)
        turn = {
            "speaker": label,
            "claim_id": node["id"],
            "level": level,
            "text": clean_text(node["text"]),
        }
        reaction = reaction_for(node, swap_order)
        if reaction is not None:
            turn["reaction"] = reaction
        turns_by_section[section_for_level(level)].append((sibling_index, turn))

    if question is None:
        raise ValueError("debate %s has no question node" % source_name)

    sections = []
    for section_number in (1, 2, 3, 4):
        ordered = sorted(
            turns_by_section[section_number],
            key=lambda item: (
                item[1]["level"],
                0 if item[1]["speaker"] == "Debater A" else 1,
                item[0],
            ),
        )
        public_turns = []
        for _, turn in ordered:
            public = {
                "speaker": turn["speaker"],
                "claim_id": turn["claim_id"],
                "text": turn["text"],
            }
            if "reaction" in turn:
                public["reaction"] = turn["reaction"]
            public_turns.append(public)
        sections.append({"section": section_number, "turns": public_turns})

    if swap_order:
        debater_a, debater_b = "dishonest", "honest"
    else:
        debater_a, debater_b = "honest", "dishonest"

    return {
        "source": source_name,
        "question": question,
        "definitions": parse_definitions(data.get("defs_and_sources", "")),
        "debater_a": debater_a,
        "debater_b": debater_b,
        "sections": sections,
    }


def render_markdown(payload):
    lines = [
        "# %s" % payload["source"],
        "",
        "Show these sections to a judge one at a time. The file does not say which debater is honest.",
        "",
    ]
    for section in payload["sections"]:
        lines.append("## Section %d" % section["section"])
        lines.append("")
        if section["section"] == 1:
            lines.append("**Question**")
            lines.append("")
            lines.append(payload["question"])
            lines.append("")
            if payload["definitions"]:
                lines.append("**Glossary**")
                lines.append("")
                for item in payload["definitions"]:
                    lines.append("- **%s:** %s" % (item["id"], item["text"]))
                lines.append("")
        for turn in section["turns"]:
            lines.append(
                "**%s** (claim %s): %s"
                % (turn["speaker"], turn["claim_id"], turn["text"])
            )
            lines.append("")
            if "reaction" in turn:
                reaction = turn["reaction"]
                lines.append("> %s %s." % (reaction["speaker"], reaction["text"]))
                lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def output_paths(input_path, out_dir, swap_order):
    stem = os.path.splitext(os.path.basename(input_path))[0]
    if swap_order:
        stem += ".swapped"
    return (
        os.path.join(out_dir, stem + ".sections.json"),
        os.path.join(out_dir, stem + ".sections.md"),
    )


def write_unrolled(input_path, out_dir, swap_order):
    with open(input_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    payload = unroll(data, os.path.basename(input_path), swap_order)
    json_path, md_path = output_paths(input_path, out_dir, swap_order)
    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    with open(md_path, "w", encoding="utf-8") as handle:
        handle.write(render_markdown(payload))
    return json_path, md_path, payload


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "inputs",
        nargs="*",
        help="Debate JSON files. Defaults to both probability transcripts.",
    )
    parser.add_argument(
        "--out-dir",
        default=os.path.join(HERE, "unrolled"),
        help="Directory for the section files.",
    )
    parser.add_argument(
        "--swap-order",
        action="store_true",
        help="Label the dishonest debater as Debater A (the other study order).",
    )
    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    inputs = args.inputs or DEFAULT_INPUTS
    os.makedirs(args.out_dir, exist_ok=True)
    for input_path in inputs:
        json_path, md_path, payload = write_unrolled(
            input_path, args.out_dir, args.swap_order
        )
        counts = [len(section["turns"]) for section in payload["sections"]]
        print("%s -> %s" % (os.path.basename(input_path), json_path))
        print("  sections: %s" % counts)
        print("  markdown: %s" % md_path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
