"""The crawler bounce on /research/digital-reform/contracts?<query>.

⚠⚠ 83% OF php-fpm WORKER TIME WAS ONE URL SHAPE. The per-request fpm timing
log (#425) measured /research/digital-reform/contracts WITH a query string at
29,753 requests / 12.7h, median 947ms. nginx over 24h: 67,715 such requests,
Referer = the bare origin 55,516, none 12,199, **a real databook.nyc page 0**.
A reader changing a sort/page/filter clicks a link ON a databook.nyc page and
the browser sends that page's full path, so a query-string request there with
no same-site PATH Referer is 302'd to the bare page.

These are behavioural where they can be: the two map regexes are pulled out of
security.conf and APPLIED to the Referers and keys that were actually seen,
rather than asserting the text looks right.
"""
import io
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
NGINX = os.path.join(ROOT, 'nginx', 'conf.d')
BARE = '/research/digital-reform/contracts'


def _read(name):
    with io.open(os.path.join(NGINX, name), encoding='utf-8') as fh:
        return fh.read()


def _map(var):
    """{pattern_or_literal: value} and default for `map ... $var { ... }`."""
    sec = _read('security.conf')
    m = re.search(r'^map[ \t]+([^\n]+?)[ \t]+\$' + re.escape(var) + r'\s*\{(.*?)^\}',
                  sec, re.M | re.S)
    assert m, f'security.conf declares no map for ${var}'
    source, body = m.group(1), m.group(2)
    entries, default = [], None
    for line in body.splitlines():
        # ⚠ Not split('#'): the Referer regex itself contains `[^?#]`.
        line = line.strip().rstrip(';').strip()
        if not line or line.startswith('#'):
            continue
        key, _, val = line.rpartition(' ')
        key = key.strip().strip('"')
        val = val.strip().strip('"')
        if key == 'default':
            default = val
        else:
            assert key.startswith('~'), f'${var}: expected regex entries, got {key!r}'
            entries.append((re.compile(key.lstrip('~*').lstrip('~')), val))
    assert default in ('0', ''), f'${var} must default to "let the request through"'
    assert entries, f'${var} has no entries — it can never fire'
    return source.strip('"'), entries


def _eval(var, value):
    _, entries = _map(var)
    for rx, val in entries:
        if rx.search(value):
            return val
    return '0' if var == 'dr_referer_is_page' else ''


def test_only_a_real_same_site_page_counts_as_a_referer():
    page = lambda r: _eval('dr_referer_is_page', r)
    # Seen from real readers in the prod log.
    for ok in ('https://databook.nyc/research/digital-reform',
               'https://www.databook.nyc/procurement/vendor/1647619',
               'https://databook.nyc/research/digital-reform/products/planview',
               'https://databook.nyc/research/digital-reform?contract_page=2#x'):
        assert page(ok) == '1', f'a real page Referer was rejected: {ok}'
    # ⚠ The crawler's fake Referer IS the bare origin, both spellings.
    for bad in ('https://databook.nyc', 'https://databook.nyc/',
                'https://www.databook.nyc/', 'https://databook.nyc/?x=1',
                '', '-', 'https://databook.nyc.evil.com/research/x',
                'https://evil.example/research/digital-reform/contracts'):
        assert page(bad) == '0', f'{bad!r} passed as a same-site page Referer'


def test_the_bounce_fires_only_on_the_contracts_urls_with_a_query_and_no_page_referer():
    source, _ = _map('dr_bounce_to')
    assert source == '$uri|$dr_referer_is_page|$args', (
        f'the bounce map is keyed on {source!r}; the regex below assumes '
        '"$uri|<0/1>|$args"')
    to = lambda uri, ref, args: _eval('dr_bounce_to', f'{uri}|{ref}|{args}')
    q = 'contract_page=3&contract_sort=vendor'
    queue = BARE + '/review'
    assert to(BARE, '0', q) == BARE
    assert to(BARE + '/', '0', q) == BARE
    # The Renewal Review Queue (split out 2026-09-23) and its export bounce to
    # the BARE queue page, not to Contracts.
    assert to(queue, '0', 'expiring_flag=underused') == queue
    assert to(queue + '/export', '0', 'expiring_year=2027') == queue
    # ⚠ The bare pages must never bounce, or the redirect target loops.
    for bare in (BARE, queue, queue + '/export'):
        assert to(bare, '0', '') == '', f'{bare} bounces with no query — a loop'
    assert to(BARE, '1', q) == '' and to(queue, '1', q) == '', \
        'a real reader clicking a sort or filter link bounced'
    # Scoped — /projects carries the same fake Referer, and that is a separate
    # decision.
    for other in ('/research/digital-reform', '/research/digital-reform/products',
                  BARE + 'x', queue + 'x', '/projects'):
        assert to(other, '0', q) == '', f'the bounce leaked onto {other}'


def _research_block(conf):
    text = _read(conf)
    i = text.find('location /research/ {')
    assert i >= 0, f'{conf} has no /research/ block'
    depth, out = 0, []
    for ch in text[i:]:
        out.append(ch)
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                break
    return ''.join(out)


def test_both_server_blocks_bounce_to_the_mapped_BARE_page():
    for conf in ('ssl.conf', 'app.conf'):
        block = _research_block(conf)
        m = re.search(r'if \(\$dr_bounce_to\)\s*\{\s*return\s+(\d+)\s+(\S+);', block)
        assert m, f'{conf}: /research/ does not act on $dr_bounce_to'
        assert m.group(1) == '302', f'{conf}: bounce is {m.group(1)}, expected 302'
        target = m.group(2)
        # ⚠ Carrying the query (or $request_uri) forward would redirect the
        # request to itself; the target is the map's bare page.
        assert target == 'https://$host$dr_bounce_to', (
            f'{conf}: bounce target {target!r} is not the mapped bare page')
        # The limiter stays: the bounce is spoofable, the cap is not.
        assert 'zone=research_total' in block
