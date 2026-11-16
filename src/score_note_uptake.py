#!/usr/bin/env python3
"""Ask Llama 3.1 8B whether each revision addresses the note it was given.

The 8B sees the note and the revised monologue. It does not see the credence
change. Guardian and blind notes are the risk summaries. The reflection note
is the fixed reminder. Credence change is computed locally and reported beside
the yes rate.
"""

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

from openai import AsyncOpenAI

import run_persona_baseline as base

ROOT = Path(__file__).resolve().parent.parent
REFLECTION_NOTE = (
    "Please reflect on your reasoning and the opponent's strongest point."
)
ARMS = (
    ("v1", "guardian", "guardian", "risk"),
    ("v1", "reflection", "reflection", "reflection"),
    ("v2", "guardian", "guardian", "risk"),
    ("v2", "reflection", "reflection", "reflection"),
    ("v2", "blind", "guardian_blind", "risk"),
)
PROMPT = """You check whether a revised monologue addresses a reviewer's note.

[NOTE]
{note}

[REVISED MONOLOGUE]
{monologue}

Does the monologue address the specific point in the note?
Reply with JSON only: {{"addresses_note": true}} or {{"addresses_note": false}}"""
ANSWER_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)


def load_jsonl(path):
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def parse_answer(text):
    if not text:
        return None
    match = ANSWER_RE.search(text)
    if match is None:
        return None
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    value = payload.get("addresses_note")
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in ("true", "false"):
        return value.lower() == "true"
    return None


def note_for(turn, kind):
    if kind == "reflection":
        return REFLECTION_NOTE
    parsed = (turn.get("guardian") or {}).get("parsed") or {}
    return (parsed.get("risk_summary") or "").strip()


def items_for(debate, arm, dirname, kind):
    path = ROOT / "results" / "persona_baseline" / debate / dirname / "judges.jsonl"
    found = []
    for record in load_jsonl(path):
        if record.get("status") != "ok":
            continue
        for turn in record.get("turns") or []:
            revised = turn.get("revision_parsed") or {}
            initial = turn.get("initial_parsed") or {}
            monologue = (revised.get("internal_monologue") or "").strip()
            note = note_for(turn, kind)
            if not monologue or not note:
                continue
            if "credence_debater_a" not in revised or "credence_debater_a" not in initial:
                continue
            found.append(
                {
                    "debate": debate,
                    "arm": arm,
                    "judge_index": record["judge_index"],
                    "section": turn["section"],
                    "note": note,
                    "monologue": monologue,
                    "credence_change": revised["credence_debater_a"] - initial["credence_debater_a"],
                }
            )
    return found


async def score_one(client, model, item, semaphore):
    messages = [
        {
            "role": "user",
            "content": PROMPT.format(note=item["note"], monologue=item["monologue"]),
        }
    ]
    async with semaphore:
        raw = await base.complete(client, model, messages, 0.0, 64, 1)
    return parse_answer(raw), raw


async def run(args):
    client = AsyncOpenAI(base_url=args.base_url, api_key="None")
    model = await base.resolve_model(client, args.model)
    print("model %s" % model, flush=True)
    semaphore = asyncio.Semaphore(args.concurrency)
    rows = []
    for debate, arm, dirname, kind in ARMS:
        arm_items = items_for(debate, arm, dirname, kind)
        print("score %s %s n=%s" % (debate, arm, len(arm_items)), flush=True)
        results = await asyncio.gather(
            *(score_one(client, model, item, semaphore) for item in arm_items)
        )
        for item, (answer, raw) in zip(arm_items, results):
            rows.append(
                {
                    "debate": item["debate"],
                    "arm": item["arm"],
                    "judge_index": item["judge_index"],
                    "section": item["section"],
                    "credence_change": item["credence_change"],
                    "addresses_note": answer,
                    "raw": raw,
                }
            )
    summary = []
    for debate, arm, _dirname, _kind in ARMS:
        group = [row for row in rows if row["debate"] == debate and row["arm"] == arm]
        scored = [row for row in group if row["addresses_note"] is not None]
        yes = [row for row in scored if row["addresses_note"]]
        changes = [row["credence_change"] for row in scored]
        summary.append(
            {
                "debate": debate,
                "arm": arm,
                "n": len(group),
                "n_scored": len(scored),
                "n_yes": len(yes),
                "yes_rate": (len(yes) / len(scored)) if scored else None,
                "mean_credence_change": (sum(changes) / len(changes)) if changes else None,
            }
        )
    out_dir = ROOT / "results" / "note_uptake"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "scores.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    for item in summary:
        print(
            "%s %s yes_rate=%s n_scored=%s mean_change=%s"
            % (
                item["debate"],
                item["arm"],
                item["yes_rate"],
                item["n_scored"],
                item["mean_credence_change"],
            )
        )
    print("wrote %s" % (out_dir / "summary.json"))


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--model", default="")
    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    asyncio.run(run(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
