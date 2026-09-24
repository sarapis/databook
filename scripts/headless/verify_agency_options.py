"""Every agency option's count is exactly what its filter returns — and the map
agrees with the list.

⚠⚠ THE RULE HAS TWO SQL TEXTS AND THEY CANNOT BE PINNED BY LOOKING ALIKE. The
option list resolves each ROW's agency through a `voc` CTE; the filter resolves
the CALLER's value through one uncorrelated subquery (the per-row form measured
1,165ms against this one's 4.9ms). Two spellings of one rule is the defect this
repo records over and over, so the guard is BEHAVIOURAL: for every option the
list offers, ask the list endpoint for that option and demand the same number.

⚠ And the MAP is asked too. `/get/capital/geojson` shares `_list_filters`, so a
divergence there would draw pins for projects the list excludes — the defect
measured at 12,464 listed against 4,560 drawn under a legend reading 17,024.
"""
import json
import sys
import urllib.parse
import urllib.request

API = 'http://localhost:8581'


def get(path):
    with urllib.request.urlopen(API + path, timeout=60) as r:
        return json.load(r)


opts = get('/get/capital/projects/filters')['agencies']
total = sum(o['n'] for o in opts)
allp = get('/get/capital/projects?per_page=1')['total']
print(f'{len(opts)} agency options, counts sum to {total:,} against {allp:,} projects')

ok = total == allp
if not ok:
    print('  FAIL: the options do not partition the spine — an agency is either '
          'split across two options or counted twice')

for o in opts:
    q = urllib.parse.quote(o['value'])
    got = get(f'/get/capital/projects?per_page=1&agency={q}')['total']
    mapped = get(f'/get/capital/geojson?agency={q}')['coverage']['matching_filters']
    flag = '' if got == o['n'] else '   <-- FAIL'
    if got != o['n']:
        ok = False
    if mapped != got:
        ok = False
        flag += ' MAP DISAGREES (%d)' % mapped
    print(f"  {o['value']:<7} option {o['n']:>6,}  list {got:>6,}  map {mapped:>6,}{flag}")

# ⚠ NON-VACUITY. An empty option list would sum to 0 == 0 and print nothing,
# which is this repo's oldest defect wearing an agency hat.
if len(opts) < 20:
    print('FAIL: only %d options — the vocabulary is truncated' % len(opts))
    ok = False

# ⚠ A legacy `?agency=846` link must still resolve to something, because the
# dropdown used to offer it. It now names a subset of Parks rather than an
# option, and that is the backward-compatible behaviour, not a match failure.
legacy = get('/get/capital/projects?per_page=1&agency=846')['total']
print(f'  legacy ?agency=846 still resolves: {legacy:,} projects')
if legacy <= 0:
    print('FAIL: an old agency link stopped resolving')
    ok = False

print('AGENCY OPTIONS OK' if ok else 'AGENCY OPTIONS FAILED')
sys.exit(0 if ok else 1)
