"""Build capital-project geometry and the district crosswalks.

⚠⚠ THE DEFECT THIS CLOSES. `/d/cc-…/projects` and `/d/sd-…/projects` have been
serving NOTHING, and not because those districts have no capital work:
`capitalprojects_cc_idx` and `capitalprojects_sd_idx` hold **0 rows**, and
**nothing in the repo creates any of the three crosswalks** — `cd_idx`'s 8,107
rows were loaded by hand at some forgotten point. An empty crosswalk and "this
council district has no capital projects" are byte-identical to the endpoint,
which is this repo's oldest failure shape.

⚠⚠ AND CPDB'S TABULAR PROJECTS CARRY NO GEOMETRY AT ALL. The only published
locations are the two CPDB geometry exports, registered 2026-09-05. Measured:
2,776 points + 1,784 polygons, disjoint, **4,560 distinct projects — 35.3% of
the current plan**, and all 4,560 join the spine on (agency, project id).

So coverage is bounded by what NYC maps, and every consumer must say so rather
than implying the rest are absent from the district.

⚠ THE SPATIAL JOIN IS DUCKDB, NOT POSTGIS. This Postgres has no PostGIS, and
`enrich_fire_data.py` already established the pattern: `st_read` the boundary
GeoJSON that `map.databook.nyc` already serves, attach Postgres, join, write
back. Reusing it means one spatial mechanism in the codebase, not two.

Usage:
    python build_capital_geography.py            # dry run
    python build_capital_geography.py --apply
"""
import argparse
import asyncio
import os
import sys

import asyncpg
import duckdb

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'modules'))

try:
    from modules import dbcreds
except ImportError:
    import dbcreds

try:
    from config import Config
except ImportError:
    Config = None

# The four boundary sets map.databook.nyc already serves, each carrying its
# identifier in `nameCol`. ⚠ `cd` is borough+district ('306'), matching the
# format the legacy crosswalk and the district pages already use — do not
# "normalise" it to a bare number.
BOUNDARIES = {
    'cd':  'https://map.databook.nyc/data/cd.geojson',
    'cc':  'https://map.databook.nyc/data/cc.geojson',
    'sd':  'https://map.databook.nyc/data/sd.geojson',
    'nta': 'https://map.databook.nyc/data/nta.geojson',
}

GEOM_TABLE = 'capital_project_geometry'
DIST_TABLE = 'capital_project_districts'


def _pg_dsn(cfg):
    """DSN for DuckDB's postgres attach.

    ⚠ EVERY LOOKUP IS `.get()`, NEVER A SUBSCRIPT. `test_dbcreds` bans reading a
    credential key by subscript across api/, and it caught the first draft of
    this function. The reason is not style: deleting `pwd:` from the box's
    env.yaml once raised `KeyError: 'pwd'` on four call sites for four days,
    and one of them swallowed it and served zeros. A missing key must degrade,
    not raise.
    """
    s = dbcreds.settings(cfg)
    user = s.get('user') or 'postgres'
    pwd = s.get('password') or ''
    host = s.get('host') or '127.0.0.1'
    port = s.get('port') or 5432
    name = s.get('database') or 'databook'
    return f"postgresql://{user}:{pwd}@{host}:{port}/{name}"


def build_geometry(db):
    """One row per (agency, project) with a published location.

    ⚠ The two exports are UNIONed, not joined: a project appears in at most one
    of them (measured — they are disjoint), and `geom_kind` records which.
    """
    db.execute(f"""
        CREATE OR REPLACE TABLE geom AS
        SELECT * FROM (
            SELECT lpad(trim(magency), 3, '0')      AS agency_key,
                   upper(trim(projectid))           AS fms_id,
                   trim(maprojid)                   AS maprojid,
                   'point'                          AS geom_kind,
                   geometry                         AS wkt
            FROM pg.cpdb_geometry_points
            WHERE geometry IS NOT NULL AND trim(geometry) <> ''
            UNION ALL
            SELECT lpad(trim(magency), 3, '0'),
                   upper(trim(projectid)),
                   trim(maprojid),
                   'polygon',
                   geometry
            FROM pg.cpdb_geometry_polygons
            WHERE geometry IS NOT NULL AND trim(geometry) <> ''
        )
    """)
    db.execute("""
        CREATE OR REPLACE TABLE geom2 AS
        SELECT agency_key, fms_id, maprojid, geom_kind, wkt,
               ST_GeomFromText(wkt)               AS g,
               ST_X(ST_Centroid(ST_GeomFromText(wkt))) AS centroid_lng,
               ST_Y(ST_Centroid(ST_GeomFromText(wkt))) AS centroid_lat
        FROM geom
    """)
    return db.execute("SELECT count(*) FROM geom2").fetchone()[0]


