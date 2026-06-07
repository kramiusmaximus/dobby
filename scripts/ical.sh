#!/usr/bin/env bash
set -euo pipefail

ICAL=${ICAL:-/opt/homebrew/bin/ical}
ATTEMPTS=${ATTEMPTS:-3}
SLEEP_SECONDS=${SLEEP_SECONDS:-2}
LOG_FILE=${EVENTKIT_ACCESS_LOG:-/Users/kramiusmaximus/projects/dobby/tmp/eventkit-access.log}
PREFLIGHT=${CALENDAR_PREFLIGHT:-/Users/kramiusmaximus/projects/dobby/scripts/calendar_preflight.sh}

mkdir -p "$(dirname "$LOG_FILE")"

log() {
  printf '%s ical_wrapper %s\n' "$(date '+%Y-%m-%dT%H:%M:%S%z')" "$*" >>"$LOG_FILE"
}

access_error() {
  local text
  text=$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')
  [[ "$text" == *"access denied"* || "$text" == *"not-determined"* || "$text" == *"failed to initialize calendar"* ]]
}

if [[ ! -x "$ICAL" ]]; then
  echo "ical not found or not executable at $ICAL" >&2
  exit 127
fi

log "start pid=$$ ppid=$PPID command=$*"
"$PREFLIGHT" >/dev/null 2>>"$LOG_FILE" || log "preflight failed before command; continuing to command retries"

last_stdout=$(mktemp)
last_stderr=$(mktemp)
trap 'rm -f "$last_stdout" "$last_stderr"' EXIT

for attempt in $(seq 1 "$ATTEMPTS"); do
  : >"$last_stdout"
  : >"$last_stderr"
  if "$ICAL" "$@" >"$last_stdout" 2>"$last_stderr"; then
    log "command ok attempt=$attempt"
    cat "$last_stdout"
    cat "$last_stderr" >&2
    exit 0
  fi

  rc=$?
  combined="$(cat "$last_stderr" "$last_stdout")"
  log "command failed attempt=$attempt rc=$rc output=$(printf '%s' "$combined" | tr '\n' ' ' | cut -c 1-500)"

  if access_error "$combined" && [[ "$attempt" -lt "$ATTEMPTS" ]]; then
    open -b com.apple.iCal >/dev/null 2>&1 || open -a Calendar >/dev/null 2>&1 || true
    osascript -e 'tell application "Calendar" to get name of calendars' >/dev/null 2>&1 || true
    sleep "$SLEEP_SECONDS"
    continue
  fi

  cat "$last_stdout"
  cat "$last_stderr" >&2
  exit "$rc"
done
