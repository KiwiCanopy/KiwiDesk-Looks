"""Turns a "Submit a look" or "Remove my look" issue into a change.

The issue body is untrusted input: it is read from a file, parsed
as data, and only ever written into looks/<id>/ after the id
passes lookcheck's pattern. Nothing from it reaches a shell.

Usage:
  submission.py submit <body-file> <login> <account-id> <result-file>
  submission.py remove <body-file> <login> <account-id> <result-file>

Writes a JSON result {"ok", "id", "action", "message"} that the
workflow turns into a comment, a commit and a pull request.
"""

import json
import re
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

import lookcheck
import looksim

ROOT = lookcheck.ROOT
LOOKS = ROOT / "looks"
ATTACHMENT = re.compile(
    r"https://github\.com/user-attachments/assets/[0-9a-fA-F-]{36}"
)
NO_RESPONSE = "_No response_"

# Issue-form labels, exactly as .github/ISSUE_TEMPLATE renders them.
F_LOOK = "Look file"
F_AUTHOR = "Your name as the author"
F_BASED_ON = "Based on"
F_TAGS = "Tags"
F_DESCRIPTION = "One-line description"
F_FONT_URL = "Font download link"
F_WALLPAPER = "Wallpaper"
F_WALLPAPER_URL = "Wallpaper link"
F_VERSION = "KiwiDesk version"
F_SCREENSHOT = "Screenshot"
F_KEYWORDS = "Keywords"
F_INSPIRED = "Inspired by"
F_REMOVE_ID = "Look"
F_REMOVE_NAME = "Credit"


def sections(body):
    """{label: text} from an issue form's '### Label' sections."""
    out = {}
    label = None
    lines = []
    for line in body.replace("\r\n", "\n").split("\n"):
        if line.startswith("### "):
            if label is not None:
                out[label] = "\n".join(lines).strip()
            label = line[4:].strip()
            lines = []
        elif label is not None:
            lines.append(line)
    if label is not None:
        out[label] = "\n".join(lines).strip()
    return {k: ("" if v == NO_RESPONSE else v) for k, v in out.items()}


def unfence(text):
    """The JSON inside a ```json fence, or the text as it is."""
    match = re.search(r"```[a-z]*\n(.*?)\n```", text, re.S)
    return match.group(1) if match else text


def checked(text):
    """Labels of the ticked boxes in a checkboxes section."""
    return [m.group(1).strip()
            for m in re.finditer(r"^- \[[xX]\] (.+)$", text, re.M)]


def parse_based_on(text):
    """'Dusk by Anna' or a gallery link/id into a based_on object."""
    text = text.strip()
    if not text:
        return None
    ident = text.rstrip("/").split("/")[-1].lower()
    folder = LOOKS / ident
    if lookcheck.ID.match(ident) and (folder / "look.json").is_file():
        original = json.loads((folder / "look.json").read_text())
        return {"name": original["look"]["name"],
                "author": original["author"], "id": ident}
    name, sep, author = text.rpartition(" by ")
    if sep and name.strip():
        return {"name": name.strip(), "author": author.strip()}
    return {"name": text}


