#!/usr/bin/env bash
# Dispatch a build or review request to one of the coordinated agents.
#
#   .agents/dispatch.sh <agent> <request-file> [timeout-seconds]
#
# agent: deepseek | mimo | codex
# Writes combined output to .agents/.agentlogs/<agent>-<request>.log (gitignored)
# and returns the agent's exit code.

set -uo pipefail

AGENT="${1:?usage: dispatch.sh <deepseek|mimo|codex> <request-file> [timeout]}"
REQUEST="${2:?usage: dispatch.sh <deepseek|mimo|codex> <request-file> [timeout]}"
TIMEOUT="${3:-1800}"

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

BRANCH="$(git branch --show-current)"
if [ "$BRANCH" = "main" ] || [ "$BRANCH" = "master" ]; then
  echo "[dispatch] error: refusing to dispatch on branch '$BRANCH'" >&2
  exit 2
fi

[ -f "$REQUEST" ] || { echo "no such request file: $REQUEST" >&2; exit 2; }

mkdir -p .agents/.agentlogs
LOG=".agents/.agentlogs/${AGENT}-$(basename "$REQUEST" .md).log"

PROMPT="You are working in the git repository at $REPO.

Read and follow the protocol at .agents/PROTOCOL.md, then read your role at
.agents/${AGENT}/ROLE.md, then execute the request in $REQUEST.

Work only inside $REPO. Do not push to main. Do not commit secrets.
When finished, write your verdict file exactly as PROTOCOL.md specifies."

echo "[dispatch] agent=$AGENT request=$REQUEST timeout=${TIMEOUT}s log=$LOG"

case "$AGENT" in
  deepseek)
    timeout "$TIMEOUT" opencode run --auto -m deepseek/deepseek-v4-pro \
      --title "pm-macro-lab-$(basename "$REQUEST" .md)" "$PROMPT" 2>&1 | tee "$LOG"
    ;;
  mimo)
    timeout "$TIMEOUT" opencode run --auto -m xiaomi-token-plan-sgp/mimo-v2.5-pro \
      --title "pm-macro-lab-$(basename "$REQUEST" .md)" "$PROMPT" 2>&1 | tee "$LOG"
    ;;
  codex)
    timeout "$TIMEOUT" codex exec --full-auto "$PROMPT" 2>&1 | tee "$LOG"
    ;;
  *)
    echo "unknown agent: $AGENT (expected deepseek|mimo|codex)" >&2; exit 2 ;;
esac

RCS=("${PIPESTATUS[@]}")
AGENT_RC=${RCS[0]}
TEE_RC=${RCS[1]}
RC=$AGENT_RC
[ "$TEE_RC" -eq 0 ] || RC=$((RC | TEE_RC))
echo "[dispatch] agent=$AGENT agent_rc=$AGENT_RC tee_rc=$TEE_RC exit=$RC"
exit "$RC"
