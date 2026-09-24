"""The api image is `python:3.9-slim`, and the unit suite is not.

⚠⚠ `def f(x: str | None = None)` is PEP 604, which **3.9 evaluates at def time**
and raises `TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'`.
The module then fails to import and **the api does not boot** — a startup crash,
not a degraded page.

The reason this needs a guard rather than care: it is invisible to every check
that runs on the developer's own interpreter. `modules/sourcedupes.py` shipped
with it, `python3 -m pytest` passed 1,482 tests on 3.12, `ast.parse` was happy,
and only the **Integration Smoke — which boots the real image** — caught it, at
the end of a four-minute build. Four other files under `api/` use PEP 604 and
all four carry `from __future__ import annotations`; nothing made that a rule,
so the fifth simply did not.

`from __future__ import annotations` (PEP 563) makes every annotation a string,
so the union is never evaluated. That is the house fix and it works on 3.7+.
"""
import ast
import os
import re

_API = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DOCKERFILE = os.path.join(_API, "Dockerfile")
_DOCKERFILE_MCP = os.path.join(_API, "Dockerfile.mcp")


def _pinned_python(dockerfile):
    """The interpreter an image actually runs, read from its own Dockerfile.

    Read rather than hardcoded so the rule tracks the image: the day either base
    moves to 3.10 this guard relaxes itself, and the day the mcp image moves
    DOWN the exemption below evaporates.
    """
    try:
        with open(dockerfile, encoding="utf-8") as fh:
            m = re.search(r"^FROM\s+python:(\S+)", fh.read(), re.M)
    except OSError:
        return (0, 0), "unknown"
    if not m:
        return (0, 0), "unknown"
    tag = m.group(1)
    v = re.match(r"(\d+)\.(\d+)", tag)
    return ((int(v.group(1)), int(v.group(2))) if v else (0, 0)), tag


def _mcp_only_files():
    """Files the MCP image copies BY NAME — its own entrypoint and nothing else.

    ⚠ Derived from `Dockerfile.mcp`, never a hand-written exemption list. A
    single-file `COPY x.py .` names something that belongs to that image; a
    directory copy (`COPY modules/ ./modules/`) is SHARED with the api image and
    must still satisfy the lower floor. `test_the_mcp_only_files_are_really_
    mcp_only` proves the api never imports them, which is what makes this an
    honest scope rather than a way of ignoring an inconvenient file.
    """
    out = set()
    try:
        with open(_DOCKERFILE_MCP, encoding="utf-8") as fh:
            for line in fh:
                m = re.match(r"^COPY\s+(\S+\.py)\s", line)
                if m:
                    out.add(m.group(1))
    except OSError:
        pass
    return out


def _pep604_lines(tree):
    """Line numbers where a PEP 604 union sits in an annotation the
    interpreter EVALUATES: a parameter, a return, or an annotated assignment.

    ⚠ Deliberately not a text scan for `|`. That would hit every bitwise or,
    every regex alternation and every SQL literal in this repo, and a guard that
    cries wolf is a guard someone switches off.
    """
    hits = []

    def scan(node):
        for sub in ast.walk(node):
            if isinstance(sub, ast.BinOp) and isinstance(sub.op, ast.BitOr):
                hits.append(sub.lineno)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for a in (list(node.args.args) + list(node.args.kwonlyargs)
                      + list(getattr(node.args, "posonlyargs", []))):
                if a.annotation is not None:
                    scan(a.annotation)
            for a in (node.args.vararg, node.args.kwarg):
                if a is not None and a.annotation is not None:
                    scan(a.annotation)
            if node.returns is not None:
                scan(node.returns)
        elif isinstance(node, ast.AnnAssign) and node.annotation is not None:
            scan(node.annotation)
    return sorted(set(hits))


def _has_future_annotations(tree):
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            if any(n.name == "annotations" for n in node.names):
                return True
    return False


# --------------------------------------------------------------------------
# The detector must work before the tree scan below means anything.
# --------------------------------------------------------------------------

_OFFENDING = "def relation(table: str, alias: str | None = None) -> str:\n    return table\n"
_GUARDED = "from __future__ import annotations\n" + _OFFENDING
_INNOCENT = "MASK = 0o644 | 0o111\nx: str = 'a|b'\n\ndef f(a, b):\n    return a | b\n"


def test_the_detector_sees_a_pep604_annotation():
    assert _pep604_lines(ast.parse(_OFFENDING))


def test_the_detector_ignores_ordinary_bitwise_or_and_pipes_in_strings():
    """Pinned because the tempting implementation — grep for `|` — would flag
    hundreds of innocent lines and get the guard disabled within a week.
    """
    assert not _pep604_lines(ast.parse(_INNOCENT))


