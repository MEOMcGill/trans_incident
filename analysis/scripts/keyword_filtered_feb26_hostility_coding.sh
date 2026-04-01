#!/bin/bash
#SBATCH --job-name=hostility-coding
#SBATCH --account=def-aengusb
#SBATCH --time=2:30:00
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
VLLM_LOG="$SCRATCH/vllm_server.log"

module load python/3.11.5 cuda/12.6
source ~/venv_qwen35/bin/activate

export HF_HOME=$HOME/scratch/hf_cache
export HF_HUB_OFFLINE=1
export VLLM_USE_DEEP_GEMM=0
export FLASHINFER_JIT_DISABLE=1

# Diagnostics
echo "Node: $(hostname)"
echo "GPU:"
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader 2>/dev/null || echo "nvidia-smi failed"
echo "Python: $(which python)"
python -c "import vllm; print(f'vLLM {vllm.__version__}')" 2>&1
echo "Model path exists: $(ls $MODEL/config.json 2>/dev/null && echo YES || echo NO)"
echo "---"

# Start vLLM server, capture all output
vllm serve "$MODEL" \
    --port $PORT \
    --tensor-parallel-size 1 \
    --max-model-len 8192 \
    --gpu-memory-utilization 0.88 \
    --trust-remote-code \
    --enforce-eager \
    --limit-mm-per-prompt.image 0 \
    --limit-mm-per-prompt.video 0 \
    > "$VLLM_LOG" 2>&1 &

VLLM_PID=$!

# Wait for server
echo "Waiting for vLLM server (PID $VLLM_PID)..."
for i in $(seq 1 240); do
    if curl -s http://localhost:$PORT/health > /dev/null 2>&1; then
        echo "  Server ready after $((i*5))s"
        break
    fi
    if ! kill -0 $VLLM_PID 2>/dev/null; then
        echo "  vLLM died! Last 30 lines of log:"
        tail -30 "$VLLM_LOG"
        exit 1
    fi
    sleep 5
done

if ! curl -s http://localhost:$PORT/health > /dev/null 2>&1; then
    echo "Server failed to start within 20 min. Last 30 lines of log:"
    tail -30 "$VLLM_LOG"
    kill $VLLM_PID 2>/dev/null
    exit 1
fi

# Run classification
python -u $SCRATCH/scripts/keyword_filtered_feb26_hostility_coding.py \
    --port $PORT \
    --model "$MODEL"

kill $VLLM_PID 2>/dev/null; wait $VLLM_PID 2>/dev/null || true