def download_screenshot(text, target):
    """Saves the first attached image; returns an error or None."""
    match = ATTACHMENT.search(text)
    if not match:
        return None if not text.strip() else (
            "attach the screenshot by pasting or dragging it into the "
            "Screenshot field"
        )
    request = urllib.request.Request(match.group(0),
                                     headers={"User-Agent": "kiwidesk-looks"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read(lookcheck.MAX_SCREENSHOT + 1)
    except (urllib.error.URLError, OSError):
        return "the screenshot couldn't be downloaded; attach it again"
    if len(data) > lookcheck.MAX_SCREENSHOT:
        return "the screenshot is larger than 2 MB"
    if not data.startswith(lookcheck.PNG_MAGIC):
        return "the screenshot must be a PNG image"
    target.write_bytes(data)
    return None


def build_submission(fields, login, staging, fetch=download_screenshot,
                     account=None):
    """Writes the look folder into staging; returns (id, errors)."""
    try:
        look = json.loads(unfence(fields.get(F_LOOK, "")))
    except ValueError as error:
        return None, [f"the look file is not valid JSON: {error}"]
    if not isinstance(look, dict) or not isinstance(look.get("look"), dict):
        return None, ["paste the whole exported file, starting with {"]
    if "format" not in look:
        # Only KiwiDesk before 4.1 wrote a look without its format.
        return None, ["this look comes from KiwiDesk 4.0 or older; "
                      "update KiwiDesk and export it again"]
    look["author"] = fields.get(F_AUTHOR, "").strip() or login
    based_on = parse_based_on(fields.get(F_BASED_ON, ""))
    if based_on:
        look["based_on"] = based_on
    else:
        look.pop("based_on", None)
    name = look["look"].get("name")
    ident = lookcheck.slug(name) if isinstance(name, str) else ""
    if not lookcheck.ID.match(ident):
        return None, ["the look needs a name made of letters or digits"]
    meta = {
        "tags": [t.split(" ")[0] for t in checked(fields.get(F_TAGS, ""))],
        "description": fields.get(F_DESCRIPTION, "").strip(),
        "submitted_by": login,
    }
    if account is not None:
        meta["submitted_by_id"] = account
    words = re.split(r"[,\s]+", fields.get(F_KEYWORDS, "").strip().lower())
    words = [w.lstrip("#") for w in words if w.lstrip("#")]
    if words:
        meta["keywords"] = words
    inspired = fields.get(F_INSPIRED, "").strip()
    if inspired and inspired != "None":
        meta["inspired_by"] = inspired
    for key, field in (("font_url", F_FONT_URL),
                       ("wallpaper", F_WALLPAPER),
                       ("wallpaper_url", F_WALLPAPER_URL),
                       ("kiwidesk_version", F_VERSION)):
        value = fields.get(field, "").strip()
        if value:
            meta[key] = value
    folder = staging / ident
    folder.mkdir(parents=True)
    (folder / "look.json").write_text(
        json.dumps(look, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    )
    (folder / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    )
    shot_error = fetch(fields.get(F_SCREENSHOT, ""), folder / "screenshot.png")
    errors = lookcheck.check_folder(folder)
    if shot_error:
        errors.append(shot_error)
    return ident, errors


def owner_of(ident):
    """The submitting account's meta, or None for a free id."""
    meta = LOOKS / ident / "meta.json"
    if not meta.is_file():
        return None
    return json.loads(meta.read_text())


def same_account(meta, login, account):
    """Matches by account number where both sides have one, since a
    renamed login can be claimed by someone else."""
    if account is not None and meta.get("submitted_by_id") is not None:
        return meta["submitted_by_id"] == account
    return str(meta.get("submitted_by", "")).lower() == login.lower()


def quoted(errors):
    """Errors as a code block: they echo submitted text, which must not
    render as mentions, links or markup in the bot's comment."""
    lines = [e.replace("`", "'") for e in errors]
    return "```text\n" + "\n".join(lines) + "\n```"


def submit(fields, login, fetch=download_screenshot, account=None):
    staging = ROOT / ".staging"
    shutil.rmtree(staging, ignore_errors=True)
    try:
        ident, errors = build_submission(fields, login, staging, fetch,
                                         account)
        if errors:
            return {"ok": False, "id": ident, "action": "none",
                    "message": quoted(errors)}
        owner = owner_of(ident)
        if owner is not None and not same_account(owner, login, account):
            return {"ok": False, "id": ident, "action": "none",
                    "message": quoted([f"a look named like this already "
                                       f"exists (looks/{ident}); pick "
                                       f"another name"])}
        action = "update" if owner is not None else "add"
        target = LOOKS / ident
        shutil.rmtree(target, ignore_errors=True)
        LOOKS.mkdir(exist_ok=True)
        shutil.move(str(staging / ident), str(target))
        candidate = json.loads((target / "look.json").read_text())
        close = looksim.close_matches(candidate, skip=ident)
        note = "".join(f"\n- {looksim.label(i, k)}: {s:.0%} of its "
                       f"settings match" for i, s, k in close)
        pending = [i for i, _, k in close if k == looksim.PENDING]
        return {"ok": True, "id": ident, "action": action, "close": note,
                "pending": pending, "message": ""}
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def remove(fields, login, account=None):
    ident = fields.get(F_REMOVE_ID, "").strip().rstrip("/").split("/")[-1]
    ident = ident.lower()
    if not lookcheck.ID.match(ident) or not (LOOKS / ident).is_dir():
        return {"ok": False, "id": None, "action": "none",
                "message": "No gallery look has that id."}
    owner = owner_of(ident)
    if owner is None or not same_account(owner, login, account):
        return {"ok": False, "id": ident, "action": "none",
                "message": "Only the account that submitted this look can "
                           "remove it here. Please use Report a look."}
    drop_name = bool(checked(fields.get(F_REMOVE_NAME, "")))
    renamed = []
    if drop_name:
        for path in sorted(LOOKS.glob("*/look.json")):
            look = json.loads(path.read_text())
            if (look.get("based_on") or {}).get("id") == ident:
                look["based_on"] = {"removed": True}
                path.write_text(json.dumps(look, indent=2, sort_keys=True,
                                           ensure_ascii=False) + "\n")
                renamed.append(path.parent.name)
    shutil.rmtree(LOOKS / ident)
    return {"ok": True, "id": ident, "action": "remove", "renamed": renamed,
            "message": ""}


def main(argv):
    mode, body_file, login, account, result_file = argv
    account = int(account)
    fields = sections(Path(body_file).read_text(encoding="utf-8"))
    result = submit(fields, login, account=account) if mode == "submit" \
        else remove(fields, login, account)
    Path(result_file).write_text(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
