#!/usr/bin/env python3
"""Call every Databook MCP tool against a live server and fail on any exception.

This is the guard for the class of regression where a tool's SQL drifts out of
sync with the database schema (renamed columns, text-typed numerics, etc.). Such
errors only surface against a *populated* instance, so run this against prod (or
any instance with real data), NOT the empty CI stack:

    python3 scripts/mcp-tool-audit.py                       # defaults to prod
    MCP_URL=https://api.databook.nyc/mcp python3 scripts/mcp-tool-audit.py

Exit code 0 = every tool executed without an exception; 1 = one or more threw;
2 = could not complete the MCP handshake. Uses only the Python stdlib.
"""
import json
import os
import sys
import urllib.request

MCP_URL = os.environ.get("MCP_URL", "https://api.databook.nyc/mcp")

# Real count is 40 (test_mcp_docs_sync.py pins it against the docs page). This
# floor exists only to make an empty/truncated list fail instead of passing.
MIN_TOOLS = 35
# ⚠⚠ BROWSER-SHAPED, BUT IT MUST IDENTIFY ITSELF. The plain browser UA this
# used to send made the audit INDISTINGUISHABLE FROM A REAL USER in the MCP
# log — 40 tool calls a day, every day, landing in the same place as genuine
# sessions, so usage analytics would have read our own health check as user
# demand. `AUDIT_UA_TOKEN` is what scripts/usage-rollup.sh excludes on.
#
# ⚠ The browser shape is KEPT rather than replaced. The original comment said
# api.databook.nyc "403s obviously-automated agents"; re-tested 2026-08-21 and
# that is NOT true today (a bare `databook-mcp-audit/1` gets 200 — the Managed
# Challenge on this hostname is disabled). But the rule could be re-enabled, and
# an audit that starts 403ing is a red monitor manufactured for the sake of a
# tidier string. Appending the token costs nothing and survives either world.
AUDIT_UA_TOKEN = "databook-mcp-audit/1"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 " + AUDIT_UA_TOKEN)

# Representative arguments per tool. Detail tools use IDs that may not resolve;
# a graceful "not found" counts as working — only a raised exception is a failure.
ARGS = {
    "get_database_overview": {},
    "search_organizations": {"query_text": "parks", "limit": 2},
    "get_organization_profile": {"org_id": 1},
    "get_organization_notices": {"org_id": 1, "limit": 2},
    "search_civil_titles": {"query_text": "engineer", "limit": 2},
    "get_title_positions": {"job_code": "10001", "limit": 2},
    "search_notices": {"query_text": "hearing", "limit": 2},
    "get_notice_stats": {},
    "get_recent_events": {"limit": 2},
    "search_capital_projects": {"query_text": "park", "limit": 2},
    "get_project_details": {"project_id": "125THPDIM"},
    "get_agency_projects": {"agency": "Parks", "limit": 2},
    "get_project_milestones": {"days_back": 3650, "days_forward": 3650, "limit": 4},
    "search_people": {"query_text": "smith", "limit": 2},
    "search_vendors": {"query_text": "tech", "limit": 2},
    "get_vendor_profile": {"vendor_id": "1"},
    "search_contracts": {"query_text": "software", "limit": 2},
    "get_contract_details": {"contract_id": "1"},
    "get_contract_stats": {},
    "search_solicitations": {"query_text": "construction", "limit": 2},
    "get_solicitation_details": {"epin": "06923Y0146"},
    "get_open_solicitations": {"limit": 2},
    "search_jobs": {"query_text": "engineer", "limit": 2},
    "get_job_details": {"job_id": "784250"},
    "get_salary_stats": {"agency": "Police"},
    "get_top_salaries": {"limit": 3},
    "search_facilities": {"query_text": "library", "limit": 2},
    "get_facility_types": {},
    "search_schools": {"query_text": "academy", "limit": 2},
    "get_school_stats": {},
    "get_agency_budget": {"agency": "Police"},
    "compare_agency_budgets": {"limit": 3},
    "search_legislation": {"query_text": "housing", "limit": 2},
    "get_legislation_detail": {"intro_number": "Int 0025-2024"},
    "get_council_member": {"slug": "lincoln-restler"},
    "get_recent_legislation": {"limit": 2},
    "get_local_laws": {"year": 2024},
    "get_upcoming_hearings": {"limit": 2},
    "get_hearing_detail": {"event_id": "1"},
    "get_hearing_briefing": {"event_id": "1"},
}


