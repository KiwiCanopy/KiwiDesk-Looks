"""Draws preview.png for every look without a screenshot.

KiwiDesk draws it (`kiwidesk preview <look.json> <out.png>`): the
picture its own Looks shelf shows, at a fixed size and scale, so a
rerun writes the same bytes. A look given a screenshot loses its
preview. A KiwiDesk too old for the verb draws nothing, and the
site keeps drawing its sketch.

Usage: python3 scripts/previews.py <kiwidesk binary> [looks dir]
"""

import subprocess
import sys
from pathlib import Path

import lookcheck

USAGE = "usage: kiwidesk preview"
TIMEOUT = 60


def run(binary, *args):
    return subprocess.run(
        [str(binary), "preview", *map(str, args)],
        capture_output=True, text=True, check=False, timeout=TIMEOUT,
    )


def supported(binary):
    """Whether this KiwiDesk has the verb: one that lacks it sends
    `preview` to the running app instead and never prints its usage."""
    return USAGE in run(binary).stderr


def draw(binary, looks_dir):
    """(drawn, failed): folder ids, each with its error for a failure."""
    drawn, failed = [], []
    for folder in sorted(p for p in Path(looks_dir).iterdir() if p.is_dir()):
        preview = folder / "preview.png"
        if (folder / "screenshot.png").is_file():
            preview.unlink(missing_ok=True)
            continue
        result = run(binary, folder / "look.json", preview)
        if result.returncode == 0:
            drawn.append(folder.name)
        else:
            # An old picture of an edited look is worse than none.
            preview.unlink(missing_ok=True)
            failed.append((folder.name, result.stderr.strip()))
    return drawn, failed


def main(argv):
    if not argv:
        print(__doc__.strip().splitlines()[-1])
        return 2
    binary = Path(argv[0])
    looks_dir = Path(argv[1]) if len(argv) > 1 else lookcheck.ROOT / "looks"
    if not supported(binary):
        print("::notice::this KiwiDesk cannot draw previews; none drawn")
        return 0
    drawn, failed = draw(binary, looks_dir)
    for ident, error in failed:
        print(f"::warning::no preview for {ident}: {error}")
    print(f"drew {len(drawn)} preview(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
