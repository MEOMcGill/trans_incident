#!/bin/bash
#SBATCH --job-name=hostility-coding
#SBATCH --account=def-aengusb
#SBATCH --time=2:00:00
#SBATCH --mem=80G
#SBATCH --cpus-per-task=8
#SBATCH --gpus=h100:1
#SBATCH --output=%x-%j.out
#SBATCH --error=%x-%j.err
#SBATCH --mail-type=END,FAIL
#SBATCH --mail-user=saewon.park@mcgill.ca

MODEL="$HOME/scratch/hf_cache/models--Qwen--Qwen3.5-27B-FP8/snapshots/2e1b21350ce589fcaafbb3c7d7eac526a7aed582"
PORT=8197
SCRATCH="$HOME/scratch/trans_incident"

module load python/3.11.5 cuda/12.6
source ~/venv_qwen35/bin/activate

export HF_HOME=$HOME/scratch/hf_cache
export HF_HUB_OFFLINE=1
export VLLM_USE_DEEP_GEMM=0
export FLASHINFER_JIT_DISABLE=1

# Start vLLM server
vllm serve "$MODEL" \
    --port $PORT \
    --tensor-parallel-size 1 \
    --max-model-len 4096 \
    --gpu-memory-utilization 0.88 \
    --trust-remote-code &

VLLM_PID=$!

# Wait for server
echo "Waiting for vLLM server..."
for i in $(seq 1 120); do
    curl -s http://localhost:$PORT/health > /dev/null 2>&1 && break
    kill -0 $VLLM_PID 2>/dev/null || { echo "vLLM died"; exit 1; }
    sleep 5
done

if ! curl -s http://localhost:$PORT/health > /dev/null 2>&1; then
    echo "Server failed to start within 10 min"
    kill $VLLM_PID 2>/dev/null
    exit 1
fi
echo "Server ready"

# Run classification
python -u $SCRATCH/scripts/keyword_filtered_feb26_hostility_coding.py \
    --port $PORT \
    --model "$MODEL"

kill $VLLM_PID 2>/dev/null; wait $VLLM_PID 2>/dev/null || true
