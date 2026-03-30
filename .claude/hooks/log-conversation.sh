#!/bin/bash
# Log full conversation transcripts when a Claude Code session ends

# Read hook input from stdin
INPUT=$(cat)

# Extract fields using jq
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // "unknown"')
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty')
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')

# Logging directory
LOGS_DIR="$(dirname "$(dirname "$(realpath "$0")")")/logs"
mkdir -p "$LOGS_DIR"

# Generate timestamp and filename
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
LOG_FILE="$LOGS_DIR/conversation_${TIMESTAMP}_${SESSION_ID}.jsonl"

# Copy full transcript if available
if [ -n "$TRANSCRIPT_PATH" ] && [ -f "$TRANSCRIPT_PATH" ]; then
  {
    echo "# Session ID: $SESSION_ID"
    echo "# Timestamp: $TIMESTAMP"
    echo "# Working Directory: $CWD"
    echo ""
    cat "$TRANSCRIPT_PATH"
  } > "$LOG_FILE"
fi

# Append to summary index
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Session $SESSION_ID — Transcript: $LOG_FILE" >> "$LOGS_DIR/sessions.log"

exit 0