# Borough name -> the leading digit of a community-district id ('Brooklyn 06'
# -> '306'). ⚠ The Dashboard writes borough-wide values with no number
# ('Brooklyn' alone); those cannot name a district and are skipped rather than
# guessed at.
# ⚠⚠ `RICHMOND` AND `STATEN ISLAND` ARE ONE BOROUGH, AND OMITTING THE FIRST
# DELETES A BOROUGH SILENTLY. The retired series writes `RICHMOND` (5,869
# tokens) where the Dashboard writes `Staten Island`; with only the second
# spelling the `CASE` returns NULL, `NULL || '03'` is NULL, and every Staten
# Island row from that source is filtered out by the `dist IS NOT NULL` guard
# that exists to drop unmappable boroughs. I shipped exactly that for one build
# — the text rows for borough digit 5 fell from 707 to 205 and nothing raised.
# This is the defect `_borough_sql` already records ("normalise BOTH SIDES"),
# arriving in the builder.
BOROUGH_CODE = {
    'MANHATTAN': '1', 'BRONX': '2', 'BROOKLYN': '3',
    'QUEENS': '4', 'STATEN ISLAND': '5', 'RICHMOND': '5',
}


def build_cd_from_text(db):
    """Community-district links from the two published TEXT columns.

    ⚠⚠ GEOMETRY ALONE IS A REGRESSION, and this was caught by comparing against
    the crosswalk already on prod. Measured 2026-09-05: the hand-loaded
    `capitalprojects_cd_idx` covered 6,894 projects; a geometry-only rebuild
    covers 4,524, losing 4,091 — and only 19 of those have geometry at all. The
    original was evidently built from `capitalprojectsdollarscomp.COMMUNITY_BOARD`,
    which is populated for exactly 6,894 projects.

    So the crosswalk is a UNION and every row records HOW it was placed:

        geometry              precise, and the only method that can serve
                              cc / sd / nta at all
        community_board_text  broader, community districts ONLY

    ⚠ A community board is NOT a council district. This fallback fills `cd`
    and nothing else; inferring a council district from a community board would
    be inventing data.

    ⚠ The two sources are punctuated differently and neither splits on a single
    space by accident: the retired series writes '206 207 208', the Dashboard
    writes 'Brooklyn 06, Brooklyn 07'.
    ⚠⚠ THIS DOCSTRING SAID THE RETIRED SERIES' IDS ARE "already in crosswalk
    form", AND THAT WAS THE DEFECT IN ONE SENTENCE. They are the right SHAPE and
    the wrong NUMBERING — see the measurement below. Both text sources are now
    translated through the same `BORO`-driven `CASE`, and both are gated on the
    published boundary set.
    """
    # ⚠⚠ THE RETIRED SERIES DOES NOT NUMBER BOROUGHS THE WAY DCP DOES, AND
    # TAKING ITS TOKEN VERBATIM PUT 2,947 PROJECTS IN THE WRONG BOROUGH'S
    # COMMUNITY DISTRICT. This query used to write `trim(tok)` straight into
    # `dist`, which is DCP's `BoroCD` everywhere else in this table, under a
    # comment reading "already '206' shaped". It is 206-SHAPED; it is not a
    # 206-MEANING code.
    #
    # Measured 2026-09-10 over all 68,473 tokens, with ZERO exceptions — the
    # series' own `BORO` column says what its leading digit means:
    #
    #     1 -> BRONX     11,575        3 -> MANHATTAN  17,650
    #     2 -> BROOKLYN  16,917        4 -> QUEENS     16,462
    #                                  5 -> RICHMOND    5,869
    #
    # DCP's is 1 Manhattan, 2 Bronx, 3 Brooklyn, so 1/2/3 are permuted and only
    # Queens and Staten Island coincide.
    # ⭐ THE TWO METHODS PROVED IT INDEPENDENTLY: of 3,145 text rows on projects
    # that ALSO have geometry, **0** matched a geometry-derived code, and the
    # first-digit cross-tab is a clean permutation (text 1 -> geom 2 on 601 of
    # 702; text 3 -> geom 1 on 895 of 1,021). The worked example is
    # `826HED-545`, the CROTON FILTRATION PLANT: `BORO = BRONX`,
    # `COMMUNITY_BOARD = 107 108` — recorded in MANHATTAN community districts 7
    # and 8, and listed on `/d/cd-107` beside genuine Upper West Side projects.
    #
    # ⭐ SO THE TRANSLATION READS THE PUBLISHER'S OWN `BORO`, never a digit
    # permutation inferred here — and it is the SAME `CASE` the Dashboard path
    # below already uses, so the two text sources now share one rule instead of
    # disagreeing about what a borough digit means.
    cases = " ".join(
        f"WHEN upper(trim(boro_part)) = '{name}' THEN '{code}'"
        for name, code in BOROUGH_CODE.items())

    db.execute(rf"""
        CREATE OR REPLACE TABLE cd_text AS
        -- retired series: whitespace-separated ids, '206'-SHAPED but in the
        -- series' own borough numbering; translated through its `BORO` column.
        SELECT DISTINCT agency_key, fms_id, dist FROM (
            SELECT lpad(trim(CAST("MANAGING_AGCY_CD" AS VARCHAR)), 3, '0') AS agency_key,
                   upper(trim("PROJECT_ID"))                               AS fms_id,
                   CASE {cases} END || right(trim(tok), 2)                 AS dist
            FROM (SELECT *, "BORO" AS boro_part FROM pg.capitalprojectsdollarscomp),
                 UNNEST(str_split_regex(trim("COMMUNITY_BOARD"), '\s+')) AS t(tok)
            WHERE "COMMUNITY_BOARD" IS NOT NULL
              AND trim("COMMUNITY_BOARD") <> ''
              AND regexp_matches(trim(tok), '^[1-5][0-9]{{2}}$')
        )
        WHERE dist IS NOT NULL
    """)
    n1 = db.execute("SELECT count(*) FROM cd_text").fetchone()[0]
    db.execute(rf"""
        CREATE OR REPLACE TABLE cd_text2 AS
        SELECT DISTINCT agency_key, fms_id, dist FROM (
            SELECT agency_key, fms_id,
                   CASE {cases} END || lpad(num_part, 2, '0') AS dist
            FROM (
                SELECT lpad(trim(m.code), 3, '0') AS agency_key,
                       upper(trim(b."FMS ID"))    AS fms_id,
                       regexp_extract(trim(tok), '^([A-Za-z ]+?)\s*[0-9]*$', 1) AS boro_part,
                       regexp_extract(trim(tok), '([0-9]+)$', 1)                 AS num_part
                FROM pg.capprojectsbudgetsandschedule b
                LEFT JOIN agencymap m ON m.acro = trim(b."Managing Agency"),
                     UNNEST(str_split(b."Community Board", ',')) AS t(tok)
                WHERE b."Community Board" IS NOT NULL
                  AND trim(b."Community Board") <> ''
            )
            -- ⚠ a borough with no number is borough-wide, not a district
            WHERE num_part <> '' AND boro_part <> ''
        )
        WHERE dist IS NOT NULL AND dist NOT LIKE '%None%'
    """)
    n2 = db.execute("SELECT count(*) FROM cd_text2").fetchone()[0]
    print(f"  cd text: {n1} from the retired series, {n2} from the Dashboard")

    # ⚠⚠ GATED ON THE PUBLISHED BOUNDARY SET, WHICH IS A LOOKUP RATHER THAN A
    # RANGE. `cd.geojson` carries **71** codes — the 59 real community districts
    # plus 12 DCP Joint Interest Areas (Central Park 164, Van Cortlandt 226,
    # Prospect Park 355, the Queens parks 480-484, …). A token whose translation
    # is not one of them is not a community district, so it is dropped rather
    # than written as if it were:
    #
    #     x00   4,370 rows / 4,369 projects   a BOROUGH, with no district
    #     x99      24 rows /    20 projects   not a district
    #
    # ⭐ Hardcoding "Manhattan is 1-12, Brooklyn 1-18" would be the same answer
    # typed out, and would go stale the day DCP changes one. The boundary set is
    # the thing the geometry half already joins against, so both halves of this
    # table now agree about what a community district IS.
    # ⚠ The Dashboard path is gated too, not just the retired one — it had no
    # such check either, and one rule with two exceptions is not one rule.
    db.execute("""
        INSERT INTO dists
        SELECT agency_key, fms_id, 'cd', dist, 'community_board_text' FROM (
            SELECT * FROM cd_text UNION SELECT * FROM cd_text2
        ) t
        WHERE agency_key IS NOT NULL AND fms_id IS NOT NULL
          AND EXISTS (SELECT 1 FROM cd_codes c WHERE c.dist = t.dist)
          AND NOT EXISTS (
              SELECT 1 FROM dists d
              WHERE d.agency_key = t.agency_key AND d.fms_id = t.fms_id
                AND d.dist_type = 'cd' AND d.dist = t.dist)
    """)


