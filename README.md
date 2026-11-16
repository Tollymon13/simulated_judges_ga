# Simulated judges

Persona-based Llama 3.1 judges for two DC-Debates probability transcripts, and an inference-time guardian that writes a risk summary after each section.

The debaters are the hand-written transcripts. Debater A is the correct side in the files the persona reads. The persona is not told which side is honest.

## What is here

- `unroll_debate.py` turns a debate JSON into the four sections a human judge saw. Markdown is the judge view. JSON keeps the role map.
- `prompt_user.md` is the lay judge. `{assigned_prior}` is one human's section-1 credence in the correct side. Every judge is told they may move 10 to 30 points for a simple argument.
- `sample_human_priors.py` draws 50 priors with replacement for each transcript (seeds 21 and 22).
- `run_persona_baseline.py` runs those judges. `compare_persona_to_humans.py` checks whether the section-4 mean is within 5 points of the paired humans.
- `guardian_angel.yaml` and `run_persona_arms.py` run three arms on that same prompt: a risk summary, a fixed reflection sentence, and no revision. The judge always sees the summary. The allow/intervene label is stored and not shown. The blind arm replays saved v2 drafts without the persona prompt.
- `prompt_user_varied.md` replaces the fixed update sentence with `{update_tendency}`. `sample_update_tendencies.py` draws that sentence from the other humans' updates, not from that row's own ending. That run is vanilla only.
- `score_note_uptake.py` asks Llama 3.1 8B whether a revised monologue addresses its note. It does not see the credence change.

## Runs

The SLURM scripts start SGLang on the GPU node and then the client. They are written for this cluster: account `p201613`, `/project/home/p201613/sglang-env`, and `/project/home/p201613/ai-debate/debate-env`.

```bash
sbatch scripts/run_persona_baseline.sh
sbatch scripts/run_persona_arms.sh          # v2 guardian and reflection
sbatch scripts/run_persona_followup.sh      # varied judges, v1 arms, blind v2
sbatch scripts/run_note_uptake.sh           # 8B, one GPU
```

`results/` and `logs/` are gitignored. `DC_Debates.pdf` stays on disk and is not tracked.
