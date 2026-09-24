"""The MCP client label must preserve the audit's self-identifying token.

⚠⚠ WHY THIS EXISTS. `scripts/usage-rollup.sh` tells our own daily health check
apart from real users by looking for `AUDIT_UA_TOKEN` in the client label that
`api/mcp_server.py` records. The audit APPENDS that token to a browser-shaped
User-Agent (134 chars), and the label was capped at 60 — so the token was cut off
and the rollup classified our own 40-calls-a-day audit as `browser`, i.e. as user
demand. The defect the field exists to prevent, reintroduced by its own length
limit, and invisible until the rendered log line was read on prod.

⚠ Hermetic on purpose: it reads both values out of the SOURCE with ast rather
than importing, because mcp_server.py imports the `mcp` package (absent in the
unit-test environment) and conftest.py replaces `modules` with a MagicMock that
would satisfy almost any assertion.
"""
import ast
import io
import os

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
SERVER = os.path.join(ROOT, 'api/mcp_server.py')
AUDIT = os.path.join(ROOT, 'scripts/mcp-tool-audit.py')


def _read(p):
    with io.open(p, encoding='utf-8') as fh:
        return fh.read()


def _literal(path, name):
    """Value of a module-level assignment, evaluated without importing.

    ⚠ Handles string CONCATENATION, not just a bare literal: the audit builds its
    UA as `"Mozilla/... " + AUDIT_UA_TOKEN`, so `ast.literal_eval` alone raises —
    and a guard that cannot read the value it is meant to check would have to be
    weakened to pass, which is how a guard stops guarding.
    """
    tree = ast.parse(_read(path))
    env = {}

    def _eval(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id not in env:
                raise AssertionError(f'{name} in {path} refers to {node.id}, '
                                     'which is not a preceding module-level literal')
            return env[node.id]
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return _eval(node.left) + _eval(node.right)
        raise AssertionError(f'{name} in {path} is not a resolvable expression')

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for t in node.targets:
            if not isinstance(t, ast.Name):
                continue
            if t.id == name:
                return _eval(node.value)
            try:                      # remember simple constants for later use
                env[t.id] = _eval(node.value)
            except AssertionError:
                pass
    raise AssertionError(f'{name} not found as a module-level assignment in {path}')


def test_the_audit_token_survives_the_client_label_cap():
    """The whole mechanism in one assertion: cap the audit's real UA the way the
    server does, and the token must still be there."""
    cap = _literal(SERVER, '_CLIENT_MAX')
    ua = _literal(AUDIT, 'UA')
    token = _literal(AUDIT, 'AUDIT_UA_TOKEN')

    assert token in ua, (
        'the audit no longer identifies itself in its User-Agent — '
        'scripts/usage-rollup.sh can no longer exclude our own monitoring')
    assert token in ua[:cap], (
        f'_CLIENT_MAX={cap} truncates the audit token out of the client label '
        f'(UA is {len(ua)} chars, token ends at {ua.index(token) + len(token)}). '
        'The rollup would count our own health check as a real user.')


def test_the_rollup_excludes_on_that_same_token():
    """⚠ The label and the exclusion must name the SAME token. A rollup filtering
    a different string than the server records is worse than no filter — it reads
    as working while excluding nothing (the suffix-list defect)."""
    token = _literal(AUDIT, 'AUDIT_UA_TOKEN')
    rollup = _read(os.path.join(ROOT, 'scripts/usage-rollup.sh'))
    assert token in rollup, (
        f'scripts/usage-rollup.sh does not mention {token!r}, so its '
        'self:audit classification cannot match what the audit sends')
