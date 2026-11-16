#!/bin/bash -l
#SBATCH -A p201613
#SBATCH -p gpu
#SBATCH -q short
#SBATCH -N 1
#SBATCH --gres=gpu:1
#SBATCH -t 00:40:00
#SBATCH --hint=nomultithread
#SBATCH -J note-uptake
#SBATCH -o logs/note_uptake_%j.out
#SBATCH -e logs/note_uptake_%j.err

# Llama 3.1 8B scores whether each revision addresses its note.
# The server binds to 127.0.0.1, so the client runs on this node.
#
#   sbatch scripts/run_note_uptake.sh

set -euo pipefail
cd /project/home/p201613/dc-debates
mkdir -p logs

module load NVHPC Python
source /project/home/p201613/sglang-env/bin/activate

python -m sglang.launch_server \
    --model-path meta-llama/Llama-3.1-8B-Instruct \
    --tp 1 \
    --mem-fraction-static 0.85 \
    --disable-cuda-graph \
    --port 8000 \
    > "logs/note_uptake_sglang_${SLURM_JOB_ID}.log" 2>&1 &
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

PY=/project/home/p201613/ai-debate/debate-env/bin/python
echo "START note uptake $(date -Is)"
"$PY" -u src/score_note_uptake.py --concurrency 8
echo "END note uptake $(date -Is)"
