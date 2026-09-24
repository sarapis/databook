#!/bin/bash
# Daily rollup of MCP and public-API usage into Postgres.
#
# WHY THIS EXISTS
# ---------------
# We could not answer "who uses the public MCP server, and which tools do they
# call?" — not because nothing is instrumented, but because the instrumentation
# is thrown away. `api/mcp_server.py` already logs `TOOL CALL: <name>` and
# `SESSION:` for every call, and nginx logs every request with IP and
# User-Agent. Both go to docker json-file logs that are BOUNDED and reset when a
# container is recreated: measured 2026-08-21, the mcp log reached back 3 days
# and the api log only as far as the previous deploy. So the data exists for a
# few days and then is gone forever, and nobody had ever aggregated it.
#
# This turns that into permanent history in two Postgres tables. It is
# deliberately a HOST script, not an api job: reading `docker compose logs`
# needs the docker socket, which the api container does not have and should not.
#
# WHAT IT MEASURED ON THE FIRST LOOK, so a future reader knows the starting point:
#   * public API v1 had SIX requests in 24h and all six were one vulnerability
#     scanner probing /api/v1/settings, /config, /env — paths that do not exist.
#     Effectively zero real usage.
#   * /mcp had 131 requests, of which the attributable external slice was UA
#     `Claude-User` from Anthropic's ranges. Real, but small.
#   * the api hostname's actual traffic is a crawler: /oce/transactions 6,616.
#
# ⚠⚠ IT EXCLUDES OUR OWN MONITORING BY DEFAULT. The daily MCP tool audit makes
# 40 calls a day. Sessions are opaque ids and the audit used to send a plain
# browser User-Agent, so it was indistinguishable from a real user — i.e. this
# rollup would have reported our own health check as user demand, which is the
# same family of mistake as a monitor that is green for the wrong reason. The
# audit now appends `databook-mcp-audit/1` to its UA and that is what
# AUDIT_TOKEN filters. Audit rows are still COUNTED, under client
# 'self:audit', rather than dropped — a category you cannot see is one you
# cannot sanity-check.
#
# ⚠ A DAY WITH NO TOOL CALLS IS LEGITIMATE; AN UNREADABLE LOG IS NOT. Those two
# are indistinguishable in a plain count of zero, which is this repository's
# oldest recurring defect. So the script asserts it could READ the logs at all
# (the mcp container is polled constantly by /admin/logs, so its log is never
# genuinely empty) and only then allows a tool-call count of zero.
#
# Runs for a COMPLETE past day, default yesterday, so counts are never partial.
# Idempotent: re-running any date replaces that date's rows.
#
#   scripts/usage-rollup.sh                # yesterday
#   scripts/usage-rollup.sh 2026-08-19     # a specific day (must be in the logs)
#
set -euo pipefail

ROOT=${DATABOOK_ROOT:-/home/ubuntu/databook}
LOG="$ROOT/scripts/usage-rollup.log"
log(){ echo "[$(date -u +%FT%TZ)] $*" | tee -a "$LOG"; }
[ -f "$ROOT/.env" ] && . "$ROOT/.env"    # SENTRY_DSN + HC_URL_* (gitignored)

DAY=${1:-$(date -u -d yesterday +%F)}
NEXT=$(date -u -d "$DAY + 1 day" +%F)
AUDIT_TOKEN=${AUDIT_UA_TOKEN:-databook-mcp-audit/1}

dc(){ docker compose -f "$ROOT/docker-compose.yml" "$@"; }
psql_q(){  dc exec -T postgres psql -U postgres -d databook -tAF$'\t' -c "$1" 2>/dev/null; }

HC_URL="${HC_URL_USAGE_ROLLUP:-}"
hc_ping(){   # $1 = success | fail
  [ -n "$HC_URL" ] || return 0
  local u="$HC_URL"; [ "$1" = fail ] && u="$u/fail"
  tail -n 40 "$LOG" 2>/dev/null | curl -fsS -m 20 -o /dev/null --data-binary @- "$u" 2>/dev/null || true
}

