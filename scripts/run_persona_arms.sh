#!/bin/bash -l
#SBATCH -A p201613
#SBATCH -p gpu
#SBATCH -q short
#SBATCH -N 1
#SBATCH --gres=gpu:4
#SBATCH -t 02:00:00
#SBATCH --hint=nomultithread
#SBATCH -J persona-arms
#SBATCH -o logs/persona_arms_%j.out
#SBATCH -e logs/persona_arms_%j.err

# Llama 3.1 70B, then the guardian arm and the reflection arm on probability v2.
# The server binds to 127.0.0.1. Vanilla judges are already saved and are not rerun.
#
#   sbatch scripts/run_persona_arms.sh

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
    > "logs/persona_arms_sglang_${SLURM_JOB_ID}.log" 2>&1 &
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

echo "START arms n=${N} concurrency=${CONCURRENCY} $(date -Is)"
"$PY" -u src/run_persona_arms.py --arm both --n "$N" --concurrency "$CONCURRENCY"
echo "START arm comparison $(date -Is)"
"$PY" -u src/compare_arms.py
echo "END arms $(date -Is)"
