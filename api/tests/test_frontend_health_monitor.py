"""The monitor that would have caught the 2026-08-31 site outage.

⚠⚠ WHY IT EXISTS. The whole site returned 504 for hours — 150-550 per minute,
peaking at 18,947 in one hour, in bursts since 28 August — and NOTHING ALERTED.
Every monitor was looking elsewhere:

    Sentry            watches the API, which was healthy the entire time
    healthchecks.io   watches CRONS; every cron ran fine
    prod-smoke.sh     the only thing that checks pages, and it is MANUAL
    lake-staleness    data freshness, unaffected

Everything green, site down. That is the permanently-red monitor inverted, and
worse: a red monitor is at least visible.
"""
import io
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
SRC = os.path.join(ROOT, 'scripts', 'frontend-health.sh')


def _src():
    with io.open(SRC, encoding='utf-8') as fh:
        return fh.read()


def _code():
    """The script with # comments stripped.

    ⚠ Its header explains the incident in detail and names the very things these
    guards search for. Reading the raw text would match the prose — the own-prose
    guard failure this repo has paid for eleven times.
    """
    return '\n'.join(re.sub(r'(?<!\$)#.*$', '', l) for l in _src().splitlines())


def test_the_monitor_exists_and_is_executable():
    assert os.path.exists(SRC), 'the frontend health monitor is gone'
    assert os.access(SRC, os.X_OK), 'the monitor is not executable, so cron cannot run it'


def test_it_probes_the_ORIGIN_not_the_edge():
    """⚠⚠ A Cloudflare edge HIT answers while the origin is dead — precisely the
    state this must catch. It must ask nginx directly with a Host header."""
    code = _code()
    assert '127.0.0.1' in code, 'the probe no longer targets the origin'
    assert 'Host: databook.nyc' in code, (
        'the probe does not send a Host header, so it cannot reach the right '
        'vhost at the origin')
    assert not re.search(r'curl[^\n]*https://databook\.nyc', code), (
        'the probe goes through Cloudflare, where a cached HIT would answer '
        'while the origin is down — the exact failure being monitored')


def test_it_probes_a_CHEAP_page():
    """⚠ The failure mode is worker STARVATION, so the signal is a page that
    should be instant not being. Pointed at the expensive page it would measure
    that page's own cost and say nothing about whether the site is up."""
    code = _code()
    m = re.search(r'PROBE_PATH="\$\{PROBE_PATH:-([^}]*)\}"', code)
    assert m, 'PROBE_PATH is no longer configurable with a default'
    assert m.group(1).strip() in ('/', '/about'), (
        f'the default probe path is {m.group(1)!r}; it must be a cheap page, '
        'not one whose own cost is what saturates the workers')
    assert 'research' not in m.group(1), 'the probe points at the expensive page'


def test_an_unreadable_log_fails_rather_than_reading_as_quiet():
    """⚠⚠ THIS REPO'S OLDEST DEFECT. nginx serves constant traffic, so zero
    parsed request lines means the log format changed or the container was
    recreated — a BROKEN MEASUREMENT, not a quiet period. Verified on the box:
    ROOT=/nonexistent exits 1."""
    code = _code()
    assert re.search(r'if \[ "\$lines" -eq 0 \]', code), (
        'the monitor no longer refuses when it parsed no request lines, so a '
        'log it cannot read would report a healthy site')


def test_it_checks_the_5xx_RATE_as_well_as_a_single_probe():
    """⚠ A single 200 does not mean healthy — 40% of requests were still
    succeeding at the worst moment, so the probe can get lucky."""
    code = _code()
    assert 'MAX_5XX_PCT' in code and 'pct' in code, (
        'the 5xx rate check is gone; a lucky 200 would report the site healthy '
        'while a large share of real traffic fails')
    assert 'MIN_SAMPLE' in code, (
        'there is no sample floor, so a quiet window could produce a scary '
        'percentage from three requests')


def test_a_death_before_reporting_still_reports():
    """⚠ `set -e` is not enough: the likeliest death is `docker compose logs`
    dying mid-pipe, which never reaches a fail() call. dos-crosswalk-refresh
    carries an EXIT trap for the same reason."""
    code = _code()
    assert 'trap ' in code and 'EXIT' in code, 'no EXIT trap; a mid-script death would be silent'
    assert 'REPORTED' in code, (
        'nothing guards against double-reporting, so a real fail() and the trap '
        'would both fire')


def test_the_healthchecks_ping_is_a_NO_OP_when_unset():
    """⚠ Rollout order, and this repo has the scar: ship the pinging code as a
    no-op FIRST, create the check second, set the env var last. Creating a check
    for a script that cannot ping it manufactures a red monitor."""
    code = _code()
    assert 'HC_URL_FRONTEND' in code, 'the monitor cannot report to healthchecks'
    assert re.search(r'\[ -n "\$\{HC_URL_FRONTEND:-\}" \] \|\| return 0', code), (
        'the ping is not a no-op when HC_URL_FRONTEND is unset, so the monitor '
        'would fail before the check exists')


def test_it_sources_dotenv_so_cron_can_actually_ping():
    """⚠⚠ CRON HAS ALMOST NO ENVIRONMENT. Reading HC_URL_FRONTEND from the
    environment alone makes the ping a permanent no-op under cron — the check
    would be created, never pinged, and go down on its first missed schedule.
    A red monitor manufactured by omission.

    Caught by asking how the value would reach the script, not by reading it:
    every other monitor here sources .env (egress-check.sh line 56) and this one
    did not.
    """
    code = _code()
    assert re.search(r'\[ -f "\$ROOT/\.env" \] && \. "\$ROOT/\.env"', code), (
        'the monitor does not source .env, so HC_URL_FRONTEND will be unset '
        'under cron and the ping is a permanent no-op')
    src_lines = code.splitlines()
    dotenv = next(i for i, l in enumerate(src_lines) if '.env"' in l and '-f' in l)
    first_hc = next(i for i, l in enumerate(src_lines) if 'HC_URL_FRONTEND' in l)
    assert dotenv < first_hc, (
        '.env is sourced after HC_URL_FRONTEND is first read, so the value '
        'would still be empty when it matters')
