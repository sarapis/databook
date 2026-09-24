"""php-fpm logs every request's URI and duration, and flags slow ones.

Without this, the 2026-09-23 question "which requests hold the 15 workers?" had
no answer: nginx logs no timings, and fpm's default access line is
`"GET /index.php" 200`. See app/docker/php-fpm-timing.conf.
"""

import io
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
CONF = os.path.join(ROOT, 'app', 'docker', 'php-fpm-timing.conf')


def _read(p):
    with io.open(p, encoding='utf-8') as fh:
        return fh.read()


def _settings():
    out = {}
    for line in _read(CONF).splitlines():
        line = line.strip()
        if line and not line.startswith(';') and '=' in line:
            k, v = line.split('=', 1)
            out[k.strip()] = v.strip()
    return out


def test_the_dockerfile_installs_the_timing_conf_after_www_conf():
    df = '\n'.join(l for l in _read(os.path.join(ROOT, 'app', 'Dockerfile')).splitlines()
                   if not l.lstrip().startswith('#'))
    # zz- sorts after www.conf and zz-docker.conf, so these settings win.
    assert 'COPY docker/php-fpm-timing.conf /usr/local/etc/php-fpm.d/zz-timing.conf' in df


def test_the_access_line_names_the_page_and_the_duration():
    s = _settings()
    fmt = s.get('access.format', '')
    assert '%{REQUEST_URI}e' in fmt, 'without REQUEST_URI every line reads /index.php'
    assert re.search(r'%\{mili\}d', fmt), 'the duration is the point of this file'
    assert '[www]' in _read(CONF), 'pool settings outside [www] are ignored'


def test_slow_requests_are_flagged_below_the_api_timeout():
    s = _settings()
    t = s.get('request_slowlog_timeout', '')
    m = re.fullmatch(r'(\d+)s', t)
    assert m and 1 <= int(m.group(1)) < 5, (
        f'request_slowlog_timeout={t!r}: must fire below the 5s API timeout, '
        'or a request stuck on the API is never flagged')
    assert s.get('slowlog'), 'a timeout with nowhere to log is inert'
