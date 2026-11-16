#!/usr/bin/env python3
"""Run the overwhelmed-anchor persona over one unrolled probability debate.

Each judge is an independent chat. The system prompt is prompt_user.md.
Sections are appended one at a time, and the model's own replies stay in
the thread. Fifty judges is the default. The SGLang server must already be
listening on localhost; scripts/run_persona_baseline.sh starts it.
"""

import argparse
import asyncio
import json
import re
import statistics
import sys
from pathlib import Path

from openai import AsyncOpenAI

ROOT = Path(__file__).resolve().parent.parent
DEBATE_FILES = {
    "v1": ROOT / "data" / "unrolled" / "Probability_-_expected_number_of_rolls.sections.md",
    "v2": ROOT / "data" / "unrolled" / "Probability_-_expected_number_of_rolls_v2.sections.md",
}
SECTION_HEADING = re.compile(r"^## Section (\d+)\s*$", re.MULTILINE)
FIELD_RE = {
    "monologue": re.compile(
        r"(?:\*\*)?INTERNAL_MONOLOGUE:(?:\*\*)?\s*(.*?)\s*(?=(?:\*\*)?CREDENCE_DEBATER_A:)",
        re.DOTALL,
    ),
    "credence_a": re.compile(r"(?:\*\*)?CREDENCE_DEBATER_A:(?:\*\*)?\s*\[?\s*(\d+)\s*\]?"),
    "credence_b": re.compile(r"(?:\*\*)?CREDENCE_DEBATER_B:(?:\*\*)?\s*\[?\s*(\d+)\s*\]?"),
}
SEED_BASE = 1000
API_ATTEMPTS = 5
FORMAT_EXTRA_ATTEMPTS = 2


def load_system_prompt(path):
    text = path.read_text(encoding="utf-8").strip()
    if "{assigned_prior}" not in text:
        raise ValueError("prompt %s has no {assigned_prior} placeholder" % path)
    return text


def fill_prompt(template, assigned_prior, update_tendency=None):
    filled = template.replace("{assigned_prior}", str(int(assigned_prior)))
    if "{update_tendency}" in template:
        if not update_tendency:
            raise ValueError("prompt requires an update tendency")
        filled = filled.replace("{update_tendency}", update_tendency)
    if "{assigned_prior}" in filled or "{update_tendency}" in filled:
        raise ValueError("failed to fill prompt placeholders")
    return filled


def load_draws(path, n):
    payload = json.loads(path.read_text(encoding="utf-8"))
    draws = payload["draws"]
    if len(draws) < n:
        raise ValueError("%s has %s draws, need %s" % (path, len(draws), n))
    return draws[:n]


def load_sections(path):
    """Return the four section bodies, each starting with its heading."""
    text = path.read_text(encoding="utf-8")
    matches = list(SECTION_HEADING.finditer(text))
    if [int(match.group(1)) for match in matches] != [1, 2, 3, 4]:
        raise ValueError("expected sections 1-4 in %s" % path)
    sections = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append(text[match.start() : end].strip())
    return sections


def parse_reply(text):
    """Return the three fields, or None when the reply is not a valid turn."""
    if not text:
        return None
    monologue = FIELD_RE["monologue"].search(text)
    credence_a = FIELD_RE["credence_a"].search(text)
    credence_b = FIELD_RE["credence_b"].search(text)
    if not (monologue and credence_a and credence_b):
        return None
    credence_a = int(credence_a.group(1))
    credence_b = int(credence_b.group(1))
    if not (1 <= credence_a <= 99 and 1 <= credence_b <= 99):
        return None
    if credence_a + credence_b != 100:
        return None
    return {
        "internal_monologue": monologue.group(1).strip(),
        "credence_debater_a": credence_a,
        "credence_debater_b": credence_b,
    }


async def complete(client, model, messages, temperature, max_tokens, seed):
    delay = 2
    last_error = None
    for attempt in range(1, API_ATTEMPTS + 1):
        try:
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                seed=seed,
            )
            return (response.choices[0].message.content or "").strip()
        except Exception as exc:
            last_error = exc
            if attempt == API_ATTEMPTS:
                break
            await asyncio.sleep(delay)
            delay *= 2
    raise RuntimeError("API call failed after %s attempts: %s" % (API_ATTEMPTS, last_error))


