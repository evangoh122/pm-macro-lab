#!/usr/bin/env bash
# Pick the Coder and Validator pair for a build round from the UTC hour.
#
#   .agents/pick-roles.sh              # coder/validator for "now" (UTC)
#   .agents/pick-roles.sh --keep C V   # echo an existing pair (fix rounds)
#
# Prints exactly two lines:
#   CODER=<mimo|deepseek>
#   VALIDATOR=<deepseek|mimo>
#
# Rule: MiMo codes only while DeepSeek is in its peak window; otherwise
# DeepSeek codes and MiMo validates. The pair is always cross-model: the
# validator is never the coder's model.
#
# The DeepSeek peak window is not hardcoded. It is supplied by the owner:
#   PEAK_START_UTC  first peak hour, 0-23 (inclusive)
#   PEAK_END_UTC    first non-peak hour, 0-23 (exclusive)
# The window is half-open [start, end) and may wrap midnight (e.g. 22 -> 6).
# If either variable is unset, set-but-empty, non-numeric or out of range the
# script exits 2 without printing a pair (fail closed: no guessing a window).
#
# Test hook:
#   NOW_UTC_HOUR  override the current UTC hour (0-23) instead of reading clock.
#                 If it is set at all it must be a valid hour: an explicitly
#                 empty value is an error, not "use the real clock".

set -uo pipefail

usage() {
  cat >&2 <<'EOF'
usage: pick-roles.sh
       pick-roles.sh --keep <mimo|deepseek> <deepseek|mimo>
env (required for the time-based mode):
  PEAK_START_UTC  first DeepSeek peak hour, 0-23 inclusive
  PEAK_END_UTC    first non-peak hour, 0-23 exclusive (may wrap midnight)
env (optional):
  NOW_UTC_HOUR    override the current UTC hour (0-23), for tests
EOF
}

fail() {
  echo "[pick-roles] error: $*" >&2
  exit 2
}

is_model() {
  case "${1:-}" in
    mimo | deepseek) return 0 ;;
    *) return 1 ;;
  esac
}

is_hour() {
  case "${1:-}" in
    '' | *[!0-9]*) return 1 ;;
  esac
  [ "$1" -ge 0 ] && [ "$1" -le 23 ]
}

# --keep: repeat the pair chosen at the start of the round (fix rounds).
if [ "${1:-}" = "--keep" ]; then
  [ "$#" -eq 3 ] || { usage; exit 2; }
  keep_coder="$2"
  keep_validator="$3"
  is_model "$keep_coder" || fail "invalid coder '$keep_coder' (want mimo|deepseek)"
  is_model "$keep_validator" || fail "invalid validator '$keep_validator' (want mimo|deepseek)"
  [ "$keep_coder" != "$keep_validator" ] ||
    fail "coder and validator must differ (both '$keep_coder')"
  echo "CODER=$keep_coder"
  echo "VALIDATOR=$keep_validator"
  exit 0
fi

case "${1:-}" in
  -h | --help) usage; exit 0 ;;
  '') ;;
  *) usage; exit 2 ;;
esac

# Unset means "owner has not supplied the window" -> fail closed.
if [ -z "${PEAK_START_UTC+x}" ] || [ -z "${PEAK_END_UTC+x}" ]; then
  fail "DeepSeek peak window unknown: set PEAK_START_UTC and PEAK_END_UTC (hours 0-23).
       The owner must supply the verified DeepSeek peak window; this script does not guess."
fi

# Set-but-empty is a malformed window, not a missing one: still exit 2.
is_hour "$PEAK_START_UTC" || fail "PEAK_START_UTC='$PEAK_START_UTC' is not an hour 0-23"
is_hour "$PEAK_END_UTC" || fail "PEAK_END_UTC='$PEAK_END_UTC' is not an hour 0-23"
[ "$PEAK_START_UTC" -ne "$PEAK_END_UTC" ] ||
  fail "PEAK_START_UTC and PEAK_END_UTC are both $PEAK_START_UTC: empty/ambiguous window"

# Set at all (even empty) means the caller is supplying the hour: validate it.
# Only a truly unset NOW_UTC_HOUR falls back to the wall clock.
if [ -n "${NOW_UTC_HOUR+x}" ]; then
  is_hour "$NOW_UTC_HOUR" || fail "NOW_UTC_HOUR='$NOW_UTC_HOUR' is not an hour 0-23"
  hour="$NOW_UTC_HOUR"
else
  hour="$(date -u +%-H)" || fail "could not read the UTC hour from date(1)"
  is_hour "$hour" || fail "date(1) returned a non-hour: '$hour'"
fi

# Half-open [start, end); a start greater than end wraps through midnight.
if [ "$PEAK_START_UTC" -lt "$PEAK_END_UTC" ]; then
  if [ "$hour" -ge "$PEAK_START_UTC" ] && [ "$hour" -lt "$PEAK_END_UTC" ]; then
    in_peak=1
  else
    in_peak=0
  fi
else
  if [ "$hour" -ge "$PEAK_START_UTC" ] || [ "$hour" -lt "$PEAK_END_UTC" ]; then
    in_peak=1
  else
    in_peak=0
  fi
fi

if [ "$in_peak" -eq 1 ]; then
  echo "CODER=mimo"
  echo "VALIDATOR=deepseek"
else
  echo "CODER=deepseek"
  echo "VALIDATOR=mimo"
fi
