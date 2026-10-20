#!/bin/bash
# docker_claude_agent.sh — Runs inside Docker container as the entrypoint
# for Claude Code agent evaluation. Called by run_claude_code.sh.
#
# Expected env vars: ANTHROPIC_API_KEY, ANTHROPIC_BASE_URL, AGENT_MODEL
# Expected mounts:
#   /task/instruction.md (ro) — task instruction only, NO tests directory
#   /agent_logs (rw)          — output logs and results archive
#
# Design:
#   - Does NOT pass instruction content as CLI arg (avoids shell limit / escaping issues)
#   - Instead, copies instruction.md into the agent's workspace and tells the model to read it
#   - The model uses its own tool capabilities (Read, Bash, etc.) to explore the task
#   - No `set -e` so tar always runs even if claude exits non-zero

set -uo pipefail

# Strip trailing /v1 from base URL — Claude Code appends its own path
CC_BASE_URL="${ANTHROPIC_BASE_URL%/v1}"
CC_BASE_URL="${CC_BASE_URL%/}"

# Optional: text-only-endpoint content proxy (GLM). GLM's gateway rejects any
# non-text content block (image/document) with `messages.content.type must be one of
# ['text']`, which 400-crashes the whole trajectory the moment the agent Reads a
# figure/PDF. When GLM_PROXY=1 we start a local proxy that extracts PDFs to text
# (and placeholders raster images) before forwarding to the real upstream, then
# point Claude Code at the proxy instead of the upstream directly.
if [ "${GLM_PROXY:-}" = "1" ]; then
    echo "[docker_claude_agent] GLM_PROXY=1: starting content proxy -> ${CC_BASE_URL}"
    # Ensure a PDF-to-text backend exists in the container. pymupdf ships manylinux
    # wheels (no compile) and is the fastest; fall back to pypdf if the wheel is
    # unavailable. If neither installs, the proxy still runs and placeholders PDFs
    # (agent keeps going, just blind on that doc) — it logs a WARNING at startup.
    if ! python3 -c "import fitz" 2>/dev/null; then
        pip3 install -q pymupdf 2>/dev/null || pip3 install -q pypdf 2>/dev/null || true
    fi
    UPSTREAM_BASE="${CC_BASE_URL}" PORT=8799 python3 /src_harness/glm_content_proxy.py \
        > /agent_logs/glm_proxy.log 2>&1 &
    # Wait for the proxy to accept connections (up to ~10s)
    for _ in $(seq 1 20); do
        if python3 -c "import socket,sys; s=socket.socket(); s.settimeout(0.3); sys.exit(0 if s.connect_ex(('127.0.0.1',8799))==0 else 1)" 2>/dev/null; then
            break
        fi
        sleep 0.5
    done
    CC_BASE_URL="http://127.0.0.1:8799"
    echo "[docker_claude_agent] Claude Code base URL now -> ${CC_BASE_URL} (via proxy)"
fi

# Create non-root user (--dangerously-skip-permissions refuses root)
useradd -m -s /bin/bash agent 2>/dev/null || true
chmod 777 /agent_logs

mkdir -p /home/agent/results /home/agent/workspace /home/agent/.claude

# Ensure agent owns everything in their home (including dirs just created)
chown -R agent:agent /home/agent

# Copy instruction into agent-readable workspace (not the raw /task mount)
cp /task/instruction.md /home/agent/workspace/instruction.md
chown agent:agent /home/agent/workspace/instruction.md

# Write Claude Code settings
cat > /home/agent/.claude/settings.json << EOF
{
  "env": {
    "ANTHROPIC_AUTH_TOKEN": "${ANTHROPIC_API_KEY}",
    "ANTHROPIC_BASE_URL": "${CC_BASE_URL}",
    "ANTHROPIC_MODEL": "${AGENT_MODEL}",
    "ANTHROPIC_DEFAULT_SONNET_MODEL": "${AGENT_MODEL}",
    "ANTHROPIC_DEFAULT_OPUS_MODEL": "${AGENT_MODEL}",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL": "${AGENT_MODEL}",
    "DISABLE_AUTOUPDATER": "1"
  },
  "permissions": {
    "allow": [
      "Bash(*)",
      "Read(*)",
      "Write(*)",
      "Edit(*)"
    ]
  }
}
EOF
chown -R agent:agent /home/agent/.claude

