#!/usr/bin/env python3
"""Attach an update sentence to the existing 50 draws.

The sentence is drawn from the other rows of the same transcript. A judge
does not receive the update from their own human row. v1 and v2 are drawn
separately. The original human_priors.json files are not modified.
"""

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SEEDS = {"v1": 32, "v2": 31}
SENTENCES = {
    "barely": (
        "You stay within about 5 points of your starting credence unless a "
        "point is made in very plain language."
    ),
    "drop": (
        "You will lower your credence in Debater A by 10 to 30 points if a "
        "simple explanation feels right."
    ),
    "rise": (
        "You will raise your credence in Debater A by 10 to 30 points if a "
        "simple explanation feels right."
    ),
}


def band(delta):
    if delta <= -10:
        return "drop"
    if delta >= 10:
        return "rise"
    return "barely"


def assign(draws, seed):
    bands = [band(draw["human_section_4"] - draw["assigned_prior"]) for draw in draws]
    rng = np.random.RandomState(seed)
    assigned = []
    for index, draw in enumerate(draws):
        pool = [item for other, item in enumerate(bands) if other != index]
        chosen = pool[int(rng.randint(0, len(pool)))]
        updated = dict(draw)
        updated["update_band"] = chosen
        updated["update_tendency"] = SENTENCES[chosen]
        assigned.append(updated)
    return assigned


def main():
    for debate, seed in SEEDS.items():
        source = ROOT / "results" / "persona_baseline" / debate / "human_priors.json"
        payload = json.loads(source.read_text(encoding="utf-8"))
        payload["draws"] = assign(payload["draws"], seed)
        payload["update_seed"] = seed
        out_dir = ROOT / "results" / "persona_varied" / debate
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "human_priors.json"
        out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        counts = {name: 0 for name in SENTENCES}
        for draw in payload["draws"]:
            counts[draw["update_band"]] += 1
        print("%s seed=%s %s wrote %s" % (debate, seed, counts, out_path))


if __name__ == "__main__":
    main()