def build_districts(db):
    """Spatial-join every mapped project to each boundary set.

    ⚠ ST_Intersects, not ST_Within: a polygon project can straddle a boundary
    and genuinely belongs to both districts. Using Within would silently drop
    every project that crosses a line — and a park or a road frequently does.
    """
    db.execute("CREATE OR REPLACE TABLE dists (agency_key VARCHAR, fms_id VARCHAR, dist_type VARCHAR, dist VARCHAR, method VARCHAR)")
    # acronym -> agency code, so the Dashboard's rows can be keyed like CPDB's
    db.execute("""
        CREATE OR REPLACE TABLE agencymap AS
        SELECT DISTINCT trim(magencyacro) AS acro, lpad(trim(magency), 3, '0') AS code
        FROM pg.capitalprojectslist WHERE magencyacro IS NOT NULL AND trim(magencyacro) <> ''
    """)
    for kind, url in BOUNDARIES.items():
        db.execute(f"""
            CREATE OR REPLACE TABLE b AS
            SELECT CAST(nameCol AS VARCHAR) AS dist, geom FROM st_read('{url}')
        """)
        n = db.execute("SELECT count(*) FROM b").fetchone()[0]
        db.execute(f"""
            INSERT INTO dists
            SELECT DISTINCT g.agency_key, g.fms_id, '{kind}', b.dist, 'geometry'
            FROM geom2 g JOIN b ON ST_Intersects(g.g, b.geom)
            WHERE b.dist IS NOT NULL AND b.dist <> ''
        """)
        if kind == 'cd':
            # ⚠ Kept before `b` is overwritten by the next boundary set — the
            # text half below gates on these codes, and `build_cd_from_text` is
            # called after the loop has moved on to `nta`.
            db.execute("CREATE OR REPLACE TABLE cd_codes AS SELECT DISTINCT dist FROM b")
        got = db.execute(
            "SELECT count(*) FROM dists WHERE dist_type = ?", [kind]).fetchone()[0]
        print(f"  {kind:4s} {n:4d} boundaries -> {got:6d} links (geometry)")
    build_cd_from_text(db)
    total = db.execute("SELECT count(*) FROM dists").fetchone()[0]
    print(f"  total links: {total}")
    return total