REPORTED=0
MCP_RAW=""; NGX_RAW=""; ROLL=""; ERR=""
fail(){ log "FAIL: $*"; REPORTED=1; hc_ping fail; exit 1; }

# ⚠ ONE handler, registered once. `set -e` can kill this mid-`docker compose
# logs`, the likeliest failure, and that path never reaches fail() — the same
# reason dos-crosswalk-refresh.sh guards its exit.
# ⚠⚠ Two mistakes not to repeat, both of which the first draft of this script
# made: several `EXIT` handlers OVERWRITE each other, and the last one had no
# failure reporting — so the cleanup silently disarmed the alarm. And `$?` read
# after a `&&` chain is the status of the preceding TEST, not of the script, so
# it has to be captured on the handler's first line.
cleanup(){
  local rc=$?
  rm -f "$MCP_RAW" "$NGX_RAW" "$ROLL" "$ERR" 2>/dev/null || true
  if [ "$rc" -ne 0 ] && [ "$REPORTED" -eq 0 ]; then
    log "FAIL: aborted unexpectedly (exit $rc)"
    hc_ping fail
  fi
}
trap cleanup EXIT

log "=== usage rollup for $DAY (audit token: $AUDIT_TOKEN) ==="

# ⚠⚠ THE SCHEMA IS EMITTED INTO THE TRANSACTION BELOW, NOT RUN HERE. It used to
# run at this point, which meant DRY_RUN=1 CREATED TWO TABLES — "a dry run that
# creates its own table is not dry" is already a documented lesson in this repo
# and I reproduced it anyway. One DDL definition, inside the same transaction as
# the inserts, so `DRY_RUN=1` is the only mode that touches nothing.

# --- read the logs for the window ----------------------------------------------
MCP_RAW=$(mktemp); NGX_RAW=$(mktemp)

dc logs mcp   --no-log-prefix --since "${DAY}T00:00:00" --until "${NEXT}T00:00:00" > "$MCP_RAW" 2>/dev/null || true
dc logs nginx --no-log-prefix --since "${DAY}T00:00:00" --until "${NEXT}T00:00:00" > "$NGX_RAW" 2>/dev/null || true

# ⚠⚠ COVERAGE START COMES FROM DOCKER'S OWN TIMESTAMPS, not from the app's log
# format. The mcp container's uvicorn access lines carry NO timestamp at all, so
# parsing the app format finds the first *tool call* of the day — which on a
# normal day is hours in, and made the partial-window guard fire on almost every
# complete day. `--timestamps` stamps every line, so the first one is the real
# start of retained coverage (and it catches log ROTATION as well as container
# recreation, which a container-start time would miss).
first_ts(){   # $1 = service -> RFC3339 of the earliest retained line in the window
  dc logs "$1" --no-log-prefix --timestamps \
     --since "${DAY}T00:00:00" --until "${NEXT}T00:00:00" 2>/dev/null \
   | head -1 | grep -oE '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}' || true
}
MCP_FROM=$(first_ts mcp); NGX_FROM=$(first_ts nginx)
log "coverage starts: mcp=${MCP_FROM:-none} nginx=${NGX_FROM:-none}"

MCP_LINES=$(wc -l < "$MCP_RAW"); NGX_LINES=$(wc -l < "$NGX_RAW")
log "read mcp=$MCP_LINES lines, nginx=$NGX_LINES lines"

# ⚠ THE "IT LOOKED" ASSERTION. Both containers serve constant traffic, so an
# empty window means the retention has rolled past $DAY (or the container was
# recreated) — NOT that nobody used anything. Reporting 0 there would be a
# measurement that reads as data.
[ "$MCP_LINES" -gt 0 ] || fail "mcp log has no lines for $DAY — outside retention, or the container was recreated. Refusing to record zeros."
[ "$NGX_LINES" -gt 0 ] || fail "nginx log has no lines for $DAY — outside retention, or the container was recreated. Refusing to record zeros."

