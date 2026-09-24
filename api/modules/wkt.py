"""WKT to GeoJSON, for exactly the two shapes NYC publishes for capital projects.

⚠⚠ NOT A GENERAL WKT PARSER, DELIBERATELY. Measured over all 4,560 rows of
`capital_project_geometry` on 2026-09-06:

    MULTIPOINT     2,776   members always parenthesised (2,776 of 2,776), 1-36 of them
    MULTIPOLYGON   1,784   536 carry more than one polygon, 103 carry interior rings
    Z / M / EMPTY      0
    longest value        617,894 characters

Anything outside that vocabulary RAISES rather than being guessed at, because a
parser that silently mis-reads a geometry draws a project in the wrong place —
which is worse than drawing nothing, and looks fine.

⚠ The coordinate reader is a balanced-paren descent rather than a regex. Holes
and multi-polygons are nesting, not special cases, so nesting is what it walks;
a regex over 618 kB of coordinates is where this would quietly go wrong.

⚠ There is no PostGIS on this database (`pg_extension` holds `plpgsql` and
`pg_trgm` only — checked, not assumed), so this cannot be `ST_AsGeoJSON`.
"""
from __future__ import annotations

_SUPPORTED = ("MULTIPOLYGON", "MULTIPOINT")


class WktError(ValueError):
    """A geometry this parser will not guess at."""


def _group(s, i):
    """Parse the balanced group starting at `s[i] == '('`; return (list, next)."""
    n = len(s)
    out = []
    i += 1
    while i < n:
        c = s[i]
        if c.isspace():
            i += 1
        elif c == "(":
            sub, i = _group(s, i)
            out.append(sub)
        elif c == ")":
            return out, i + 1
        elif c == ",":
            i += 1
        else:
            j = i
            while j < n and s[j] not in ",)":
                j += 1
            parts = s[i:j].split()
            if len(parts) != 2:
                # ⚠ 2-D only, and it is checked rather than assumed: a Z value
                # here would be silently read as a second coordinate and put the
                # project on the equator.
                raise WktError(f"expected an x y pair, got {s[i:j]!r}")
            out.append([float(parts[0]), float(parts[1])])
            i = j
    raise WktError("unbalanced parentheses")


def to_geojson(wkt):
    """A GeoJSON geometry dict, or raise `WktError`."""
    if not wkt or not str(wkt).strip():
        raise WktError("empty geometry")
    s = str(wkt).strip()
    head, _, _ = s.partition("(")
    kind = head.strip().upper()
    if kind not in _SUPPORTED:
        raise WktError(f"unsupported geometry type {kind!r}")
    coords, _ = _group(s, s.index("("))

    if kind == "MULTIPOLYGON":
        # ((ring),(hole)),((ring)) — already GeoJSON MultiPolygon nesting.
        return {"type": "MultiPolygon", "coordinates": coords}

    # ⚠ MULTIPOINT's members are parenthesised in every row measured, which adds
    # one level of nesting GeoJSON does not want. Flattening blindly would be
    # wrong for the bare form, so the shape is CHECKED and the bare form is
    # accepted on its own terms rather than assumed absent for ever.
    pts = []
    for m in coords:
        if m and isinstance(m[0], list):
            pts.extend(m)
        else:
            pts.append(m)
    return {"type": "MultiPoint", "coordinates": pts}


def bbox(geom):
    """[west, south, east, north] over every coordinate in a geometry."""
    xs, ys = [], []

    def walk(node):
        if node and isinstance(node[0], (int, float)):
            xs.append(node[0])
            ys.append(node[1])
            return
        for child in node:
            walk(child)

    walk(geom["coordinates"])
    if not xs:
        raise WktError("geometry carries no coordinates")
    return [min(xs), min(ys), max(xs), max(ys)]
