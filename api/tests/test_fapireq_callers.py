"""A `fapireq` caller may not dereference `resp.data[0]` without checking the row.

⚠⚠ THIS IS THE GUARD THAT WAS MISSING, AND ITS ABSENCE COST THE SAME FIX THREE
TIMES. `fapireq` hands back three shapes and only one carries a row:

    {data: rows}               the request answered, with or without rows
    {data: [], unexpected}     it answered in a shape we do not read
    {data: [], error, status}  we could not ask

`resp.data[0].<field>` throws `Cannot read properties of undefined` on every
shape whose `data` is empty — and that is NOT only the two failure shapes. It is
reachable on a HEALTHY 200: `/get/schools/schoolStats/{id}` returns `{rows: []}`
for a location code it cannot resolve (api/main.py `get_school_stats`). An
uncaught error there aborts the rest of the handler it fires in, so whatever the
page does next dies with it.

It was fixed on `/schools`, then found again VERBATIM in `distsection.blade.php`,
then found a THIRD time in `schoolSection.blade.php` — each time by someone
reading the page, never by a test. `test_fapireq_shape.py` guards `fapireq`
itself and the staleness of its comments; nothing looked at the CALLERS.

⭐ So this scans for the BANNED PATTERN rather than the three known sites — the
rule this repo already paid for with the pagination clamp, where a guard written
for three known sites found three more.

⚠ COMMENTS ARE STRIPPED FIRST. All three of those views now carry comments that
QUOTE `resp.data[0]` while explaining why it is forbidden, so a raw-text scan
fires on its own prose — this repo's most repeated guard defect.
⚠ And `//` is stripped only where it is not part of a URL: a dataset description
in these views contains `http://labs.council.nyc/...`, and a naive `//` strip
eats the rest of that line.
"""
import os
import re

HERE = os.path.dirname(os.path.realpath(__file__))
ROOT = os.path.realpath(os.path.join(HERE, '..', '..'))
VIEWS = os.path.join(ROOT, 'app', 'resources', 'views')

# `.data[0].field` or `.data[0]['field']` — the deref, not a length check.
BANNED = re.compile(r'\.data\s*\[\s*0\s*\]\s*[.\[]')


def _code(src):
    """Blade + JS comments removed, URLs preserved."""
    src = re.sub(r'\{\{--.*?--\}\}', '', src, flags=re.S)   # Blade
    src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)         # block
    # ⚠ `(?<!:)` keeps `http://…` intact; a bare `//` strip would eat the rest
    # of the line and could hide real code sitting after a URL in a string.
    src = re.sub(r'(?<!:)//[^\n]*', '', src)
    return src


def _views():
    out = []
    for dirpath, _dirs, files in os.walk(VIEWS):
        for fn in files:
            if fn.endswith('.blade.php'):
                out.append(os.path.join(dirpath, fn))
    return sorted(out)


def test_no_view_dereferences_a_fapireq_row_without_checking_it():
    views = _views()
    # non-vacuity: a guard that walks the tree must assert it LOOKED.
    assert len(views) > 80, 'only %d views scanned — the walk is nearly vacuous' % len(views)

    scanned_with_fapireq = 0
    offenders = []
    for path in views:
        with open(path, encoding='utf-8', errors='replace') as fh:
            code = _code(fh.read())
        if 'fapireq(' not in code:
            continue
        scanned_with_fapireq += 1
        for i, line in enumerate(code.splitlines(), 1):
            if BANNED.search(line):
                offenders.append('%s:%d  %s' % (os.path.relpath(path, ROOT), i, line.strip()[:90]))

    # non-vacuity again: if nothing calls fapireq, the scan proved nothing.
    assert scanned_with_fapireq > 10, (
        'only %d views call fapireq — the pattern scan is nearly vacuous'
        % scanned_with_fapireq)

    assert not offenders, (
        'a fapireq callback dereferences `data[0]` without checking the row. '
        'Two of fapireq\'s three shapes carry an empty `data`, and so does a '
        'healthy 200 from an endpoint that matched nothing — this throws and '
        'aborts the rest of the handler. Route it through a helper that checks '
        'the row (see `schoolStatTiles` in script.js):\n  ' + '\n  '.join(offenders))
