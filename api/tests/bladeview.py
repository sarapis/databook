"""Read a Blade view the way it RENDERS: every `@include` expanded in place.

⚠ A guard that reads one file measures one file. The Digital Services pages
share their chart markup and JS through partials (the Overview's Contracts band
and the Contracts page render the SAME charts), so a guard asking "does the page
do X" must see the partial's text where the page includes it. Expanding IN PLACE,
not appending, keeps "is this statement before that one" questions meaningful.

Load by path (tests/ is a package, so a bare import fails):
    spec = importlib.util.spec_from_file_location('bladeview', <this file>)
"""
import os
import re

ROOT = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..'))
VIEWS = os.path.join(ROOT, 'app', 'resources', 'views')
_INC = re.compile(r"@include\(\s*['\"]([A-Za-z0-9_.\-]+)['\"][^)]*\)")


def path_of(name):
    return os.path.join(VIEWS, *name.split('.')) + '.blade.php'


def expand(path, _depth=0, skip=frozenset()):
    with open(path, encoding='utf-8') as fh:
        src = fh.read()
    if _depth > 3:
        return src

    def sub(m):
        if m.group(1) in skip:
            return ''
        p = path_of(m.group(1))
        # A partial that does not exist renders nothing here, exactly as a
        # missing include would fail loudly at runtime — the guard reading it
        # should not invent text either way.
        return expand(p, _depth + 1, skip) if os.path.exists(p) else m.group(0)
    return _INC.sub(sub, src)
