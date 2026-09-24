"""Guard for the docker-run env pass-through trap in the host refresh scripts.

⚠⚠ THE BUG THIS EXISTS FOR, measured 2026-08-25. `docker run -e POSTGRES_HOST`
with no `=VALUE` is a PASS-THROUGH: it forwards the variable only if it is set
in the invoking shell — and POSTGRES_HOST/USER/DB live in docker-compose.yml's
`environment:` block, which no host shell (least of all cron's `env -i`-like
environment) ever sees. So `oce-refresh.sh`'s contract-timeline precompute
passed NOTHING, dbcreds fell back to localhost inside the isolated container,
and the FIRST scheduled run of #272's precompute died on
`[Errno 111] Connect call failed ('127.0.0.1', 5432)` — while the flags read
perfectly to a human, and the failure surfaced only because someone read the
log two days later.

The working pattern (dos-crosswalk-refresh.sh had it all along) is to export
the live api container's own values first:

    eval "$(docker inspect databook-api ... | grep -E '^POSTGRES_...' ...)"

so the values cannot drift from compose. This guard requires that preamble in
any script that uses the bare-`-e` form, and asserts it scanned a real number
of scripts so it cannot pass vacuously (the zero-files-scanner rule).
"""
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
SCRIPTS = os.path.join(ROOT, 'scripts')


def test_every_bare_env_passthrough_has_the_export_preamble():
    scanned = 0
    offenders = []
    for name in sorted(os.listdir(SCRIPTS)):
        if not name.endswith('.sh'):
            continue
        path = os.path.join(SCRIPTS, name)
        with open(path, encoding='utf-8', errors='replace') as fh:
            src = fh.read()
        scanned += 1
        # The bare pass-through form: `-e POSTGRES_HOST` not followed by `=`.
        # ⚠ Comments are stripped first, or this guard fires on the prose in
        # oce-refresh.sh that EXPLAINS the trap — the own-prose failure this
        # repo has now paid for ten times.
        code = '\n'.join(l for l in src.split('\n')
                         if not l.lstrip().startswith('#'))
        for m in re.finditer(r'-e\s+POSTGRES_(HOST|USER|DB)(?!=)', code):
            before = code[:m.start()]
            if 'docker inspect databook-api' not in before \
                    or 'export' not in before:
                offenders.append(f"{name}: bare -e POSTGRES_{m.group(1)} with "
                                 f"no docker-inspect export preamble above it")
                break
    assert scanned > 10, f"only {scanned} shell scripts scanned — the guard is not looking"
    assert not offenders, (
        "these pass POSTGRES_* to docker run as a pass-through that the host "
        "shell cannot satisfy (the values live only in compose):\n  "
        + "\n  ".join(offenders))


def test_a_failed_precompute_raises_a_sentry_event():
    """The `|| log` guard is right (a builder hiccup must not roll back a good
    lake) — but a WARN that lands only in a log file recurs silently every
    Sunday. The failure branch must also call sentry_event."""
    with open(os.path.join(SCRIPTS, 'oce-refresh.sh'), encoding='utf-8') as fh:
        src = fh.read()
    i = src.find('contract timeline precompute FAILED')
    assert i > 0, "the precompute failure branch is gone — re-anchor this guard"
    tail = src[i:i + 400]
    assert 'sentry_event' in tail, (
        "the precompute failure branch no longer raises a Sentry event, so a "
        "weekly-recurring failure is visible only to someone reading the log")