# --- aggregate ------------------------------------------------------------------
ROLL=$(mktemp); ERR=$(mktemp)
# ⚠ The heredoc must stay attached to this python call, so the exit status is
# captured AFTER it closes — and errexit is lifted across it so a deliberate
# refusal (a partial window) is reported with its reason instead of aborting
# the script bare.
set +e
python3 - "$MCP_RAW" "$NGX_RAW" "$DAY" "$AUDIT_TOKEN" "${ALLOW_PARTIAL:-0}" \
    "$MCP_FROM" "$NGX_FROM" > "$ROLL" 2>"$ERR" <<'PYEOF'
import collections, datetime, re, sys

mcp_path, ngx_path, day, audit_token = sys.argv[1:5]
allow_partial = len(sys.argv) > 5 and sys.argv[5] == "1"

# ---- PARTIAL-WINDOW DETECTION -------------------------------------------------
# ⚠⚠ A PARTIAL DAY IS INDISTINGUISHABLE FROM A QUIET ONE, which is the same
# defect as the zero-count the shell already guards. Recreating a container
# TRUNCATES its docker log, so a rebuild at 03:00 leaves the rest of that day
# looking like a complete but very quiet day — and the count would be recorded
# as fact. Rebuilding the mcp container is a routine deploy, so this is not
# hypothetical: it is the expected consequence of the next one.
#
# So: find the earliest line in each log and refuse if it starts materially
# after midnight. `ALLOW_PARTIAL=1` records it anyway, for when the gap is known
# and the number is still wanted.
_TOLERANCE_S = 300

# The two coverage starts are computed by the shell from `docker logs
# --timestamps` and passed in, precisely because the app log formats cannot
# answer this (see the note beside first_ts).
day_start = datetime.datetime.strptime(day, "%Y-%m-%d")
gaps = []
window_from = {}
for label, raw in (("mcp", sys.argv[6] if len(sys.argv) > 6 else ""),
                   ("nginx", sys.argv[7] if len(sys.argv) > 7 else "")):
    if not raw:
        sys.exit(f"could not determine {label} log coverage for {day} — refusing "
                 "to record, since an unknown window cannot be called complete.")
    first = datetime.datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S")
    window_from[label] = first
    late = (first - day_start).total_seconds()
    if late > _TOLERANCE_S:
        gaps.append(f"{label} log starts {first.isoformat()} "
                    f"({int(late // 60)} min into {day})")

if gaps and not allow_partial:
    sys.exit("PARTIAL WINDOW for " + day + ": " + "; ".join(gaps) +
             ". A truncated log reads as a quiet day, so this is refused rather "
             "than recorded. Re-run with ALLOW_PARTIAL=1 to record it anyway "
             "(most likely cause: a container was recreated during that day).")
if gaps:
    print("ALLOW_PARTIAL=1 — recording a known-incomplete day: "
          + "; ".join(gaps), file=sys.stderr)

def sql(v):
    return "'" + str(v).replace("'", "''") + "'"

# ⚠⚠ THE CLIENT DIMENSION IS A CLASS, NOT THE RAW USER-AGENT. The first draft
# used the UA and produced 122 rows for ONE DAY — unbounded cardinality that
# grows forever and buries the answer, because every browser patch release is a
# new "client". This closed vocabulary keeps a day to a couple of dozen rows.
#
# ⚠ `browser` DOES NOT MEAN HUMAN, and on this site it mostly is not: the
# largest bucket on 2026-08-20 was a Mac Safari UA with 11,649 requests from
# **2,209 distinct IPs**, which is the distributed crawler this repo has fought
# twice. That is why `distinct_ips` is stored beside every count — a browser UA
# spread over thousands of IPs is the tell, and no UA string will ever say so.
#
# Self-identifying bots keep their name because it is genuinely useful and
# bounded in practice; everything else collapses.
BOTS = ("Claude-User", "ClaudeBot", "GPTBot", "OAI-SearchBot", "PerplexityBot",
        "Googlebot", "Google-Agent", "Google-Extended", "bingbot", "DuckDuckBot",
        "DuckAssistBot", "Amazonbot", "Amzn-SearchBot", "Applebot", "YandexBot",
        "ExaSearchBot", "meta-externalagent", "SemrushBot", "AhrefsBot",
        "Bytespider", "facebookexternalhit")
