#!/usr/bin/env bash
set -euo pipefail

ICAL=${ICAL:-/opt/homebrew/bin/ical}
ATTEMPTS=${ATTEMPTS:-5}
SLEEP_SECONDS=${SLEEP_SECONDS:-2}
LOG_FILE=${EVENTKIT_ACCESS_LOG:-/Users/kramiusmaximus/projects/dobby/tmp/eventkit-access.log}

mkdir -p "$(dirname "$LOG_FILE")"

log() {
  printf '%s calendar_preflight %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$*" >>"$LOG_FILE"
}

if [[ ! -x "$ICAL" ]]; then
  echo "ical not found or not executable at $ICAL" >&2
  echo "Install with: brew install BRO3886/tap/ical" >&2
  exit 127
fi

last_output=""

log "start pid=$$ ppid=$PPID attempts=$ATTEMPTS"
if osascript -e 'tell application "Calendar" to get name of calendars' >/dev/null 2>&1; then
  log "applescript warm-up ok"
else
  log "applescript warm-up failed"
fi

for attempt in $(seq 1 "$ATTEMPTS"); do
  if output=$("$ICAL" calendars --output json --no-color 2>&1); then
    log "ical calendars ok attempt=$attempt"
    echo "Calendar access: available via ical"
    exit 0
  fi

  last_output="$output"
  log "ical calendars failed attempt=$attempt output=$(printf '%s' "$output" | tr '\n' ' ' | cut -c 1-500)"

  if [[ "$output" == *"access denied"* || "$output" == *"not-determined"* || "$output" == *"failed to initialize"* ]]; then
    if [[ "$attempt" -eq 1 ]]; then
      open -b com.apple.iCal >/dev/null 2>&1 || open -a Calendar >/dev/null 2>&1 || true
      osascript -e 'tell application "Calendar" to get name of calendars' >/dev/null 2>&1 || true
    fi

    if [[ "$attempt" -lt "$ATTEMPTS" ]]; then
      sleep "$SLEEP_SECONDS"
      continue
    fi
  fi

  break
done

echo "Calendar access unavailable after $ATTEMPTS attempts via $ICAL" >&2
echo "$last_output" >&2
exit 1
