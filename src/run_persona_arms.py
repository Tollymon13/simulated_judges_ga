#!/usr/bin/env python3
"""Guardian and reflection arms for the 50 probability-v2 persona judges.

Each section the persona writes a monologue and credences. The guardian arm
then always shows that judge a risk summary and asks for a revision. The
ALLOW or INTERVENE label is stored and is not shown to the judge. The
reflection arm uses a fixed reminder instead of a guardian note. The saved
vanilla run is not repeated.
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
GUARDIAN_PATH = ROOT / "prompts" / "guardian_angel.yaml"
GUARDIAN_TEMPERATURE = 0.2
PERSONA_TEMPERATURE = 0.6
REVISION_INSTRUCTION = """A reviewer read your latest reasoning and wrote the note below. The reviewer is not telling you which debater is correct. Read the note and revise your monologue and credences.

{risk_summary}

Output exactly:
INTERNAL_MONOLOGUE: [2-3 sentences in the first person]
CREDENCE_DEBATER_A: [integer 1-99]
CREDENCE_DEBATER_B: [100 minus Debater A's credence]"""
REFLECTION_INSTRUCTION = """Please reflect on your reasoning and the opponent's strongest point. Generate a REVISED_MONOLOGUE and REVISED_CREDENCE.

Output exactly:
REVISED_MONOLOGUE: [2-3 sentences in the first person]
REVISED_CREDENCE_DEBATER_A: [integer 1-99]
REVISED_CREDENCE_DEBATER_B: [100 minus Debater A's credence]"""


def load_guardian_prompts(path):
    text = path.read_text(encoding="utf-8")
    blocks = {}
    current = None
    lines = []
    for line in text.splitlines():
        if line in ("system: |", "user: |"):
            if current is not None:
                blocks[current] = "\n".join(lines).strip()
            current = line.split(":", 1)[0]
            lines = []
            continue
        if current is None:
            continue
        if line.startswith("  "):
            lines.append(line[2:])
        elif line == "":
            lines.append("")
        else:
            raise ValueError("unexpected guardian yaml line: %s" % line)
    if current is not None:
        blocks[current] = "\n".join(lines).strip()
    if "system" not in blocks or "user" not in blocks:
        raise ValueError("guardian yaml needs system and user blocks")
    return blocks["system"], blocks["user"]


def parse_guardian(text):
    if not text:
        return None
    body = text.strip()
    body = re.sub(r"^```(?:json)?\s*", "", body)
    body = re.sub(r"\s*```$", "", body)
    start = body.find("{")
    end = body.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        payload = json.loads(body[start : end + 1])
    except json.JSONDecodeError:
        return None
    verdict = str(payload.get("verdict", "")).strip().upper()
    principle = str(payload.get("principle_at_risk", "")).strip()
    summary = str(payload.get("risk_summary", "")).strip()
    if verdict not in ("ALLOW", "INTERVENE") or not principle or not summary:
        return None
    return {
        "verdict": verdict,
        "principle_at_risk": principle,
        "risk_summary": summary,
    }


def parse_revision(text):
    parsed = base.parse_reply(text)
    if parsed is not None:
        return parsed
    rewritten = text or ""
    rewritten = rewritten.replace("REVISED_MONOLOGUE", "INTERNAL_MONOLOGUE")
    rewritten = rewritten.replace("REVISED_CREDENCE_DEBATER_A", "CREDENCE_DEBATER_A")
    rewritten = rewritten.replace("REVISED_CREDENCE_DEBATER_B", "CREDENCE_DEBATER_B")
    return base.parse_reply(rewritten)


def credence_block(parsed):
    return "Debater A: %s%%\nDebater B: %s%%" % (
        parsed["credence_debater_a"],
        parsed["credence_debater_b"],
    )


async def one_completion(client, model, messages, temperature, max_tokens, seed, parse):
    raw = ""
    for attempt in range(1, base.FORMAT_EXTRA_ATTEMPTS + 2):
        raw = await base.complete(client, model, messages, temperature, max_tokens, seed)
        parsed = parse(raw)
        if parsed is not None:
            return raw, parsed, attempt
    return raw, None, base.FORMAT_EXTRA_ATTEMPTS + 1


async def run_judge(client, model, persona_prompt, sections, draw, arm, guardian_prompts, max_tokens):
    seed = base.SEED_BASE + draw["judge_index"]
    messages = [{"role": "system", "content": persona_prompt}]
    turns = []
    status = "ok"
    failed_section = None
    error = None
    for section_number, section_text in enumerate(sections, start=1):
        messages.append({"role": "user", "content": section_text})
        try:
            initial_raw, initial_parsed, initial_attempts = await one_completion(
                client,
                model,
                messages,
                PERSONA_TEMPERATURE,
                max_tokens,
                seed,
                base.parse_reply,
            )
        except Exception as exc:
            status = "failed"
            failed_section = section_number
            error = str(exc)
            break
        if initial_parsed is None:
            status = "failed"
            failed_section = section_number
            error = "initial reply did not match the required format"
            turns.append(
                {
                    "section": section_number,
                    "initial_raw": initial_raw,
                    "initial_parsed": None,
                    "initial_attempts": initial_attempts,
                }
            )
            break
        messages.append({"role": "assistant", "content": initial_raw})
        guardian = None
        if arm == "guardian":
            system_text, user_template = guardian_prompts
            transcript = "\n\n".join(sections[:section_number])
            guardian_user = (
                user_template.replace("{TRANSCRIPT}", transcript)
                .replace("{PERSONA}", persona_prompt)
                .replace("{REASONING}", initial_parsed["internal_monologue"])
                .replace("{CREDENCE}", credence_block(initial_parsed))
            )
            guardian_messages = [
                {"role": "system", "content": system_text},
                {"role": "user", "content": guardian_user},
            ]
            try:
                guardian_raw, guardian_parsed, guardian_attempts = await one_completion(
                    client,
                    model,
                    guardian_messages,
                    GUARDIAN_TEMPERATURE,
                    max_tokens,
                    7000 + draw["judge_index"],
                    parse_guardian,
                )
            except Exception as exc:
                status = "failed"
                failed_section = section_number
                error = str(exc)
                break
            guardian = {
                "raw": guardian_raw,
                "parsed": guardian_parsed,
                "attempts": guardian_attempts,
            }
            if guardian_parsed is None:
                status = "failed"
                failed_section = section_number
                error = "guardian reply was not the required JSON"
                turns.append(
                    {
                        "section": section_number,
                        "initial_raw": initial_raw,
                        "initial_parsed": initial_parsed,
                        "initial_attempts": initial_attempts,
                        "guardian": guardian,
                    }
                )
                break
            revision_request = REVISION_INSTRUCTION.replace(
                "{risk_summary}", guardian_parsed["risk_summary"]
            )
        else:
            revision_request = REFLECTION_INSTRUCTION
        messages.append({"role": "user", "content": revision_request})
        try:
            revised_raw, revised_parsed, revised_attempts = await one_completion(
                client,
                model,
                messages,
                PERSONA_TEMPERATURE,
                max_tokens,
                seed + 100,
                parse_revision,
            )
        except Exception as exc:
            status = "failed"
            failed_section = section_number
            error = str(exc)
            break
        turn = {
            "section": section_number,
            "initial_raw": initial_raw,
            "initial_parsed": initial_parsed,
            "initial_attempts": initial_attempts,
            "revision_raw": revised_raw,
            "revision_parsed": revised_parsed,
            "revision_attempts": revised_attempts,
        }
        if guardian is not None:
            turn["guardian"] = guardian
        turns.append(turn)
        if revised_parsed is None:
            status = "failed"
            failed_section = section_number
            error = "revision did not match the required format"
            messages.pop()
            break
        messages.append({"role": "assistant", "content": revised_raw})
    return {
        "judge_index": draw["judge_index"],
        "seed": seed,
        "assigned_prior": draw["assigned_prior"],
        "arm": arm,
        "status": status,
        "failed_section": failed_section,
        "error": error,
        "turns": turns,
    }


async def guarded(semaphore, write_lock, out_file, *args):
    async with semaphore:
        record = await run_judge(*args)
    async with write_lock:
        out_file.write(json.dumps(record, ensure_ascii=False) + "\n")
        out_file.flush()
    print(
        "%s judge %s status=%s"
        % (record["arm"], record["judge_index"], record["status"]),
        flush=True,
    )
    return record


def debate_root(debate):
    return ROOT / "results" / "persona_baseline" / debate


def blind_user(transcript, reasoning, credence):
    return (
        "[TRANSCRIPT]\n%s\n\n[JUDGE REASONING]\n%s\n\n[CREDENCE]\n%s"
        % (transcript, reasoning, credence)
    )


async def run_arm(args, arm):
    template = base.load_system_prompt(args.prompt)
    sections = base.load_sections(base.DEBATE_FILES[args.debate])
    out_dir = debate_root(args.debate) / arm
    out_dir.mkdir(parents=True, exist_ok=True)
    draws = base.load_draws(debate_root(args.debate) / "human_priors.json", args.n)
    guardian_prompts = load_guardian_prompts(args.guardian) if arm == "guardian" else None
    client = AsyncOpenAI(base_url=args.base_url, api_key="None")
    model = await base.resolve_model(client, args.model)
    print("arm %s debate %s model %s n %s" % (arm, args.debate, model, args.n), flush=True)
    jsonl_path = out_dir / "judges.jsonl"
    semaphore = asyncio.Semaphore(args.concurrency)
    write_lock = asyncio.Lock()
    with jsonl_path.open("w", encoding="utf-8") as out_file:
        tasks = []
        for draw in draws:
            tasks.append(
                guarded(
                    semaphore,
                    write_lock,
                    out_file,
                    client,
                    model,
                    base.fill_prompt(template, draw["assigned_prior"]),
                    sections,
                    draw,
                    arm,
                    guardian_prompts,
                    args.max_tokens,
                )
            )
        records = await asyncio.gather(*tasks)
    ok = sum(1 for record in records if record["status"] == "ok")
    print("arm %s ok %s/%s" % (arm, ok, args.n), flush=True)
    return ok == args.n


async def run_blind(args):
    """Blind guardian on v2. The guardian does not see the persona.

    Section 1 starts from the saved initial, which was written before any note.
    Each later section writes a new initial from the blind notes and revisions
    already in the chat, then revises after the new blind note.
    """
    if args.debate != "v2":
        raise SystemExit("the blind arm replays the saved v2 guardian judges")
    template = base.load_system_prompt(args.prompt)
    sections = base.load_sections(base.DEBATE_FILES["v2"])
    root = debate_root("v2")
    saved_records = [
        json.loads(line)
        for line in (root / "guardian" / "judges.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    saved_by_index = {record["judge_index"]: record for record in saved_records}
    draws = base.load_draws(root / "human_priors.json", args.n)
    system_text, _user_template = load_guardian_prompts(args.guardian)
    out_dir = root / "guardian_blind"
    out_dir.mkdir(parents=True, exist_ok=True)
    client = AsyncOpenAI(base_url=args.base_url, api_key="None")
    model = await base.resolve_model(client, args.model)
    print("arm blind debate v2 model %s n %s" % (model, args.n), flush=True)

    async def one_judge(draw):
        saved = saved_by_index[draw["judge_index"]]
        persona_prompt = base.fill_prompt(template, draw["assigned_prior"])
        prefix = [{"role": "system", "content": persona_prompt}]
        turns = []
        status = "ok"
        failed_section = None
        error = None
        for section_number, section_text in enumerate(sections, start=1):
            initial_attempts = None
            if section_number == 1:
                saved_turn = next(
                    turn for turn in saved["turns"] if turn.get("section") == 1
                )
                initial_raw = saved_turn.get("initial_raw")
                initial = saved_turn.get("initial_parsed")
                if not initial_raw or not initial:
                    status = "failed"
                    failed_section = section_number
                    error = "saved section 1 initial is missing"
                    break
            else:
                try:
                    initial_raw, initial, initial_attempts = await one_completion(
                        client,
                        model,
                        list(prefix) + [{"role": "user", "content": section_text}],
                        PERSONA_TEMPERATURE,
                        args.max_tokens,
                        1100 + draw["judge_index"],
                        base.parse_reply,
                    )
                except Exception as exc:
                    status = "failed"
                    failed_section = section_number
                    error = str(exc)
                    break
                if initial is None:
                    status = "failed"
                    failed_section = section_number
                    error = "initial reply did not match the required format"
                    turns.append(
                        {
                            "section": section_number,
                            "initial_raw": initial_raw,
                            "initial_parsed": None,
                            "initial_attempts": initial_attempts,
                        }
                    )
                    break
            transcript = "\n\n".join(sections[:section_number])
            guardian_messages = [
                {"role": "system", "content": system_text},
                {
                    "role": "user",
                    "content": blind_user(
                        transcript, initial["internal_monologue"], credence_block(initial)
                    ),
                },
            ]
            try:
                guardian_raw, guardian_parsed, guardian_attempts = await one_completion(
                    client,
                    model,
                    guardian_messages,
                    GUARDIAN_TEMPERATURE,
                    args.max_tokens,
                    8000 + draw["judge_index"],
                    parse_guardian,
                )
            except Exception as exc:
                status = "failed"
                failed_section = section_number
                error = str(exc)
                break
            guardian = {
                "raw": guardian_raw,
                "parsed": guardian_parsed,
                "attempts": guardian_attempts,
            }
            if guardian_parsed is None:
                status = "failed"
                failed_section = section_number
                error = "guardian reply was not the required JSON"
                turns.append(
                    {
                        "section": section_number,
                        "initial_raw": initial_raw,
                        "initial_parsed": initial,
                        "initial_attempts": initial_attempts,
                        "guardian": guardian,
                    }
                )
                break
            revision_request = REVISION_INSTRUCTION.replace(
                "{risk_summary}", guardian_parsed["risk_summary"]
            )
            messages = list(prefix)
            messages.append({"role": "user", "content": section_text})
            messages.append({"role": "assistant", "content": initial_raw})
            messages.append({"role": "user", "content": revision_request})
            try:
                revised_raw, revised_parsed, revised_attempts = await one_completion(
                    client,
                    model,
                    messages,
                    PERSONA_TEMPERATURE,
                    args.max_tokens,
                    1200 + draw["judge_index"],
                    parse_revision,
                )
            except Exception as exc:
                status = "failed"
                failed_section = section_number
                error = str(exc)
                break
            turns.append(
                {
                    "section": section_number,
                    "initial_raw": initial_raw,
                    "initial_parsed": initial,
                    "initial_attempts": initial_attempts,
                    "revision_raw": revised_raw,
                    "revision_parsed": revised_parsed,
                    "revision_attempts": revised_attempts,
                    "guardian": guardian,
                }
            )
            if revised_parsed is None:
                status = "failed"
                failed_section = section_number
                error = "revision did not match the required format"
                break
            prefix.extend(
                [
                    {"role": "user", "content": section_text},
                    {"role": "assistant", "content": initial_raw},
                    {"role": "user", "content": revision_request},
                    {"role": "assistant", "content": revised_raw},
                ]
            )
        return {
            "judge_index": draw["judge_index"],
            "seed": base.SEED_BASE + draw["judge_index"],
            "assigned_prior": draw["assigned_prior"],
            "arm": "blind",
            "status": status,
            "failed_section": failed_section,
            "error": error,
            "turns": turns,
        }

    semaphore = asyncio.Semaphore(args.concurrency)
    write_lock = asyncio.Lock()
    jsonl_path = out_dir / "judges.jsonl"

    async def guarded_blind(draw):
        async with semaphore:
            record = await one_judge(draw)
        async with write_lock:
            out_file.write(json.dumps(record, ensure_ascii=False) + "\n")
            out_file.flush()
        print("blind judge %s status=%s" % (record["judge_index"], record["status"]), flush=True)
        return record

    with jsonl_path.open("w", encoding="utf-8") as out_file:
        records = await asyncio.gather(*(guarded_blind(draw) for draw in draws))
    ok = sum(1 for record in records if record["status"] == "ok")
    print("arm blind ok %s/%s" % (ok, args.n), flush=True)
    return ok == args.n


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=("guardian", "reflection", "both", "blind"), default="both")
    parser.add_argument("--debate", choices=("v1", "v2"), default="v2")
    parser.add_argument("--n", type=int, default=50)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--model", default="")
    parser.add_argument("--prompt", type=Path, default=ROOT / "prompts" / "prompt_user.md")
    parser.add_argument("--guardian", type=Path, default=GUARDIAN_PATH)
    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv)

    async def run_all():
        if args.arm == "blind":
            return await run_blind(args)
        arms = ("guardian", "reflection") if args.arm == "both" else (args.arm,)
        results = []
        for arm in arms:
            results.append(await run_arm(args, arm))
        return all(results)

    return 0 if asyncio.run(run_all()) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