SCRIPTS = ("python-requests", "Python-urllib", "curl/", "Wget/", "Go-http-client",
           "Bun/", "node-fetch", "axios/", "okhttp", "HTTPie")


def classify(ua, audit_token):
    """A bounded client class. Order matters: our own audit first, then declared
    bots, then obvious scripts, then a browser-shaped catch-all."""
    # ⚠ "unknown" is a real, distinct answer, not a fallback: MCP sessions
    # started before the CLIENT field shipped genuinely have no client, and that
    # must not read as "other" (an unclassifiable UA), or the two are conflated.
    if not ua or ua in ("-", "unknown"):
        return "unknown"
    if audit_token in ua:
        return "self:audit"
    for b in BOTS:
        if b.lower() in ua.lower():
            return f"bot:{b}"
    for t in SCRIPTS:
        if t.lower() in ua.lower():
            return "script:" + t.rstrip("/").lower()
    if ua.startswith("Mozilla/") or "AppleWebKit" in ua or "Gecko" in ua:
        return "browser"
    return "other"


# ---- MCP: TOOL CALL / SESSION|CLIENT come as consecutive lines ----------------
# TOOL CALL: <tool>
# SESSION: <id> | CLIENT: <client> | REQUEST #<n>
# ⚠ CLIENT is absent on sessions started before that field shipped; those count
# as 'unknown' rather than being dropped.
tool_re = re.compile(r"TOOL CALL: ([a-zA-Z_][a-zA-Z0-9_]*)")
sess_re = re.compile(r"SESSION: (\S+)(?: \| CLIENT: (.*?))? \| REQUEST #")
mcp = collections.defaultdict(lambda: {"calls": 0, "sessions": set()})
pending = None
with open(mcp_path, errors="replace") as fh:
    for line in fh:
        m = tool_re.search(line)
        if m:
            pending = m.group(1)
            continue
        m = sess_re.search(line)
        if m and pending:
            sid, client = m.group(1), (m.group(2) or "unknown").strip()
            label = classify(client, audit_token)
            e = mcp[(pending, label)]
            e["calls"] += 1
            e["sessions"].add(sid)
            pending = None

# ---- nginx: only the surfaces this exists to measure -------------------------
# ⚠ Deliberately NOT every path. The api hostname serves ~6,600 crawler hits a
# day to /oce/transactions alone; rolling all of it up would bury the signal and
# grow the table without answering the question. Grouped, not raw, so a path
# with an id or a query string does not become thousands of distinct rows.
GROUPS = (
    (re.compile(r"^/mcp"),        "/mcp"),
    (re.compile(r"^/api/v1/"),    "/api/v1/*"),
    (re.compile(r"^/oce/"),       "/oce/*"),
    (re.compile(r"^/get/"),       "/get/*"),
)
# combined log format: IP - - [ts] "METHOD path proto" status size "ref" "ua"
line_re = re.compile(r'^(\S+) \S+ \S+ \[[^\]]+\] "(\S+) (\S+)[^"]*" (\d{3}) \S+ "[^"]*" "([^"]*)"')
api = collections.defaultdict(lambda: {"requests": 0, "ips": set()})
with open(ngx_path, errors="replace") as fh:
    for line in fh:
        m = line_re.match(line.strip())
        if not m:
            continue
        ip, _method, path, _status, ua = m.groups()
        path = path.split("?", 1)[0]
        group = next((g for rx, g in GROUPS if rx.match(path)), None)
        if not group:
            continue
        client = classify(ua, audit_token)
        e = api[(group, client)]
        e["requests"] += 1
        e["ips"].add(ip)

# ---- emit one idempotent transaction ------------------------------------------
print("BEGIN;")
print("""CREATE TABLE IF NOT EXISTS mcp_usage_daily (
  day date NOT NULL, tool text NOT NULL, client text NOT NULL,
  calls integer NOT NULL, sessions integer NOT NULL,
  PRIMARY KEY (day, tool, client));""")
