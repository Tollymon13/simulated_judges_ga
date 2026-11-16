#!/usr/bin/env python3
"""Sample section-1 credences for each probability transcript.

Draws are with replacement and independent across transcripts. Each draw
keeps the human row so the persona's final credence can be compared with
that person's final credence.
"""

import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
WORKBOOK = ROOT / "data" / "quant-1-official-study-noids.xlsx"
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
EXPERIMENTS = (
    {
        "debate": "v1",
        "debate_name": "Probability_-_expected_number_of_rolls",
        "seed": 21,
    },
    {
        "debate": "v2",
        "debate_name": "Probability_-_expected_number_of_rolls_v2",
        "seed": 22,
    },
)
N_DRAWS = 50


def column_index(ref):
    column = ""
    for char in ref:
        if char.isalpha():
            column += char
        else:
            break
    index = 0
    for char in column:
        index = index * 26 + ord(char) - 64
    return index - 1


def load_sheet_rows(path):
    with zipfile.ZipFile(path) as workbook:
        shared = []
        root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
        for item in root.findall(NS + "si"):
            shared.append("".join(node.text or "" for node in item.iter(NS + "t")))
        sheet = ET.fromstring(workbook.read("xl/worksheets/sheet1.xml"))
    rows = []
    for row in sheet.findall(NS + "sheetData/" + NS + "row"):
        cells = {}
        for cell in row.findall(NS + "c"):
            index = column_index(cell.attrib["r"])
            value = cell.find(NS + "v")
            if value is None or value.text is None:
                text = ""
            elif cell.attrib.get("t") == "s":
                text = shared[int(value.text)]
            else:
                text = value.text
            cells[index] = text
        if not cells:
            continue
        width = max(cells) + 1
        rows.append([cells.get(index, "") for index in range(width)])
    header = rows[0]
    return header, rows[1:]


def percentage(value):
    return int(round(float(value) * 100))


def rows_for(records, header, debate_name):
    index = {name: position for position, name in enumerate(header)}
    selected = []
    for row_index, row in enumerate(records):
        if row[index["debate_name"]] != debate_name:
            continue
        section_1 = percentage(row[index["section_1_credence_in_correct_answer"]])
        section_4 = percentage(row[index["section_4_credence_in_correct_answer"]])
        selected.append(
            {
                "row_index": row_index,
                "section_1": section_1,
                "section_4": section_4,
            }
        )
    return selected


def mean(values):
    return sum(values) / len(values)


def sample_experiment(humans, experiment):
    np.random.seed(experiment["seed"])
    chosen = np.random.choice(len(humans), size=N_DRAWS, replace=True)
    draws = []
    for judge_index, human_index in enumerate(chosen.tolist()):
        person = humans[human_index]
        draws.append(
            {
                "judge_index": judge_index,
                "row_index": person["row_index"],
                "assigned_prior": person["section_1"],
                "human_section_1": person["section_1"],
                "human_section_4": person["section_4"],
            }
        )
    return {
        "debate": experiment["debate"],
        "debate_name": experiment["debate_name"],
        "seed": experiment["seed"],
        "n_humans": len(humans),
        "n_draws": N_DRAWS,
        "draws": draws,
    }


def summarize(experiment, humans):
    return {
        "debate": experiment["debate"],
        "debate_name": experiment["debate_name"],
        "n_humans": len(humans),
        "mean_section_1": mean([person["section_1"] for person in humans]),
        "mean_section_4": mean([person["section_4"] for person in humans]),
    }


def main():
    header, records = load_sheet_rows(WORKBOOK)
    for experiment in EXPERIMENTS:
        humans = rows_for(records, header, experiment["debate_name"])
        if not humans:
            raise SystemExit("no rows for %s" % experiment["debate_name"])
        out_dir = ROOT / "results" / "persona_baseline" / experiment["debate"]
        out_dir.mkdir(parents=True, exist_ok=True)
        priors = sample_experiment(humans, experiment)
        summary = summarize(experiment, humans)
        (out_dir / "human_priors.json").write_text(
            json.dumps(priors, indent=2) + "\n", encoding="utf-8"
        )
        (out_dir / "human_summary.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )
        sampled = [draw["assigned_prior"] for draw in priors["draws"]]
        print(
            "%s humans=%s sampled_mean_s1=%.2f human_mean_s4=%.2f"
            % (
                experiment["debate"],
                len(humans),
                mean(sampled),
                summary["mean_section_4"],
            )
        )


if __name__ == "__main__":
    main()
