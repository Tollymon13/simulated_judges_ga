#!/bin/bash -l
#SBATCH -A p201613
#SBATCH -p gpu
#SBATCH -q short
#SBATCH -N 1
#SBATCH --gres=gpu:4
#SBATCH -t 02:00:00
#SBATCH --hint=nomultithread
#SBATCH -J persona-baseline
#SBATCH -o logs/persona_baseline_%j.out
#SBATCH -e logs/persona_baseline_%j.err

# Starts Llama 3.1 70B on this node, then runs the overwhelmed-anchor
# judges against one unrolled probability debate. The server binds to
# 127.0.0.1, so the client has to run on this node.
#
#   DEBATE=both N=50 CONCURRENCY=4 sbatch scripts/run_persona_baseline.sh
#   DEBATE=v1 runs one transcript. DEBATE=both runs v1, then v2.

set -euo pipefail
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
    > "logs/persona_baseline_sglang_${SLURM_JOB_ID}.log" 2>&1 &
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

DEBATE="${DEBATE:-both}"
N="${N:-50}"
CONCURRENCY="${CONCURRENCY:-4}"
PY=/project/home/p201613/ai-debate/debate-env/bin/python

echo "START sample priors $(date -Is)"
"$PY" -u sample_human_priors.py

if [[ "$DEBATE" == "both" ]]; then
    DEBATES=(v1 v2)
else
    DEBATES=("$DEBATE")
fi

for debate in "${DEBATES[@]}"; do
    echo "START persona baseline debate=${debate} n=${N} concurrency=${CONCURRENCY} $(date -Is)"
    "$PY" -u run_persona_baseline.py \
        --debate "$debate" \
        --n "$N" \
        --concurrency "$CONCURRENCY"
    echo "START comparison debate=${debate} $(date -Is)"
    "$PY" -u compare_persona_to_humans.py --debate "$debate"
done
echo "END persona baseline $(date -Is)"
