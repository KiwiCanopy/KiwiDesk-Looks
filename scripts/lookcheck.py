"""Validates the gallery's look folders.

A folder under looks/ holds look.json (an exported KiwiDesk look,
stamped with format, author and an optional based_on), meta.json
and an optional screenshot.png. Every check returns messages a
submitter can act on; an empty list means the folder is fine.

Usage: python3 scripts/lookcheck.py [looks/<id> ...]
"""

import hashlib
import json
import re
import sys
from pathlib import Path

import looktags

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = json.loads((ROOT / "schema" / "keys.json").read_text())
BUILTIN_FONTS = {
    line.strip()
    for line in (ROOT / "schema" / "builtin-fonts.txt").read_text().splitlines()
    if line.strip()
}
# Names KiwiDesk reserves for its bundled looks.
BUNDLED_NAMES = {"glass", "taskbar", "classic", "tiler", "pill", "sakura"}
# Fonts KiwiDesk resolves itself rather than by family name.
SYSTEM_FONTS = {"", "System", "System Monospaced", "System Rounded"}

LOOK_KEYS = {"format", "author", "based_on", "look"}
LOOK_BODY_KEYS = {"name", "style", "colors"}
BASED_ON_KEYS = {"name", "author", "id", "removed"}
META_KEYS = {
    "tags", "description", "font_url", "submitted_by", "submitted_by_id",
    "kiwidesk_version", "keywords", "inspired_by",
}
KEYWORD = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
ALLOWED_FILES = {"look.json", "meta.json", "screenshot.png"}

HEX = re.compile(r"^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$")
ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
LOGIN = re.compile(r"^[A-Za-z0-9](-?[A-Za-z0-9]){0,38}$")
VERSION = re.compile(r"^\d+\.\d+(\.\d+)?$")
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
MAX_SCREENSHOT = 2 * 1024 * 1024
MAX_LOOK_FILE = 64 * 1024


def slug(name):
    """The folder id a look name files under."""
    text = name.lower().replace("&", " and ")
    ident = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    if ident:
        return ident
    # A name with no Latin letters or digits ("夜") still needs an id.
    return "look-" + hashlib.sha1(name.strip().encode()).hexdigest()[:8]


def plain_text(value, field, limit, errors, required=True):
    """A short single-line string with no control characters."""
    if value is None and not required:
        return
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{field} must be a non-empty string")
        return
    if len(value) > limit:
        errors.append(f"{field} is longer than {limit} characters")
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        errors.append(f"{field} contains control characters")
    if "://" in value or "<" in value:
        errors.append(f"{field} must not contain links or markup")


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def check_value(path, value, rule, errors):
    if "bool" in rule:
        if not isinstance(value, bool):
            errors.append(f"style {path} must be true or false")
    elif "number" in rule:
        low, high = rule["number"]
        if not is_number(value):
            errors.append(f"style {path} must be a number")
        elif not low <= value <= high:
            errors.append(f"style {path} must be between {low} and {high}")
    elif "enum" in rule:
        if value not in rule["enum"]:
            allowed = ", ".join(rule["enum"])
            errors.append(f"style {path} must be one of: {allowed}")
    elif "font" in rule:
        plain_text(value if value != "" else "System", f"style {path}",
                   64, errors)
    elif "gaps" in rule:
        check_gaps(path, value, errors)


def check_gaps(path, value, errors):
    shape = {
        "inner": {"horizontal", "vertical"},
        "outer": {"top", "bottom", "left", "right"},
    }
    if not isinstance(value, dict) or set(value) != set(shape):
        errors.append(f"style {path} must hold inner and outer gaps")
        return
    for part, sides in shape.items():
        group = value[part]
        if not isinstance(group, dict) or set(group) != sides:
            errors.append(f"style {path}.{part} must hold {sorted(sides)}")
            continue
        for side, number in group.items():
            if not is_number(number) or not 0 <= number <= 500:
                errors.append(f"style {path}.{part}.{side} must be 0-500")


