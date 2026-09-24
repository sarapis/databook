"""First-party assets must bust their cache on filemtime, not a constant.

⚠⚠ THE OUTAGE THIS EXISTS TO PREVENT, AND IT HAPPENED ON PROD 2026-09-09.
`layout.blade.php` emitted `/js/script.js?v=2` — a hardcoded version. Editing
`script.js` changes the file but NOT the URL, so every browser and edge cache
holding a copy keeps serving the OLD script under the same key.

#385 shipped a `/schools` fix whose Blade calls `schoolStatTiles()`, a function
added in the same change to `script.js`. The Blade is server-rendered so it
updated instantly; the script did not. The live page therefore threw

    schoolStatTiles is not defined

which aborted the handler that hydrates the stat tiles and draws the map — so
`/schools` went from 2,184 map markers and six populated tiles to **zero and
six blank ones**, on a public page, while every check we had was green:
prod-smoke 7/7, CI green, the api healthy, the file correctly deployed at the
origin.

⭐ **The tell, and it is worth knowing.** The origin was serving the NEW file all
along — only the versioned URL was stale:

    GET /js/script.js?v=2          -> no schoolStatTiles   (what the page asks for)
    GET /js/script.js?cachebust=N  -> has schoolStatTiles  (what is deployed)

So "is it deployed?" and "is it reaching the browser?" are different questions,
and only the second one matters. Every other first-party asset in this layout
already busted on filemtime; `script.js` was the one that did not.
"""
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
LAYOUT = os.path.join(ROOT, 'app', 'resources', 'views', 'layout.blade.php')


def _read(path):
    with open(path, encoding='utf-8') as fh:
        return fh.read()


def _blade_code_only(text):
    """⚠ Strip Blade comments first. The comment in the layout EXPLAINING this
    trap contains the literal `?v=2`, so a raw scan fires on its own prose —
    the own-prose failure this repo has now paid for nineteen times."""
    return re.sub(r'\{\{--.*?--\}\}', '', text, flags=re.S)


def test_script_js_busts_its_cache_on_filemtime():
    """⚠ Asserts the TAG THE PAGE EMITS, not that the word appears in the file."""
    layout = _blade_code_only(_read(LAYOUT))
    tags = [l for l in layout.splitlines() if 'js/script.js' in l]
    assert tags, 'layout.blade.php no longer references js/script.js'
    for tag in tags:
        assert 'filemtime' in tag, (
            'script.js must be cache-busted with filemtime, or an edit never '
            'reaches a cached browser and the fix silently does not ship; '
            'found: ' + tag.strip())


def test_no_first_party_asset_uses_a_constant_version():
    """⚠ Scan for the BANNED PATTERN, not for the one site we know about.

    `?v=<digits>` on a local path is the shape that bit us. An external CDN URL
    is somebody else's cache key and is out of scope.
    """
    layout = _blade_code_only(_read(LAYOUT))
    offenders = []
    for line_no, line in enumerate(layout.splitlines(), 1):
        for m in re.finditer(r'src="(/[^"]+?)\?v=(\d+)"', line):
            offenders.append(f'{line_no}: {m.group(1)}?v={m.group(2)}')
    assert not offenders, (
        'these first-party assets carry a CONSTANT version, so editing them '
        'never reaches a cached browser:\n  ' + '\n  '.join(offenders))
