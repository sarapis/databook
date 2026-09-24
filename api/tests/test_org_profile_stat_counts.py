"""Guards for the org profile's dataset counts — the headline figure it publishes.

⚠⚠ THE ORG PROFILE SAYS "This agency's profile has N records from M datasets",
and BOTH numbers are accumulated client-side, one increment per successful
`/get/orgs/stats-reg/` response. A rejected request therefore does not render an
error — it silently UNDERCOUNTS a published figure, and two visitors loading the
same page can see different totals depending on network timing.

Measured 2026-08-31 from a 3.7-day nginx window:

    2,916  429s on /get/orgs/stats-reg/{id}/{dataset}   ← largest source on the site
      165  distinct IPs affected
       27  requests fired per page load — a FIXED number, not a function of
           agency size (136 of 216 orgs were seen requesting all 27)
       20  the `api` zone's burst

So 7+ were rejected on EVERY load, for every visitor, on every agency. Two fixes,
and these guards pin both: nginx stops causing it, and the view stops hiding it.
"""
import io
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
VIEW = os.path.join(ROOT, 'app', 'resources', 'views', 'organization.blade.php')
JS = os.path.join(ROOT, 'app', 'public', 'js', 'script.js')
NGINX = os.path.join(ROOT, 'nginx', 'conf.d')


def _read(p):
    with io.open(p, encoding='utf-8') as fh:
        return fh.read()


def _code(js):
    """`js` with // line comments removed.

    ⚠⚠ THE ELEVENTH TIME A GUARD IN THIS REPO FIRED ON ITS OWN PROSE. The
    comment inside loadTableStat QUOTES `resp['data'][0]['count']` in order to
    explain the trap, and it necessarily sits ABOVE the check it is explaining —
    so an index comparison over the raw text reported the exact defect the code
    had just fixed. Read the code, never the commentary.
    """
    return re.sub(r'//[^\n]*', '', js)


def _fn(src, name):
    """The body of a `function name(...) { ... }`, by brace balance."""
    i = src.index('function ' + name)
    depth, out, started = 0, [], False
    for ch in src[i:]:
        out.append(ch)
        if ch == '{':
            depth += 1
            started = True
        elif ch == '}':
            depth -= 1
            if started and depth == 0:
                break
    return ''.join(out)


def test_stats_reg_has_a_burst_that_clears_one_whole_page_load():
    """⚠ The page fires a FIXED 27, so any burst below that rejects some of them
    every single time. Asserted against the measured number, not a round one."""
    ssl = _read(os.path.join(NGINX, 'ssl.conf'))
    i = ssl.find('location /get/orgs/stats-reg/')
    assert i > 0, (
        'stats-reg has no dedicated location block; it falls back to `api` '
        "(burst=20), which cannot pass one page load's 27 requests")
    block = ssl[i:ssl.index('}', i)]
    m = re.search(r'limit_req\s+zone=(\w+)\s+burst=(\d+)', block)
    assert m, 'the stats-reg block has no limit_req'
    zone, burst = m.group(1), int(m.group(2))
    assert zone != 'api', (
        'stats-reg shares the `api` zone again — the point of a separate zone '
        'is that widening this burst does not widen the general API limit')
    assert burst >= 27, (
        f'burst={burst} is below the 27 requests one org profile load fires, so '
        'some are rejected on every load')

    sec = _read(os.path.join(NGINX, 'security.conf'))
    m = re.search(r'zone=%s:\d+m\s+rate=(\d+)r/s' % zone, sec)
    assert m, f'zone {zone} is used but never declared in security.conf'
    assert int(m.group(1)) <= 10, (
        f'the {zone} RATE was raised to {m.group(1)}r/s. Only the BURST should '
        'move: the burst tolerates one legitimate page load, the rate is what '
        'caps sustained crawling.')


def test_a_failed_stat_is_not_counted_as_an_empty_dataset():
    """⚠⚠ The pre-fix code read `resp['data'][0]['count']` FIRST, which throws a
    TypeError on the empty array a failure produces — so the error path did not
    merely mis-render, it threw, leaving the row in place, the count blank and
    both totals never incremented. The failure check must come first."""
    body = _code(_fn(_read(VIEW), 'loadTableStat'))
    assert 'statUnavailable' in body, (
        'loadTableStat no longer reports an unavailable count; a throttled or '
        'failed dataset would read as one with no records')
    err = body.index("resp['error']")
    idx = body.index("resp['data'][0]")
    assert err < idx, (
        "loadTableStat indexes resp['data'][0] before checking resp['error'] — "
        'that throws a TypeError on a failed request, which is how this hid')


def test_the_totals_disclose_when_they_are_incomplete():
    """⚠ A total that silently drops rows reads as the whole inventory — the
    same rule the renewal calendar's disclosed buckets follow."""
    src = _read(VIEW)
    assert 'id="stats_incomplete"' in src, (
        'the totals sentence has no element to disclose an incomplete count')
    body = _fn(src, 'statUnavailable')
    assert '#stats_incomplete' in body and 'incomplete' in body, (
        'statUnavailable no longer tells the reader the totals are incomplete')
    assert 'statLoadFailures++' in body, (
        'the failure count is not incremented, so the disclosure cannot be '
        'accurate about how many datasets are missing')


def test_fapireq_carries_the_status_so_a_failure_is_distinguishable():
    """⚠ Without it, a 429 we caused and a genuinely empty result are the same
    value to every caller — this repo's oldest defect, at the browser."""
    body = _fn(_read(JS), 'fapireq')
    assert "'status'" in body and 'jqXHR.status' in body, (
        'fapireq no longer carries the HTTP status, so a caller cannot tell a '
        'failed request from an empty one')
    assert "'error'" in body, 'fapireq no longer reports an error at all'
