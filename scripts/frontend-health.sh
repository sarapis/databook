#!/usr/bin/env bash
# Is the PUBLIC SITE actually serving? Not the api — the pages.
#
# WHY THIS EXISTS
# ---------------
# On 2026-08-31 the whole site returned 504 for hours and NOTHING ALERTED. The
# 504s ran at 150-550 per MINUTE, peaking at 18,947 in one hour, in bursts since
# 28 August. Every monitor we had was looking somewhere else:
#   * Sentry            — watches the API, which was healthy the entire time.
#   * healthchecks.io   — watches CRONS. Every cron ran fine.
#   * prod-smoke.sh     — the only thing that checks pages, and it is MANUAL.
#   * lake-staleness    — data freshness, unaffected.
# Everything green, site down. That is the permanently-red monitor inverted, and
# it is worse: a red monitor is at least visible.
#
# The mechanism was /research/digital-reform/contracts costing 11-17s per novel
# parameter combination against pm.max_children = 15, so a distributed crawler
# held every php-fpm worker and pages that render in 0.02s could not get one.
#
# ⚠⚠ THIS CHECKS A PAGE, AND A CHEAP ONE ON PURPOSE. The failure mode is worker
# STARVATION, so the signal is that a page which should be instant is not. A
# check pointed at the expensive page would measure that page's own cost and
# tell you nothing about whether the site is up.
#
# ⚠ It reads the nginx log as a SECOND, independent signal. The HTTP check can
# get lucky — 40% of requests were still succeeding at the worst moment — so a
# single 200 does not mean healthy. The 5xx RATE does.
#
# Install (root's crontab) — every 10 min, off :00 to miss the 04:00 api restart
# and off multiples of 5 to miss the sheets export:
#   3,13,23,33,43,53 * * * * /home/ubuntu/databook/scripts/frontend-health.sh \
#     >> /home/ubuntu/databook/scripts/frontend-health.cron.log 2>&1
set -uo pipefail

ROOT="${ROOT:-/home/ubuntu/databook}"
LOG="${LOG:-$ROOT/scripts/frontend-health.log}"
COMPOSE="docker compose -f $ROOT/docker-compose.yml"

# ⚠⚠ CRON HAS ALMOST NO ENVIRONMENT, so HC_URL_FRONTEND must be READ FROM .env
# here or the ping is a permanent no-op — the check would be created, never
# pinged, and go down on its first missed schedule. That is a red monitor
# manufactured by omission, and this repo has the scar (register_untracked_tables
# was unreachable in prod for months while reading as active). Every other
# monitor here does the same thing; egress-check.sh line 56 is the precedent.
# shellcheck source=/dev/null
[ -f "$ROOT/.env" ] && . "$ROOT/.env"

# The page must be cheap. / is the home page; it renders in ~0.2s when healthy.
PROBE_PATH="${PROBE_PATH:-/}"
# ⚠ Generous but finite. Healthy is ~0.2s; 15s means "a worker was not free",
# which is the condition being detected, not a slow page.
PROBE_TIMEOUT="${PROBE_TIMEOUT:-15}"
# Fail when more than this share of page responses in the window are 5xx.
MAX_5XX_PCT="${MAX_5XX_PCT:-10}"
WINDOW="${WINDOW:-10m}"
# ⚠ A floor, so a genuinely quiet window cannot produce a scary percentage from
# three requests. Below this the rate check abstains and only the probe counts.
MIN_SAMPLE="${MIN_SAMPLE:-20}"

log() { echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') $*" | tee -a "$LOG"; }

REPORTED=0
hc() {
    local suffix="$1"
    [ -n "${HC_URL_FRONTEND:-}" ] || return 0
    curl -fsS -m 10 --retry 2 -o /dev/null "${HC_URL_FRONTEND}${suffix}" || true
}
fail() {
    REPORTED=1
    log "FAIL: $*"
    hc "/fail"
    exit 1
}
# ⚠ set -e is not enough: the most likely death is `docker compose logs` dying
# mid-pipe, which never reaches a fail() call. Same reason dos-crosswalk-refresh
# carries one.
trap 'rc=$?; if [ "$rc" -ne 0 ] && [ "$REPORTED" -eq 0 ]; then
        log "FAIL: died with exit $rc before reporting"; hc "/fail"; fi' EXIT

hc "/start"

# ---- signal 1: can a cheap page be served at all? --------------------------
# ⚠ Through nginx at the ORIGIN with a Host header, not through Cloudflare: a
# CF edge HIT would answer while the origin is dead, which is precisely the
# state this must catch.
# ⚠ NO `|| echo 000` — curl already WRITES 000 on a connection failure, so a
# fallback appends a SECOND one and the log reads "000000". And ONE request, not
# two, so the status and the timing describe the same attempt rather than two
# attempts that can disagree.
probe=$(curl -s -o /dev/null -w '%{http_code} %{time_total}' -m "$PROBE_TIMEOUT" \
        -H "Host: databook.nyc" "http://127.0.0.1${PROBE_PATH}")
code=${probe%% *}
took=${probe##* }
code=${code:-000}

# ---- signal 2: what share of real page traffic is failing? -----------------
lines=$($COMPOSE logs --since "$WINDOW" --no-log-prefix nginx 2>/dev/null \
        | grep -c 'HTTP/' || true)
lines=${lines:-0}
# ⚠⚠ AN UNREADABLE LOG IS NOT A QUIET PERIOD. Zero parsed lines from a service
# that serves constant traffic means the log format changed or the container was
# recreated — a broken measurement, and this repo's oldest defect is treating one
# as a clean result.
if [ "$lines" -eq 0 ]; then
    fail "parsed 0 request lines from the nginx log over $WINDOW — the check cannot see traffic, which is not the same as there being none"
fi

n5xx=$($COMPOSE logs --since "$WINDOW" --no-log-prefix nginx 2>/dev/null \
       | awk '$9 ~ /^5[0-9][0-9]$/' | grep -c 'HTTP/' || true)
n5xx=${n5xx:-0}
pct=$(( n5xx * 100 / lines ))

log "probe ${PROBE_PATH} -> ${code} in ${took}s | ${n5xx}/${lines} 5xx over ${WINDOW} (${pct}%)"

if [ "$code" != "200" ]; then
    fail "the home page returned ${code} in ${took}s — php-fpm workers are likely starved (see the 2026-08-31 incident in this file's header)"
fi
if [ "$lines" -ge "$MIN_SAMPLE" ] && [ "$pct" -gt "$MAX_5XX_PCT" ]; then
    fail "${pct}% of page responses are 5xx (${n5xx}/${lines}) over ${WINDOW} — the site is partially down even though this probe got a 200"
fi

log "OK"
hc ""
exit 0