# Write the runner script (executed as user 'agent')
# Uses a concise prompt that directs the model to read the instruction file itself
cat > /tmp/run_claude.sh << 'RUNNER_EOF'
#!/bin/bash
cd /home/agent/workspace

SYSTEM_PROMPT="You are a scientific coding agent working autonomously inside a Docker container.

Your environment:
- Task instruction: /home/agent/workspace/instruction.md (read this first)
- Input data: /home/agent/data/ (datasets, code, PDFs, etc.)
- Output directory: /home/agent/results/ (write ALL deliverables here)

Workflow:
1. Read /home/agent/workspace/instruction.md to understand the task
2. Explore /home/agent/data/ to understand the available data
3. Complete the task as specified
4. Write all deliverables to /home/agent/results/

Rules:
- Work autonomously — do not stop to ask for confirmation
- Be thorough — implement ALL requirements from the instruction
- Run self-tests if the instruction asks for validation
- Do NOT install packages already available in the environment
- Do NOT look for or access any 'tests' directory — evaluation is external"

PROMPT="Read /home/agent/workspace/instruction.md and complete the task described there. Write all output deliverables to /home/agent/results/."

EFFORT_ARGS=()
[ -n "${CC_EFFORT:-}" ] && EFFORT_ARGS=(--effort "${CC_EFFORT}")

claude -p \
    --model "${AGENT_MODEL}" \
    "${EFFORT_ARGS[@]}" \
    --dangerously-skip-permissions \
    --no-session-persistence \
    --verbose \
    --output-format stream-json \
    --system-prompt "${SYSTEM_PROMPT}" \
    "${PROMPT}"
RUNNER_EOF
chmod +x /tmp/run_claude.sh

echo "[docker_claude_agent] Starting Claude Code (model: ${AGENT_MODEL})"
echo "[docker_claude_agent] Base URL: ${CC_BASE_URL}"
echo "[docker_claude_agent] Workspace: /home/agent/workspace"
echo "[docker_claude_agent] Data dir: /home/agent/data/"
echo "[docker_claude_agent] Results dir: /home/agent/results/"
echo ""

# Run as non-root user; capture exit code without terminating script
su agent -c "
    export ANTHROPIC_API_KEY='${ANTHROPIC_API_KEY}'
    export ANTHROPIC_BASE_URL='${CC_BASE_URL}'
    export AGENT_MODEL='${AGENT_MODEL}'
    export MAX_THINKING_TOKENS='${MAX_THINKING_TOKENS:-}'
    export CC_EFFORT='${CC_EFFORT:-}'
    export DISABLE_AUTOUPDATER=1
    export HOME=/home/agent
    bash /tmp/run_claude.sh
" 2>&1 | tee /agent_logs/agent.log
CLAUDE_EXIT=${PIPESTATUS[0]}

echo ""
echo "[docker_claude_agent] Claude Code exited with code: ${CLAUDE_EXIT}"
echo ""

# Always archive results regardless of exit code
echo "=== Agent output files: ==="
find /home/agent/results -type f 2>/dev/null | head -50

FILE_COUNT=$(find /home/agent/results -type f 2>/dev/null | wc -l)
echo "Total files: ${FILE_COUNT}"

if [ "$FILE_COUNT" -gt 0 ]; then
    tar czf /agent_logs/results.tar.gz -C /home/agent results/ 2>/dev/null
    echo "[docker_claude_agent] Results archived to /agent_logs/results.tar.gz"
else
    echo "[docker_claude_agent] WARNING: No output files produced"
fi

exit 0
