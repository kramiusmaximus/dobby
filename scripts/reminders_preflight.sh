#!/usr/bin/env bash
set -euo pipefail

REM=${REM:-/opt/homebrew/bin/rem}
ATTEMPTS=${ATTEMPTS:-5}
SLEEP_SECONDS=${SLEEP_SECONDS:-2}
LOG_FILE=${EVENTKIT_ACCESS_LOG:-/Users/kramiusmaximus/projects/dobby/tmp/eventkit-access.log}

mkdir -p "$(dirname "$LOG_FILE")"

log() {
  printf '%s reminders_preflight %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$*" >>"$LOG_FILE"
}

if [[ ! -x "$REM" ]]; then
  echo "rem not found or not executable at $REM" >&2
  echo "Install with: brew install BRO3886/tap/rem-cli" >&2
  exit 127
fi

last_output=""

log "start pid=$$ ppid=$PPID attempts=$ATTEMPTS"
if osascript -e 'tell application "Reminders" to get name of every list' >/dev/null 2>&1; then
  log "applescript warm-up ok"
else
  log "applescript warm-up failed"
fi

for attempt in $(seq 1 "$ATTEMPTS"); do
  if output=$("$REM" lists --output json --no-color 2>&1); then
    log "rem lists ok attempt=$attempt"
    echo "Reminders access: available via rem"
    exit 0
  fi

  last_output="$output"
  log "rem lists failed attempt=$attempt output=$(printf '%s' "$output" | tr '\n' ' ' | cut -c 1-500)"

  if [[ "$output" == *"access denied"* || "$output" == *"not-determined"* || "$output" == *"failed to initialize Reminders access"* ]]; then
    if [[ "$attempt" -eq 1 ]]; then
      open -b com.apple.reminders >/dev/null 2>&1 || true
      osascript -e 'tell application "Reminders" to get name of every list' >/dev/null 2>&1 || true
    fi

    if [[ "$attempt" -lt "$ATTEMPTS" ]]; then
      sleep "$SLEEP_SECONDS"
      continue
    fi
  fi

  break
done

echo "Reminders access unavailable after $ATTEMPTS attempts via $REM" >&2
echo "$last_output" >&2
exit 1