async def run_judge(client, model, system_prompt, sections, judge_index, args):
    seed = SEED_BASE + judge_index
    messages = [{"role": "system", "content": system_prompt}]
    turns = []
    status = "ok"
    failed_section = None
    error = None
    for section_number, section_text in enumerate(sections, start=1):
        messages.append({"role": "user", "content": section_text})
        parsed = None
        raw = ""
        attempts = 0
        try:
            for attempts in range(1, FORMAT_EXTRA_ATTEMPTS + 2):
                raw = await complete(
                    client,
                    model,
                    messages,
                    args.temperature,
                    args.max_tokens,
                    seed,
                )
                parsed = parse_reply(raw)
                if parsed is not None:
                    break
        except Exception as exc:
            status = "failed"
            failed_section = section_number
            error = str(exc)
            turns.append(
                {
                    "section": section_number,
                    "raw": raw,
                    "parsed": None,
                    "attempts": attempts,
                }
            )
            messages.pop()
            break
        turns.append(
            {
                "section": section_number,
                "raw": raw,
                "parsed": parsed,
                "attempts": attempts,
            }
        )
        if parsed is None:
            status = "failed"
            failed_section = section_number
            error = "reply did not match the required format"
            messages.pop()
            break
        messages.append({"role": "assistant", "content": raw})
    return {
        "judge_index": judge_index,
        "seed": seed,
        "assigned_prior": args.assigned_prior,
        "status": status,
        "failed_section": failed_section,
        "error": error,
        "turns": turns,
    }


async def guarded_judge(semaphore, write_lock, out_file, client, model, system_prompt, sections, judge_index, args):
    async with semaphore:
        record = await run_judge(client, model, system_prompt, sections, judge_index, args)
    line = json.dumps(record, ensure_ascii=False)
    async with write_lock:
        out_file.write(line + "\n")
        out_file.flush()
    print(
        "judge %s status=%s seed=%s"
        % (judge_index, record["status"], record["seed"]),
        flush=True,
    )
    return record


def summarize(records):
    sections = []
    for section_number in (1, 2, 3, 4):
        values = []
        for record in records:
            for turn in record["turns"]:
                if turn["section"] == section_number and turn["parsed"] is not None:
                    values.append(turn["parsed"]["credence_debater_a"])
        if len(values) >= 2:
            stdev = statistics.stdev(values)
        else:
            stdev = None
        sections.append(
            {
                "section": section_number,
                "n_success": len(values),
                "mean_credence_a": (sum(values) / len(values)) if values else None,
                "stdev_credence_a": stdev,
            }
        )
    return sections


async def resolve_model(client, requested):
    if requested:
        return requested
    models = await client.models.list()
    if not models.data:
        raise RuntimeError("server returned no models at %s" % client.base_url)
    return models.data[0].id


async def run(args):
    template = load_system_prompt(args.prompt)
    sections = load_sections(DEBATE_FILES[args.debate])
    out_dir = args.out_dir or (ROOT / "results" / "persona_baseline" / args.debate)
    out_dir.mkdir(parents=True, exist_ok=True)
    priors_path = args.priors or (out_dir / "human_priors.json")
    draws = load_draws(priors_path, args.n)
    jsonl_path = out_dir / "judges.jsonl"
    summary_path = out_dir / "summary.json"

    client = AsyncOpenAI(base_url=args.base_url, api_key="None")
    model = await resolve_model(client, args.model)
    print(
        "model %s temperature %s n %s concurrency %s"
        % (model, args.temperature, args.n, args.concurrency),
        flush=True,
    )

    semaphore = asyncio.Semaphore(args.concurrency)
    write_lock = asyncio.Lock()
    with jsonl_path.open("w", encoding="utf-8") as out_file:
        tasks = []
        for judge_index in range(args.n):
            judge_args = argparse.Namespace(**vars(args))
            judge_args.assigned_prior = draws[judge_index]["assigned_prior"]
            tasks.append(
                guarded_judge(
                    semaphore,
                    write_lock,
                    out_file,
                    client,
                    model,
                    fill_prompt(
                        template,
                        judge_args.assigned_prior,
                        draws[judge_index].get("update_tendency"),
                    ),
                    sections,
                    judge_index,
                    judge_args,
                )
            )
        records = await asyncio.gather(*tasks)

    records.sort(key=lambda record: record["judge_index"])
    summary = {
        "debate": args.debate,
        "source": str(DEBATE_FILES[args.debate]),
        "model": model,
        "temperature": args.temperature,
        "n_requested": args.n,
        "concurrency": args.concurrency,
        "n_ok": sum(1 for record in records if record["status"] == "ok"),
        "sections": summarize(records),
    }
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print("wrote %s" % jsonl_path, flush=True)
    print("wrote %s" % summary_path, flush=True)
    return 0 if summary["n_ok"] == args.n else 1


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--debate", choices=sorted(DEBATE_FILES), default="v1")
    parser.add_argument("--n", type=int, default=50)
    parser.add_argument("--temperature", type=float, default=0.6)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--model", default="", help="Defaults to the id reported by the server.")
    parser.add_argument("--prompt", type=Path, default=ROOT / "prompts" / "prompt_user.md")
    parser.add_argument("--priors", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    if args.n < 1:
        raise SystemExit("--n must be at least 1")
    if args.concurrency < 1:
        raise SystemExit("--concurrency must be at least 1")
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
