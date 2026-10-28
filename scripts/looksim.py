"""How close one look is to another.

The same measure KiwiDesk's credit uses (#1740): only the settings
the ORIGINAL sets count, each style path and each color path once,
nothing weighted. Used here for the reviewer's copy warning.

Usage: python3 scripts/looksim.py <look.json> [--threshold 0.9]
compares one file against every current and removed gallery look.
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# An original setting fewer than this matches nearly anything.
MIN_SETTINGS = 5
CURRENT, REMOVED, PENDING = "current", "removed", "pending"


def settings(look):
    body = look.get("look") or {}
    out = {}
    for path, value in (body.get("style") or {}).items():
        out["style:" + path] = value
    for path, value in (body.get("colors") or {}).items():
        out["color:" + path] = value.upper() if isinstance(value, str) \
            else value
    return out


def match(candidate, original):
    """Share of the original's own settings the candidate keeps."""
    own = settings(original)
    if len(own) < MIN_SETTINGS:
        return 0.0
    theirs = settings(candidate)
    same = sum(1 for key, value in own.items() if theirs.get(key) == value)
    return same / len(own)


def git(*args):
    return subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True, text=True, check=False,
    ).stdout


def removed_looks():
    """(id, look, kind) for every look.json a commit on HEAD deleted."""
    out = []
    log = git("log", "--diff-filter=D", "--name-only", "--format=%H",
              "--", "looks/*/look.json")
    sha = None
    for line in log.splitlines():
        if not line.strip():
            continue
        if not line.startswith("looks/"):
            sha = line.strip()
            continue
        text = git("show", f"{sha}^:{line}")
        try:
            out.append((line.split("/")[1], json.loads(text), REMOVED))
        except ValueError:
            continue
    return out


def pending_looks():
    """(id, look, kind) for every submission still on its own branch.

    A merged submission's branch may linger, so an id the gallery
    already holds is left to current_looks."""
    git("fetch", "-q", "origin",
        "+refs/heads/submission/*:refs/remotes/origin/submission/*")
    out = []
    refs = git("for-each-ref", "--format=%(refname)",
               "refs/remotes/origin/submission/")
    for ref in refs.splitlines():
        ident = ref.rsplit("/", 1)[-1]
        if (ROOT / "looks" / ident).is_dir():
            continue
        text = git("show", f"{ref}:looks/{ident}/look.json")
        try:
            out.append((ident, json.loads(text), PENDING))
        except ValueError:
            continue
    return out


def current_looks(skip=None):
    out = []
    for path in sorted((ROOT / "looks").glob("*/look.json")):
        if skip is not None and path.parent.name == skip:
            continue
        try:
            out.append((path.parent.name, json.loads(path.read_text()),
                        CURRENT))
        except ValueError:
            continue
    return out


def label(ident, kind):
    return {CURRENT: ident, REMOVED: f"{ident} (removed)",
            PENDING: f"{ident} (waiting for review)"}[kind]


def close_matches(candidate, skip=None, threshold=0.9):
    """(id, share, kind) of gallery looks the candidate keeps at least
    threshold of: current, removed, and still waiting for review."""
    hits = []
    for ident, look, kind in (current_looks(skip) + removed_looks()
                              + pending_looks()):
        if kind != CURRENT and ident == skip:
            continue  # its own earlier or pending version
        share = match(candidate, look)
        if share >= threshold:
            hits.append((ident, share, kind))
    return sorted(hits, key=lambda hit: -hit[1])


def main(argv):
    path = Path(argv[0])
    threshold = float(argv[2]) if len(argv) > 2 else 0.9
    candidate = json.loads(path.read_text())
    for ident, share, kind in close_matches(candidate, path.parent.name,
                                            threshold):
        print(f"{label(ident, kind)}\t{share:.0%}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
