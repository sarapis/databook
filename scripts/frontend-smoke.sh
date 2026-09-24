#!/usr/bin/env bash
# Sweep every page family the Laravel app routes and record what each returns.
#
# WHY THIS IS A DIFF AND NOT A LIST OF EXPECTED 200s
# ==================================================
# CI boots the stack against an EMPTY Postgres (no seed). On an empty database a
# page that 500s because a controller indexed an empty API result is
# byte-identical to a page that 500s because a framework upgrade broke it — the
# same failure this repo keeps paying for, one layer up. So this asserts nothing
# about what a page SHOULD return. It records what every page DOES return on
# `main`, and fails when a change moves any of them.
#
# That is exactly the signal a framework migration needs (see issue #382): a
# route that stops resolving, a view that stops compiling, a class that stops
# loading, all move a status. It is NOT a content check — a page that renders
# with wrong data keeps its status and passes here.
#
#   ./scripts/frontend-smoke.sh --baseline > scripts/frontend-smoke-baseline.tsv
#   ./scripts/frontend-smoke.sh                    # compare, non-zero on drift
#   ./scripts/frontend-smoke.sh '' https://databook.nyc   # against a real host
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROUTES="$ROOT/app/routes/web.php"
BASELINE="$ROOT/scripts/frontend-smoke-baseline.tsv"
MODE="${1:-compare}"
BASE="${2:-http://localhost:8580}"

# Routes excluded from the sweep, each with the reason it cannot be asserted.
# ⚠ Keep this list short and reasoned. Excluding a route because it is
# inconvenient is how a sweep quietly stops covering the thing that breaks.
is_excluded() {
  case "$1" in
    # Reaches the Payload CMS at next.sarapis.org. An external service makes the
    # result depend on someone else's uptime, which would make this check flaky
    # and therefore ignored.
    /blog|/blog/*) return 0 ;;
    # nginx basic-auth gated, and the gate differs between the CI conf and prod.
    # Covered behaviourally by api/tests/test_review_ui.py instead.
    /admin|/admin/*|/review|/review/*) return 0 ;;
  esac
  return 1
}

urls() {
  # ⚠ Comments are stripped FIRST. Without this the sweep picks up
  # `#Route::get('/sitemap.xml', ...)` — a route commented out in web.php — and
  # then asserts on a URL that is not routed at all.
  sed -E 's://.*$::; s:^[[:space:]]*#.*$::' "$ROUTES" \
    | grep -oE "Route::get\(\s*'/[^']*'" \
    | sed -E "s:.*'(/[^']*)':\1:" \
    | grep -v '{' | sort -u \
    | while read -r u; do is_excluded "$u" || echo "$u"; done
}

# ⚠ NOT `mapfile`/`readarray` — those are bash 4+ BUILTINS and macOS ships bash
# 3.2.57, where this script died with `mapfile: command not found` followed by
# `URLS: unbound variable`. CI runs Ubuntu/bash 5, so it merged green and the
# breakage was visible only on a developer's machine — two permanently-red tests
# on every local run, which is how a red signal stops being read.
# ⚠ `URLS=()` first is load-bearing under `set -u`: bash 3.2 treats an
# expansion of an undeclared array as an unbound variable.
URLS=()
while IFS= read -r u; do URLS+=("$u"); done < <(urls)
# Non-vacuity: a sweep that finds nothing passes silently, which is the defect
# this repo has shipped more than once. web.php has ~75 parameterless GET
# routes; a floor well under that catches a broken extractor without failing on
# ordinary route churn.
if [ "${#URLS[@]}" -lt 40 ]; then
  echo "::error::route extraction found only ${#URLS[@]} URLs — the scanner is wrong" >&2
  exit 2
fi

# Printing the list without probing, so the extraction can be verified on its
# own — including from a guard test, which must share this function rather than
# reimplement it.
if [ "$MODE" = "--urls" ]; then printf '%s\n' "${URLS[@]}"; exit 0; fi

probe() { curl -s -o /dev/null -w '%{http_code}' --max-time 40 "$BASE$1"; }

# Pre-warm, results discarded. The app aborts to 404 when the api exceeds its
# 15s reqOCE timeout, and a cold api is slow enough to trip that — so measuring
# a cold stack records timeouts as if they were routing. Warming first removes
# the flake at its source rather than retrying until it passes.
for u in "${URLS[@]}"; do probe "$u" >/dev/null; done

observed=$(for u in "${URLS[@]}"; do printf '%s\t%s\n' "$(probe "$u")" "$u"; done)

if [ "$MODE" = "--baseline" ]; then
  printf '# frontend page-family baseline — see scripts/frontend-smoke.sh\n'
  printf '# status\turl\n'
  printf '%s\n' "$observed"
  exit 0
fi

if [ ! -f "$BASELINE" ]; then
  # Fail closed AND hand over the table, so the first run in a new environment
  # produces the thing it is asking for instead of just refusing.
  echo "::error::no baseline at $BASELINE — commit the table below as that file" >&2
  printf '# frontend page-family baseline — see scripts/frontend-smoke.sh\n'
  printf '# status\turl\n'
  printf '%s\n' "$observed"
  exit 2
fi

diff -u <(grep -v '^#' "$BASELINE") <(printf '%s\n' "$observed") > /tmp/fe-smoke.diff 2>&1
if [ -s /tmp/fe-smoke.diff ]; then
  echo "::error::a page family changed what it returns:" >&2
  cat /tmp/fe-smoke.diff >&2
  exit 1
fi
echo "frontend smoke OK — ${#URLS[@]} page families, all matching the baseline"
