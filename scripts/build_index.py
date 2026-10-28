"""Builds index.json, the file the gallery page reads.

Deterministic: the same tree always writes the same bytes, so the
index commit only happens when a look actually changed. Refuses to
write while any folder fails lookcheck.

Usage: python3 scripts/build_index.py [--check]
--check exits 1 when index.json is out of date instead of writing.
"""

import json
import subprocess
import sys
from pathlib import Path

import lookcheck
import looktags

ROOT = lookcheck.ROOT
INDEX = ROOT / "index.json"
STATS = ROOT / "stats.json"
INDEX_FORMAT = 1
RELEASE = "https://github.com/KiwiCanopy/KiwiDesk-Looks/releases/download/looks"


def git(*args):
    result = subprocess.run(
        ["git", "-C", str(ROOT), *args],
        capture_output=True, text=True, check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def history(folder):
    """(added, updated, version) from git; version counts look edits."""
    rel = f"looks/{folder.name}"
    dates = git("log", "--format=%cs", "--", rel).splitlines()
    edits = git("log", "--format=%H", "--", f"{rel}/look.json").splitlines()
    if not dates:
        return None, None, 1
    return dates[-1], dates[0], max(1, len(edits))


def load_stats():
    """Counts and links sync.py keeps; empty before its first run."""
    if not STATS.is_file():
        return {}
    return json.loads(STATS.read_text())


def entry(folder, stats=None):
    look = json.loads((folder / "look.json").read_text())
    meta = json.loads((folder / "meta.json").read_text())
    added, updated, version = history(folder)
    rel = f"looks/{folder.name}"
    shot = folder / "screenshot.png"
    counts = (stats or {}).get(folder.name, {})
    auto = looktags.auto_tags(look)
    return {
        "id": folder.name,
        "name": look["look"]["name"],
        "author": look["author"],
        "based_on": look.get("based_on"),
        "built_on": [],
        "tags": auto + [t for t in meta["tags"] if t not in auto],
        "auto_tags": auto,
        "keywords": meta.get("keywords", []),
        "inspired_by": meta.get("inspired_by"),
        "likes": counts.get("likes", 0),
        "like_url": counts.get("like_url"),
        "downloads": counts.get("downloads", 0),
        "download_url": f"{RELEASE}/{folder.name}.json",
        "description": meta["description"],
        "look_format": look["format"],
        "kiwidesk_version": meta.get("kiwidesk_version"),
        "needs_fonts": lookcheck.needs_fonts(look),
        "font_url": meta.get("font_url"),
        "file": f"{rel}/look.json",
        "image": {"kind": "screenshot", "path": f"{rel}/screenshot.png"}
        if shot.is_file() else None,
        "added": added,
        "updated": updated,
        "version": version,
    }


def build(looks_dir=None):
    looks_dir = Path(looks_dir or ROOT / "looks")
    report = lookcheck.check_all(looks_dir)
    bad = {name: errors for name, errors in report.items() if errors}
    if bad:
        raise ValueError(
            "; ".join(f"{n}: {e[0]}" for n, e in sorted(bad.items()))
        )
    stats = load_stats()
    looks = [entry(looks_dir / name, stats) for name in sorted(report)]
    by_id = {look["id"]: look for look in looks}
    for look in looks:
        parent = (look["based_on"] or {}).get("id")
        if parent in by_id:
            by_id[parent]["built_on"].append(look["id"])
    return {"format": INDEX_FORMAT, "looks": looks}


def render(index):
    return json.dumps(index, indent=2, ensure_ascii=False,
                      sort_keys=True) + "\n"


def main(argv):
    try:
        text = render(build())
    except ValueError as error:
        print(f"index not built: {error}")
        return 1
    if "--check" in argv:
        current = INDEX.read_text() if INDEX.is_file() else ""
        if current != text:
            print("index.json is out of date: run scripts/build_index.py")
            return 1
        print("index.json is up to date")
        return 0
    INDEX.write_text(text)
    print("wrote index.json")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
