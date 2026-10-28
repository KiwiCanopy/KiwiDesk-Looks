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
    if not own:
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
    """(id, look) for every look.json a commit on HEAD deleted."""
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
            out.append((line.split("/")[1] + " (removed)", json.loads(text)))
        except ValueError:
            continue
    return out


def current_looks(skip=None):
    out = []
    for path in sorted((ROOT / "looks").glob("*/look.json")):
        if skip is not None and path.parent.name == skip:
            continue
        try:
            out.append((path.parent.name, json.loads(path.read_text())))
        except ValueError:
            continue
    return out


def close_matches(candidate, skip=None, threshold=0.9):
    """(id, share) of gallery looks the candidate keeps >= threshold of."""
    hits = []
    for ident, look in current_looks(skip) + removed_looks():
        share = match(candidate, look)
        if share >= threshold:
            hits.append((ident, share))
    return sorted(hits, key=lambda hit: -hit[1])


def main(argv):
    path = Path(argv[0])
    threshold = float(argv[2]) if len(argv) > 2 else 0.9
    candidate = json.loads(path.read_text())
    for ident, share in close_matches(candidate, path.parent.name, threshold):
        print(f"{ident}\t{share:.0%}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