def check_look(data, errors):
    """The look file's own shape: data only, every key known."""
    if not isinstance(data, dict):
        errors.append("look.json must be a JSON object")
        return
    for key in sorted(set(data) - LOOK_KEYS):
        errors.append(f"look.json has an unknown key: {key}")
    fmt = data.get("format")
    if not isinstance(fmt, int) or isinstance(fmt, bool) or fmt < 1:
        errors.append("look.json needs a format number")
    elif fmt > SCHEMA["look_format"]:
        errors.append(
            f"look format {fmt} is newer than this gallery knows "
            f"({SCHEMA['look_format']})"
        )
    plain_text(data.get("author"), "author", 40, errors)
    based_on = data.get("based_on")
    if based_on is not None:
        if not isinstance(based_on, dict):
            errors.append("based_on must be an object")
        else:
            for key in sorted(set(based_on) - BASED_ON_KEYS):
                errors.append(f"based_on has an unknown key: {key}")
            if based_on.get("removed") is True:
                if set(based_on) != {"removed"}:
                    errors.append("a removed based_on holds nothing else")
                return check_body(data, errors)
            plain_text(based_on.get("name"), "based_on.name", 40, errors)
            plain_text(based_on.get("author"), "based_on.author", 40,
                       errors, required=False)
            ref = based_on.get("id")
            if ref is not None and (not isinstance(ref, str)
                                    or not ID.match(ref)):
                errors.append("based_on.id must be a gallery look id")
    check_body(data, errors)


def check_body(data, errors):
    """The exported look itself: its name, style and colors."""
    body = data.get("look")
    if not isinstance(body, dict):
        errors.append("look.json needs a look object")
        return
    for key in sorted(set(body) - LOOK_BODY_KEYS):
        errors.append(f"look has an unknown key: {key}")
    plain_text(body.get("name"), "look name", 40, errors)
    if isinstance(body.get("name"), str):
        if slug(body["name"]) in BUNDLED_NAMES:
            errors.append(
                f"\"{body['name']}\" is a look bundled with KiwiDesk; "
                "pick another name"
            )
    style = body.get("style")
    if not isinstance(style, dict) or not style:
        errors.append("look needs a non-empty style map")
    else:
        for path, value in sorted(style.items()):
            rule = SCHEMA["style"].get(path)
            if rule is None:
                errors.append(f"style {path} is not a look setting")
            else:
                check_value(path, value, rule, errors)
    colors = body.get("colors")
    if not isinstance(colors, dict):
        errors.append("look needs a colors map")
        return
    automatic = set(SCHEMA["automatic_colors"])
    for path, value in sorted(colors.items()):
        if path not in SCHEMA["colors"]:
            errors.append(f"color {path} is not a look color")
        elif not isinstance(value, str):
            errors.append(f"color {path} must be a hex string")
        elif value == "" and path in automatic:
            continue
        elif not HEX.match(value):
            errors.append(f"color {path} must be #RRGGBB or #RRGGBBAA")


def check_meta(data, errors):
    if not isinstance(data, dict):
        errors.append("meta.json must be a JSON object")
        return
    for key in sorted(set(data) - META_KEYS):
        errors.append(f"meta.json has an unknown key: {key}")
    tags = data.get("tags")
    allowed = SCHEMA["tags"]
    if (not isinstance(tags, list) or not 1 <= len(tags) <= 5
            or len(set(map(str, tags))) != len(tags)):
        errors.append("tags must list 1 to 5 different tags")
    else:
        for tag in tags:
            if tag in SCHEMA["auto_tags"]:
                errors.append(f"{tag} is set automatically; untick it")
            elif tag not in allowed:
                errors.append(f"unknown tag: {tag}")
    keywords = data.get("keywords", [])
    if (not isinstance(keywords, list) or len(keywords) > 5
            or len(set(map(str, keywords))) != len(keywords)):
        errors.append("keywords must list up to 5 different words")
    else:
        for word in keywords:
            if not isinstance(word, str) or len(word) > 24 \
                    or not KEYWORD.match(word):
                errors.append(
                    "keywords use lower-case letters, digits and hyphens")
                break
    inspired = data.get("inspired_by")
    if inspired is not None and inspired not in SCHEMA["inspired_by"]:
        errors.append("inspired_by must be one of the listed palettes")
    plain_text(data.get("description"), "description", 140, errors)
    url = data.get("font_url")
    if url is not None and (not isinstance(url, str)
                            or not url.startswith("https://")
                            or len(url) > 300 or any(c.isspace() for c in url)):
        errors.append("font_url must be a single https:// link")
    login = data.get("submitted_by")
    if not isinstance(login, str) or not LOGIN.match(login):
        errors.append("submitted_by must be a GitHub account name")
    account = data.get("submitted_by_id")
    if account is not None and (not isinstance(account, int)
                                or isinstance(account, bool) or account < 1):
        errors.append("submitted_by_id must be a GitHub account number")
    version = data.get("kiwidesk_version")
    if version is not None and (not isinstance(version, str)
                                or not VERSION.match(version)):
        errors.append("kiwidesk_version must look like 4.1.0")


