#!/bin/bash -l
#SBATCH -A p201613
#SBATCH -p gpu
#SBATCH -q short
#SBATCH -N 1
#SBATCH --gres=gpu:4
#SBATCH -t 02:00:00
#SBATCH --hint=nomultithread
#SBATCH -J persona-followup
#SBATCH -o logs/persona_followup_%j.out
#SBATCH -e logs/persona_followup_%j.err

# Varied-persona vanilla judges, then v1 guardian and reflection, then the
# blind v2 guardian. Saved judge files are read and are not rewritten.
#
#   sbatch scripts/run_persona_followup.sh

set -uo pipefail
cd /project/home/p201613/dc-debates
mkdir -p logs

module load NVHPC Python
source /project/home/p201613/sglang-env/bin/activate

python -m sglang.launch_server \
    --model-path meta-llama/Llama-3.1-70B-Instruct \
    --tp 4 \
    --mem-fraction-static 0.88 \
    --disable-cuda-graph \
    --port 8000 \
    > "logs/persona_followup_sglang_${SLURM_JOB_ID}.log" 2>&1 &
SERVER_PID=$!

cleanup() {
    if kill -0 "$SERVER_PID" 2>/dev/null; then
        kill "$SERVER_PID" 2>/dev/null || true
        wait "$SERVER_PID" 2>/dev/null || true
    fi
}
trap cleanup EXIT

ready=0
for _ in $(seq 1 80); do
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        echo "sglang exited before it was ready"
        exit 1
    fi
    if curl -sf --max-time 5 http://127.0.0.1:8000/v1/models >/dev/null; then
        ready=1
        break
    fi
    sleep 15
done
if [[ "$ready" -ne 1 ]]; then
    echo "sglang did not become ready within 20 minutes"
    exit 1
fi
echo "sglang ready $(date -Is)"

N="${N:-50}"
CONCURRENCY="${CONCURRENCY:-4}"
PY=/project/home/p201613/ai-debate/debate-env/bin/python
fail=0

echo "START update tendencies $(date -Is)"
"$PY" -u sample_update_tendencies.py || fail=1

for debate in v1 v2; do
    echo "START varied vanilla debate=${debate} $(date -Is)"
    "$PY" -u run_persona_baseline.py \
        --debate "$debate" \
        --n "$N" \
        --concurrency "$CONCURRENCY" \
        --prompt prompt_user_varied.md \
        --priors "results/persona_varied/${debate}/human_priors.json" \
        --out-dir "results/persona_varied/${debate}" || fail=1
done

echo "START v1 arms $(date -Is)"
"$PY" -u run_persona_arms.py --debate v1 --arm both --n "$N" --concurrency "$CONCURRENCY" || fail=1
echo "START v1 comparison $(date -Is)"
"$PY" -u compare_arms.py --debate v1 || fail=1

echo "START blind v2 guardian $(date -Is)"
"$PY" -u run_persona_arms.py --debate v2 --arm blind --n "$N" --concurrency "$CONCURRENCY" || fail=1
echo "START blind comparison $(date -Is)"
"$PY" -u compare_arms.py --debate v2 --blind || fail=1

echo "START varied comparison $(date -Is)"
"$PY" -u compare_varied.py || fail=1

echo "END followup fail=${fail} $(date -Is)"
exit "$fail"