async def write_back(conn, db, apply):
    geom_rows = db.execute(
        "SELECT agency_key, fms_id, maprojid, geom_kind, wkt, centroid_lat, centroid_lng FROM geom2"
    ).fetchall()
    dist_rows = db.execute(
        "SELECT agency_key, fms_id, dist_type, dist, method FROM dists").fetchall()

    per_type = {}
    for _, _, t, _, _ in dist_rows:
        per_type[t] = per_type.get(t, 0) + 1

    if not apply:
        return {"status": "dry-run", "geometry": len(geom_rows),
                "districts": len(dist_rows), "per_type": per_type}

    async with conn.transaction():
        await conn.execute(f"DROP TABLE IF EXISTS {GEOM_TABLE}")
        await conn.execute(f"""
            CREATE TABLE {GEOM_TABLE} (
                agency_key   text NOT NULL,
                fms_id       text NOT NULL,
                maprojid     text,
                geom_kind    text NOT NULL,
                wkt          text NOT NULL,
                centroid_lat double precision,
                centroid_lng double precision,
                built_at     timestamptz NOT NULL DEFAULT now(),
                PRIMARY KEY (agency_key, fms_id)
            )
        """)
        await conn.copy_records_to_table(
            GEOM_TABLE, records=geom_rows,
            columns=['agency_key', 'fms_id', 'maprojid', 'geom_kind', 'wkt',
                     'centroid_lat', 'centroid_lng'])

        await conn.execute(f"DROP TABLE IF EXISTS {DIST_TABLE}")
        await conn.execute(f"""
            CREATE TABLE {DIST_TABLE} (
                agency_key text NOT NULL,
                fms_id     text NOT NULL,
                dist_type  text NOT NULL,
                dist       text NOT NULL,
                method     text NOT NULL,
                built_at   timestamptz NOT NULL DEFAULT now(),
                PRIMARY KEY (agency_key, fms_id, dist_type, dist)
            )
        """)
        await conn.copy_records_to_table(
            DIST_TABLE, records=dist_rows,
            columns=['agency_key', 'fms_id', 'dist_type', 'dist', 'method'])
        await conn.execute(
            f"CREATE INDEX idx_capital_districts_lookup ON {DIST_TABLE}(dist_type, dist)")

        # ⚠ THE LEGACY CROSSWALKS ARE REFRESHED TOO, and that is the half that
        # fixes a live defect today: `capitalprojects_cc_idx` and `_sd_idx` are
        # empty, so those district tabs render nothing. The existing endpoints
        # join `PROJECT_ID` (bare, blank-padded `character`) against the retired
        # series, so the legacy shape is kept exactly until they are re-pointed.
        # ⚠ It is keyed on the BARE id, so it inherits the 24-project collision
        # the spine exists to avoid — acceptable only because it is a
        # compatibility shim with a known end date, and `capital_project_districts`
        # above is the correct-grain table new code must read.
        for kind in BOUNDARIES:
            legacy = f"capitalprojects_{kind}_idx"
            await conn.execute(f'DROP TABLE IF EXISTS "{legacy}"')
            await conn.execute(
                f'CREATE TABLE "{legacy}" ("PROJECT_ID" character varying, "DIST" text)')
            await conn.execute(f"""
                INSERT INTO "{legacy}" ("PROJECT_ID", "DIST")
                SELECT DISTINCT fms_id, dist FROM {DIST_TABLE} WHERE dist_type = $1
            """, kind)
            await conn.execute(
                f'CREATE INDEX ON "{legacy}" ("PROJECT_ID")')
            await conn.execute(f'CREATE INDEX ON "{legacy}" ("DIST")')

    return {"status": "ok", "geometry": len(geom_rows),
            "districts": len(dist_rows), "per_type": per_type}