def test_the_future_import_is_what_the_guard_looks_for():
    assert not _has_future_annotations(ast.parse(_OFFENDING))
    assert _has_future_annotations(ast.parse(_GUARDED))


# --------------------------------------------------------------------------
# The tree.
# --------------------------------------------------------------------------

def test_every_pep604_annotation_under_api_carries_the_future_import():
    scanned, users, problems = 0, [], []
    mcp_only = _mcp_only_files()
    for root, dirs, files in os.walk(_API):
        dirs[:] = [d for d in dirs
                   if d not in {"__pycache__", ".git", "node_modules", "venv", ".venv"}]
        for fn in files:
            if not fn.endswith(".py"):
                continue
            path = os.path.join(root, fn)
            rel = os.path.relpath(path, _API)
            scanned += 1
            try:
                with open(path, encoding="utf-8") as fh:
                    tree = ast.parse(fh.read())
            except (SyntaxError, UnicodeDecodeError):
                continue
            lines = _pep604_lines(tree)
            if not lines:
                continue
            users.append(rel)
            # Runs only on the MCP image, which pins a Python that understands
            # PEP 604. Shared code (modules/, seed/) is NOT exempt — it is in
            # both images and must satisfy the lower floor.
            if rel in mcp_only and _pinned_python(_DOCKERFILE_MCP)[0] >= (3, 10):
                continue
            if not _has_future_annotations(tree):
                problems.append(f"{rel}:{lines[0]}")

    # ⚠ A scan that reaches zero files is indistinguishable from a clean one.
    assert scanned > 100, f"only scanned {scanned} files"
    assert not problems, (
        f"the api runs python:{_pinned_python(_DOCKERFILE)[1]}, which EVALUATES "
        f"`X | None` in a signature and raises TypeError at import — the api "
        f"would not boot. Add `from __future__ import annotations` to:\n  "
        + "\n  ".join(problems)
        + f"\n(files legitimately using PEP 604 with the import: {len(users) - len(problems)})")


def _resolve(name, frm):
    """Map a dotted import name to a file under api/, or None if it is a
    third-party package."""
    parts = name.split(".")
    for cand in (os.path.join(_API, *parts) + ".py",
                 os.path.join(_API, *parts, "__init__.py")):
        if os.path.isfile(cand):
            return os.path.relpath(cand, _API)
    return None


def _import_closure(entry):
    """Every local file reachable from `entry` by a static import.

    ⚠ This is the api's ACTUAL boot path, which is the only thing the exemption
    can honestly be scoped to. A standalone script at api/ root that imports
    `mcp_server` is never loaded by uvicorn and proves nothing either way; the
    question is whether `main.py` can reach it.
    """
    seen, stack = set(), [entry]
    while stack:
        rel = stack.pop()
        if rel in seen:
            continue
        seen.add(rel)
        try:
            tree = ast.parse(open(os.path.join(_API, rel), encoding="utf-8").read())
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            targets = []
            if isinstance(node, ast.Import):
                targets += [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                targets.append(node.module)
                # `from modules import sourcedupes` — the submodule is the file.
                targets += [f"{node.module}.{a.name}" for a in node.names]
            for t in targets:
                got = _resolve(t, rel)
                if got and got not in seen:
                    stack.append(got)
    return seen


def test_the_api_boot_path_never_reaches_the_mcp_only_files():
    """The exemption above is only honest while the api cannot load them.

    If `main.py` ever pulls in `mcp_server`, its PEP 604 annotations start being
    evaluated under 3.9 and become a startup crash — so this must fail the
    moment the boundary moves.
    """
    mcp_only = _mcp_only_files()
    assert mcp_only, "parsed no per-file COPY out of Dockerfile.mcp"
    closure = _import_closure("main.py")
    # ⚠ Assert the closure is real before asserting what is absent from it — an
    # empty closure would make this pass for the wrong reason.
    assert len(closure) > 30, f"import closure is only {len(closure)} files"
    assert "modules/sourcedupes.py" in closure, "closure did not even reach the module under test"
    leaked = sorted(mcp_only & closure)
    assert not leaked, (
        f"the api boot path now reaches {leaked}, which this guard exempts because "
        f"only the MCP image (python:{_pinned_python(_DOCKERFILE_MCP)[1]}) runs them. "
        f"Drop the exemption or add the future import.")


def test_the_mcp_exemption_is_tied_to_the_mcp_image_pin():
    """If the MCP image ever drops below 3.10 the exemption must stop applying.

    Pinned as a property, not as the string "3.11", so a legitimate bump to 3.12
    does not fail and a regression to 3.9 does.
    """
    ver, tag = _pinned_python(_DOCKERFILE_MCP)
    assert ver >= (3, 10), (
        f"Dockerfile.mcp now pins python:{tag}, which evaluates PEP 604 unions — "
        f"the files it copies by name are no longer safe to exempt")
