#!/bin/bash
# Read-only usage report over the tables scripts/usage-rollup.sh maintains.
#
#   scripts/usage-report.sh              # last 7 complete days
#   scripts/usage-report.sh 30           # last 30
#   scripts/usage-report.sh 7 --audit    # include our own monitoring
#
# Answers "who uses the public MCP server and API, and which tools do they
# call?". Writes nothing.
#
# ⚠⚠ IT LEADS WITH COVERAGE, AND THAT IS THE POINT. A report over "the last 7
# days" that quietly omits the days it has no data for reads as a complete week —
# the same defect as a truncated list presenting itself as the whole set (the
# `by_vendor` 25-of-88 case). Days with no row are printed as MISSING and days
# recorded from a truncated log as partial, so a total is always read against the
# days it actually covers.
#
# ⚠ `self:audit` is excluded from the totals by default because our own daily
# tool audit makes 40 calls a day and would dominate every figure — but the
# amount excluded is always PRINTED, because a category you cannot see is one you
# cannot sanity-check.
set -euo pipefail

ROOT=${DATABOOK_ROOT:-/home/ubuntu/databook}
DAYS=7
INCLUDE_AUDIT=0
for a in "$@"; do
  case "$a" in
    --audit) INCLUDE_AUDIT=1 ;;
    ''|*[!0-9]*) [ "$a" = "--audit" ] || { echo "usage: $(basename "$0") [days] [--audit]" >&2; exit 2; } ;;
    *) DAYS="$a" ;;
  esac
done

psql_c(){ docker compose -f "$ROOT/docker-compose.yml" exec -T postgres \
            psql -U postgres -d databook -q "$@" 2>/dev/null; }

# The audit filter, as one string reused by every query so the sections cannot
# disagree about what they are counting.
if [ "$INCLUDE_AUDIT" = 1 ]; then AUDIT_FILTER="true"; else AUDIT_FILTER="client <> 'self:audit'"; fi

if ! psql_c -tAc "SELECT 1 FROM information_schema.tables WHERE table_name='usage_rollup_runs';" | grep -q 1; then
  echo "No usage data yet: usage_rollup_runs does not exist."
  echo "Run scripts/usage-rollup.sh (or wait for the 05:20 UTC cron) first."
  exit 0
fi

echo "================================================================"
echo " Databook usage — last $DAYS complete days$([ "$INCLUDE_AUDIT" = 1 ] && echo ' (INCLUDING self:audit)')"
echo " generated $(date -u +%FT%TZ)"
echo "================================================================"

echo
echo "--- COVERAGE (read every total below against this) ---"
psql_c -c "
WITH span AS (
  SELECT generate_series(current_date - ${DAYS}, current_date - 1, interval '1 day')::date AS day)
SELECT s.day,
       CASE WHEN r.day IS NULL THEN 'MISSING'
            WHEN r.partial   THEN 'partial'
            ELSE 'ok' END AS status,
       r.mcp_log_from, r.ngx_log_from
FROM span s LEFT JOIN usage_rollup_runs r ON r.day = s.day
ORDER BY s.day;"

echo "--- MCP: tool calls by client ---"
psql_c -c "
SELECT client, tool, sum(calls) AS calls, sum(sessions) AS sessions
FROM mcp_usage_daily
WHERE day >= current_date - ${DAYS} AND ${AUDIT_FILTER}
GROUP BY 1,2 ORDER BY calls DESC, tool LIMIT 40;"

echo "--- API: requests by surface and client ---"
# ⚠ distinct_ips is per DAY and cannot be summed across days (the same IP
# recurring would be counted twice), so the peak day is reported instead. A
# summed "distinct IPs" would be a plausible-looking number that means nothing.
psql_c -c "
SELECT path, client, sum(requests) AS requests, max(distinct_ips) AS peak_day_ips
FROM api_usage_daily
WHERE day >= current_date - ${DAYS} AND ${AUDIT_FILTER}
GROUP BY 1,2 ORDER BY requests DESC LIMIT 40;"

# Only meaningful when the audit was in fact excluded; printing "excluded: 0"
# under --audit reads as "we have no monitoring traffic", which is false.
if [ "$INCLUDE_AUDIT" = 0 ]; then
echo "--- WHAT WAS EXCLUDED (our own monitoring) ---"
psql_c -c "
SELECT 'mcp' AS surface, coalesce(sum(calls),0) AS n FROM mcp_usage_daily
  WHERE day >= current_date - ${DAYS} AND client = 'self:audit'
UNION ALL
SELECT 'api', coalesce(sum(requests),0) FROM api_usage_daily
  WHERE day >= current_date - ${DAYS} AND client = 'self:audit';"
fi

echo "⚠ 'browser' is a UA CLASS, not a human: the largest bucket here is a"
echo "  distributed crawler. Read peak_day_ips beside every count — thousands of"
echo "  IPs on one browser UA is the tell."