async def build(conn, cfg, apply):
    db = duckdb.connect()
    db.execute("PRAGMA memory_limit='1GB'")
    db.execute("PRAGMA temp_directory='/tmp'")
    db.execute("INSTALL spatial;")
    db.execute("LOAD spatial;")
    db.execute("INSTALL postgres;")
    db.execute("LOAD postgres;")
    db.execute(f"ATTACH '{_pg_dsn(cfg)}' AS pg (TYPE postgres, READ_ONLY);")

    n_geom = build_geometry(db)
    print(f"  geometry: {n_geom} mapped projects")
    if n_geom == 0:
        return {"status": "fail",
                "error": "0 mapped projects — are cpdb_geometry_* ingested?"}

    build_districts(db)
    return await write_back(conn, db, apply)


async def rebuild_capital_geography_hook(conn):
    cfg = getattr(Config, "db", {}) if Config else {}
    res = await build(conn, cfg, apply=True)
    print(f"[capital geo] {res['status']}: {res.get('geometry', 0)} mapped, "
          f"{res.get('districts', 0)} district links")
    if res["status"] == "fail":
        raise RuntimeError(f"capital geography build failed: {res.get('error')}")
    return res


async def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    cfg = getattr(Config, "db", {}) if Config else {}
    conn = await asyncpg.connect(**dbcreds.settings(cfg))
    try:
        res = await build(conn, cfg, apply=args.apply)
    finally:
        await conn.close()

    print(f"status     : {res['status']}")
    if res.get('error'):
        print(f"error      : {res['error']}")
    print(f"mapped     : {res.get('geometry', 0)} projects")
    print(f"district links: {res.get('districts', 0)}")
    for k, v in sorted((res.get('per_type') or {}).items()):
        print(f"  {k:4s} {v}")
    return 0 if res["status"] in ("ok", "dry-run") else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
