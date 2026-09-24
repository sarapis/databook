"""A community district's borough must agree with the project's own borough.

⚠⚠ THE DEFECT THIS EXISTS FOR. `capital_project_districts.dist` is DCP's
`BoroCD` — that is what the geometry half joins against, what `cd.geojson`
publishes and what `/d/cd-{id}` serves. The retired series writes the same SHAPE
in a DIFFERENT numbering, and the builder took its tokens verbatim, so
**2,947 projects were recorded in the wrong borough's community district** and
listed on that district's public page. The worked example is `826HED-545`, the
Croton Filtration Plant: `BORO = BRONX`, `COMMUNITY_BOARD = 107 108`, listed on
Manhattan's Upper West Side beside genuine Riverside Park projects.

⭐ THE CHECK IS AGAINST A COLUMN THE BUILDER NEVER READS. `capital_projects.
borough` comes from the spine, not from the crosswalk, so agreement between them
is real evidence rather than a restatement. Measured across the fix:

    community_board_text   3,917 agree / 4,948 disagree  ->  3,493 / 2
    geometry               3,899 agree /   149 disagree  ->  unchanged

⚠ The geometry disagreements are NOT a defect and must not be "fixed" to zero:
a project's polygon can cross a borough line, and the spine's own `borough` is
a single value. They are pinned as a ceiling so they cannot grow.

⚠ CITYWIDE and blank boroughs are excluded — they are not a borough claim.
"""
import os
import subprocess
import sys

# ⚠ DCP's numbering, which is what `dist` is. NOT the retired series' — that is
# the whole point, and writing it here would make the check agree with the bug.
DCP = {'1': 'MANHATTAN', '2': 'BRONX', '3': 'BROOKLYN', '4': 'QUEENS', '5': 'STATEN ISLAND'}

# What the two methods are allowed to disagree on.
LIMITS = {'community_board_text': 5, 'geometry': 160}

SQL = """
WITH m(code, boro) AS (VALUES %s)
SELECT d.method,
       count(*) FILTER (WHERE upper(replace(p.borough,'RICHMOND','STATEN ISLAND')) = m.boro),
       count(*) FILTER (WHERE upper(replace(p.borough,'RICHMOND','STATEN ISLAND')) <> m.boro)
FROM capital_project_districts d
JOIN capital_projects p USING (agency_key, fms_id)
JOIN m ON m.code = left(d.dist, 1)
WHERE d.dist_type = 'cd'
  AND coalesce(trim(p.borough), '') <> ''
  AND upper(trim(p.borough)) <> 'CITYWIDE'
GROUP BY 1 ORDER BY 1
""" % ', '.join("('%s','%s')" % kv for kv in DCP.items())


def psql(sql):
    """Result rows, one string each.

    ⚠ It used to drop every line without a `|`, which silently discarded
    SINGLE-COLUMN results — so the non-vacuity probe below read 0 distinct
    borough digits and failed on a correct crosswalk. A helper that filters on
    the shape of the answer it expects is the probe reporting a defect that is
    not there, which is the mistake this whole check exists to catch.
    """
    out = subprocess.run(
        ['docker', 'compose', 'exec', '-T', 'postgres',
         'psql', '-U', 'postgres', '-d', 'databook', '-A', '-F|', '-t', '-c', sql],
        capture_output=True, text=True,
        cwd=os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', '..'))
    if out.returncode != 0:
        raise SystemExit('psql failed: %s' % (out.stderr or '')[-300:])
    return [l.strip() for l in out.stdout.splitlines() if l.strip()]


rows = psql(SQL)
ok = True
seen = set()
for line in rows:
    method, agree, disagree = line.split('|')
    agree, disagree = int(agree), int(disagree)
    seen.add(method)
    cap = LIMITS.get(method)
    bad = cap is None or disagree > cap
    print(f'  {method:<22} {agree:>6,} agree  {disagree:>5,} disagree'
          f'{"   <-- FAIL (cap %s)" % cap if bad else ""}')
    if bad:
        ok = False

# ⚠⚠ NON-VACUITY. A crosswalk that lost its text half would report one method
# with zero disagreements and pass — the shape of every check this repo has had
# to fix. Both methods must be present, and both must have found real rows.
missing = sorted(set(LIMITS) - seen)
if missing:
    print(f'FAIL: no rows at all for {missing} — the crosswalk is missing a method')
    ok = False

# And the boroughs must actually be exercised: a `dist` column of all-4s would
# agree trivially with a spine of all-Queens projects.
boros = psql("SELECT count(DISTINCT left(dist,1)) FROM capital_project_districts "
             "WHERE dist_type='cd'")
n = int(boros[0]) if boros and boros[0].isdigit() else 0
print(f'  distinct borough digits in the crosswalk: {n}')
if n < 5:
    print('FAIL: not every borough is represented, so this check is not exercised')
    ok = False

print('DISTRICT BOROUGHS OK' if ok else 'DISTRICT BOROUGHS FAILED')
sys.exit(0 if ok else 1)