def load_json(path, errors, limit=MAX_LOOK_FILE):
    if not path.is_file():
        errors.append(f"{path.name} is missing")
        return None
    if path.stat().st_size > limit:
        errors.append(f"{path.name} is larger than {limit // 1024} KB")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError) as error:
        errors.append(f"{path.name} is not valid JSON: {error}")
        return None


def needs_fonts(look):
    """Font families the look names that macOS does not ship."""
    style = (look.get("look") or {}).get("style") or {}
    family = style.get("kiwishelf.font_family")
    if not isinstance(family, str) or family in SYSTEM_FONTS:
        return []
    return [] if family in BUILTIN_FONTS else [family]


def check_folder(folder):
    """Every problem with one look folder."""
    folder = Path(folder)
    errors = []
    if not ID.match(folder.name):
        errors.append(f"folder name {folder.name!r} must be lower-case-words")
    if folder.is_symlink():
        return errors + ["the look folder must not be a link"]
    for entry in sorted(folder.iterdir()):
        if entry.name not in ALLOWED_FILES or entry.is_symlink() \
                or not entry.is_file():
            errors.append(f"unexpected file: {entry.name}")
    look = load_json(folder / "look.json", errors)
    if look is not None:
        check_look(look, errors)
        name = (look.get("look") or {}).get("name") if isinstance(look, dict) \
            else None
        if isinstance(name, str) and slug(name) != folder.name:
            errors.append(
                f"folder must be named {slug(name)!r} after the look"
            )
    meta = load_json(folder / "meta.json", errors)
    if meta is not None:
        check_meta(meta, errors)
        if isinstance(look, dict) and isinstance(meta, dict) \
                and "high-contrast" in (meta.get("tags") or []):
            ratio = looktags.contrast(look)
            if ratio is None or ratio < looktags.HIGH_CONTRAST_AT:
                errors.append(
                    "high-contrast needs the bar's text and fill at 7:1 "
                    f"or more (this look: {ratio or 0:.1f}:1)")
    shot = folder / "screenshot.png"
    if shot.is_file() and not shot.is_symlink():
        if shot.stat().st_size > MAX_SCREENSHOT:
            errors.append("screenshot.png is larger than 2 MB")
        with shot.open("rb") as handle:
            if handle.read(8) != PNG_MAGIC:
                errors.append("screenshot.png is not a PNG image")
    return errors


def check_all(looks_dir):
    """Problems per folder. Folder ids are look-name slugs, so two
    looks can never share a name."""
    looks_dir = Path(looks_dir)
    report = {}
    if not looks_dir.is_dir():
        return report
    for folder in sorted(p for p in looks_dir.iterdir() if p.is_dir()):
        report[folder.name] = check_folder(folder)
    return report


def main(argv):
    targets = [Path(a) for a in argv] or None
    if targets is None:
        report = check_all(ROOT / "looks")
    else:
        report = {t.name: check_folder(t) for t in targets}
    failed = False
    for name, errors in report.items():
        for error in errors:
            failed = True
            print(f"looks/{name}: {error}")
    if not failed:
        print(f"{len(report)} look(s) valid")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