print("""CREATE TABLE IF NOT EXISTS api_usage_daily (
  day date NOT NULL, path text NOT NULL, client text NOT NULL,
  requests integer NOT NULL, distinct_ips integer NOT NULL,
  PRIMARY KEY (day, path, client));""")
# ⚠⚠ PROVENANCE, so a PARTIAL day can never be read as a complete one. Without
# this, `ALLOW_PARTIAL=1` would write rows indistinguishable from a full day —
# building exactly the "figure that looks measured but is not" trap this rollup
# exists to avoid. A consumer joining this table can always tell.
print("""CREATE TABLE IF NOT EXISTS usage_rollup_runs (
  day date PRIMARY KEY, mcp_log_from timestamp, ngx_log_from timestamp,
  partial boolean NOT NULL, ran_at timestamptz NOT NULL DEFAULT now());""")
print(f"DELETE FROM usage_rollup_runs WHERE day = {sql(day)};")
print("INSERT INTO usage_rollup_runs (day, mcp_log_from, ngx_log_from, partial) VALUES ("
      f"{sql(day)}, {sql(window_from['mcp'])}, {sql(window_from['nginx'])}, "
      f"{'true' if gaps else 'false'});")
print(f"DELETE FROM mcp_usage_daily WHERE day = {sql(day)};")
print(f"DELETE FROM api_usage_daily WHERE day = {sql(day)};")
for (tool, client), e in sorted(mcp.items()):
    print("INSERT INTO mcp_usage_daily (day, tool, client, calls, sessions) VALUES "
          f"({sql(day)}, {sql(tool)}, {sql(client)}, {e['calls']}, {len(e['sessions'])});")
for (path, client), e in sorted(api.items()):
    print("INSERT INTO api_usage_daily (day, path, client, requests, distinct_ips) VALUES "
          f"({sql(day)}, {sql(path)}, {sql(client)}, {e['requests']}, {len(e['ips'])});")
print("COMMIT;")
print(f"-- mcp rows: {len(mcp)}  api rows: {len(api)}")
PYEOF
rc=$?
set -e
[ "$rc" -eq 0 ] || fail "$(head -c 600 "$ERR")"
[ -s "$ERR" ] && log "note: $(head -c 400 "$ERR")" || true

MCP_ROWS=$(grep -c "INSERT INTO mcp_usage_daily" "$ROLL" || true)
API_ROWS=$(grep -c "INSERT INTO api_usage_daily" "$ROLL" || true)
log "aggregated mcp_rows=$MCP_ROWS api_rows=$API_ROWS"

# ⚠ nginx always serves SOMETHING on these prefixes, so zero api rows off a
# non-empty log means the parser stopped matching (a log-format change) rather
# than a quiet day. A tool-call count of zero IS allowed; a parse failure is not.
[ "$API_ROWS" -gt 0 ] || fail "parsed 0 api rows from $NGX_LINES nginx lines — the access-log format probably changed. Refusing to record zeros."

if [ "${DRY_RUN:-0}" = 1 ]; then
  log "DRY RUN — not writing. SQL follows:"; cat "$ROLL" | tee -a "$LOG"; exit 0
fi

dc exec -T postgres psql -U postgres -d databook -v ON_ERROR_STOP=1 -q < "$ROLL" >/dev/null \
  || fail "psql refused the rollup for $DAY"

# --- report what landed, from the table, not from the variables -----------------
SUMMARY=$(psql_q "
SELECT (SELECT coalesce(sum(calls),0) FROM mcp_usage_daily WHERE day='$DAY')::text
    || ' mcp calls / '
    || (SELECT count(DISTINCT tool) FROM mcp_usage_daily WHERE day='$DAY')::text
    || ' tools / '
    || (SELECT coalesce(sum(requests),0) FROM api_usage_daily WHERE day='$DAY')::text
    || ' api requests';")
EXTERNAL=$(psql_q "SELECT coalesce(sum(calls),0) FROM mcp_usage_daily WHERE day='$DAY' AND client <> 'self:audit';")
log "OK $DAY — $SUMMARY (mcp calls excluding our own audit: $EXTERNAL)"
hc_ping success
