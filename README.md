# Simulated judges

Persona-based Llama 3.1 judges for two DC-Debates probability transcripts, and an inference-time guardian that writes a risk summary after each section.

The debaters are the hand-written transcripts. Debater A is the correct side in the files the persona reads. The persona is not told which side is honest.

## Layout

- `data/debates/` holds the two probability JSON trees. `data/unrolled/` is the four sections a judge reads. `data/quant-1-official-study-noids.xlsx` is the human study.
- `prompts/prompt_user.md` is the lay judge. `{assigned_prior}` is one human's section-1 credence in the correct side. Every judge is told they may move 10 to 30 points for a simple argument.
- `prompts/guardian_angel.yaml` is the risk-summary prompt.
- `src/unroll_debate.py` writes the section files. `src/sample_human_priors.py` draws 50 priors with replacement for each transcript (seeds 21 and 22).
- `src/run_persona_baseline.py` runs the judges. `src/compare_persona_to_humans.py` checks whether the section-4 mean is within 5 points of the paired humans.
- `src/run_persona_arms.py` runs a risk summary, a fixed reflection sentence, and no revision on the fixed-sentence prompt. The judge always sees the summary. The allow/intervene label is stored and not shown. The blind arm replays saved v2 drafts without the persona prompt.
- `src/score_note_uptake.py` asks Llama 3.1 8B whether a revised monologue addresses its note. It does not see the credence change.
- `scripts/` are the SLURM jobs. `results/` and `logs/` are gitignored.

## Runs

The SLURM scripts start SGLang on the GPU node and then the client. They are written for this cluster: account `p201613`, `/project/home/p201613/sglang-env`, and `/project/home/p201613/ai-debate/debate-env`.

```bash
sbatch scripts/run_persona_baseline.sh
sbatch scripts/run_persona_arms.sh          # v2 guardian and reflection
sbatch scripts/run_persona_followup.sh      # v1 arms, then blind v2
sbatch scripts/run_note_uptake.sh           # 8B, one GPU
```

`DC_Debates.pdf` stays on disk and is not tracked.

## Results

Fifty draws per transcript, paired with the humans those draws came from. Credence is in Debater A. A final credence above 50 counts as correct.

The fixed-sentence persona matches the v2 mean and misses v1. v2 is 26.0 against a human mean of 28.0, with a spread of 13.1 against 27.5 and 0 of 50 above 50 against 9 humans. v1 is 29.4 against 38.3, spread 16.3 against 29.6, and 6 of 50 above 50 against 15 humans.

On that same prompt, the risk summary moves credence toward the correct side and reflection moves it away. Mean change per section is +1.77 for the v2 guardian and −1.52 for v2 reflection; on v1, +2.86 and −1.82. Final v2 means are 26.0 with no revision (0 of 50 above 50), 21.0 after reflection (3 of 50), 44.3 after the guardian (14 of 50), and 44.7 for a blind guardian that did not see the persona prompt (13 of 50). Final v1 means are 29.4 (6 of 50), 25.1 after reflection (1 of 50), and 38.9 after the guardian (8 of 50). A written credence of 0 or 100 is clamped to 1 or 99 and kept.

An 8B marked 99–100% of revisions as addressing the note, including reflection, whose credence change is negative.

A separate prompt that sampled an update sentence for each judge is not part of these results. Matching a mean with that sentence does not show that the persona simulates human beliefs.