def _post(payload, sid=None, want_headers=False):
    body = json.dumps(payload).encode()
    headers = {
        "User-Agent": UA,
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if sid:
        headers["mcp-session-id"] = sid
    req = urllib.request.Request(MCP_URL, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read().decode()
        hdrs = dict(resp.headers)
    # Response is either JSON or SSE ("data: {...}"). Grab the first JSON payload.
    parsed = None
    for line in raw.splitlines():
        if line.startswith("data: "):
            parsed = json.loads(line[6:])
            break
    if parsed is None and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = None
    return (parsed, hdrs) if want_headers else parsed


def main():
    # Handshake
    init, hdrs = _post(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                    "clientInfo": {"name": "tool-audit", "version": "1"}}},
        want_headers=True)
    sid = hdrs.get("mcp-session-id") or hdrs.get("Mcp-Session-Id")
    if not init or not sid:
        print(f"FATAL: MCP handshake failed against {MCP_URL}", file=sys.stderr)
        return 2
    _post({"jsonrpc": "2.0", "method": "notifications/initialized"}, sid=sid)

    listed = _post({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}, sid=sid)
    tools = [t["name"] for t in listed["result"]["tools"]]

    # ⚠⚠ A FLOOR, BECAUSE AN EMPTY TOOL LIST USED TO PASS. Without this, a server
    # that handshakes but registers nothing walks the loop zero times, collects no
    # exceptions and prints "PASS: all 0 tools executed without exceptions" —
    # exit 0. That is the same defect as the guard that scanned zero files: an
    # outcome of zero is indistinguishable from never having run, and it matters
    # more now this audit is on a schedule and nobody reads a green run.
    # The exact count is pinned against the docs by test_mcp_docs_sync.py; this is
    # only here to catch a truncated or empty registration, so it sits well below
    # the real 40 rather than tracking it.
    if len(tools) < MIN_TOOLS:
        print(f"FAIL: server advertised only {len(tools)} tools (floor {MIN_TOOLS}). "
              "An empty or truncated tool list is a broken server, not a pass.",
              file=sys.stderr)
        return 3

    print(f"Auditing {len(tools)} tools against {MCP_URL}\n")
    broken = []
    missing_args = []
    for name in tools:
        if name not in ARGS:
            missing_args.append(name)
        r = _post({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                   "params": {"name": name, "arguments": ARGS.get(name, {})}}, sid=sid)
        res = (r or {}).get("result", {})
        text = ""
        if res.get("content"):
            text = res["content"][0].get("text", "")
        # An exception is reported as isError + text starting "Error executing tool".
        is_exc = res.get("isError") and text.startswith("Error executing tool")
        flag = "XX EXCEPTION" if is_exc else "   ok"
        print(f"{flag:15} {name:32} {text[:80].replace(chr(10), ' ')}")
        if is_exc:
            broken.append((name, text))

    print()
    if missing_args:
        print(f"WARNING: no test args for {len(missing_args)} tool(s) "
              f"(called with empty args): {', '.join(missing_args)}")
    if broken:
        print(f"FAIL: {len(broken)}/{len(tools)} tools threw exceptions:")
        for name, text in broken:
            print(f"  - {name}: {text[:120]}")
        return 1
    print(f"PASS: all {len(tools)} tools executed without exceptions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
