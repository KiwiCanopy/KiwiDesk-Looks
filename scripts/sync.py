"""Keeps each look's download file and like page on GitHub, and
records their counts in stats.json for index.json.

- Downloads: every look's file is an asset `<id>.json` on the one
  release tagged `looks`; GitHub counts each download. An update
  re-uploads the file, so the earlier count moves into
  `downloads_base` and the total never drops.
- Likes: every look has one discussion in the "Looks" category; its
  ❤️ reactions are the likes, one per account.

Run by .github/workflows/gallery.yml with GH_TOKEN set.
Usage: python3 scripts/sync.py
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATS = ROOT / "stats.json"
REPO = os.environ.get("GITHUB_REPOSITORY", "KiwiCanopy/KiwiDesk-Looks")
TAG = "looks"
CATEGORY = "Looks"
SITE = "https://kiwidesk.kiwicanopy.com/looks/"


def file_sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def plan_assets(looks, assets, stats):
    """What to upload and delete, and the carried-over counts.

    looks:  {id: sha of look.json}
    assets: {asset name: {"id": n, "downloads": n}}
    stats:  {id: {"asset_sha", "downloads_base", ...}}
    Returns (uploads, deletes, bases): ids to upload (`--clobber`
    replaces a changed file), orphaned asset ids to delete, and each
    id's downloads_base after the change.
    """
    uploads, deletes, bases = [], [], {}
    for ident, sha in sorted(looks.items()):
        entry = stats.get(ident, {})
        base = entry.get("downloads_base", 0)
        asset = assets.get(f"{ident}.json")
        if asset is None:
            uploads.append(ident)
        elif entry.get("asset_sha") != sha:
            base += asset["downloads"]
            uploads.append(ident)
        bases[ident] = base
    for name, asset in sorted(assets.items()):
        if name.endswith(".json") and name[:-5] not in looks:
            deletes.append(asset["id"])
    return uploads, deletes, bases


def plain(text):
    """Submitted text made inert in markdown: no formatting, links,
    mentions or issue references from a bot-written post."""
    text = re.sub(r"([\\`*_{}\[\]()<>!|~])", r"\\\1", str(text))
    text = re.sub(r"([@#])", "\\1\u200b", text)
    return re.sub(r"\.(?=\S)", ".\u200b", text)


def marker(ident):
    return f"<!-- look:{ident} -->"


def like_body(name, author, ident):
    return (
        f"{marker(ident)}\n"
        f"**{plain(name)}** by {plain(author)}\n\n"
        f"Like this look by giving this post a ❤️. Only ❤️ counts, "
        f"one per account.\n\n"
        f"See it in the gallery: {SITE}#{ident}"
    )


def gh(*args, data=None):
    result = subprocess.run(["gh", *args], input=data, capture_output=True,
                            text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:3])}: {result.stderr.strip()}")
    return result.stdout


def graphql(query, **variables):
    args = ["api", "graphql", "-f", f"query={query}"]
    for key, value in variables.items():
        args += ["-F" if isinstance(value, int) else "-f", f"{key}={value}"]
    return json.loads(gh(*args))["data"]


def release_assets():
    try:
        gh("release", "view", TAG, "-R", REPO)
    except RuntimeError:
        gh("release", "create", TAG, "-R", REPO, "--title", "Looks",
           "--notes", "Every gallery look's file. Updated by CI.",
           "--latest=false")
    out = gh("api", f"repos/{REPO}/releases/tags/{TAG}")
    release = json.loads(out)
    return {a["name"]: {"id": a["id"], "downloads": a["download_count"]}
            for a in release.get("assets", [])}


def save(stats):
    """Written after every change on GitHub, so a crash or a failed
    push never loses a discussion number or a carried count."""
    STATS.write_text(json.dumps(stats, indent=2, sort_keys=True) + "\n")


def sync_assets(looks, stats):
    assets = release_assets()
    uploads, deletes, bases = plan_assets(looks, assets, stats)
    for asset_id in deletes:
        gh("api", "-X", "DELETE", f"repos/{REPO}/releases/assets/{asset_id}")
    with tempfile.TemporaryDirectory() as tmp:
        for ident in uploads:
            copy = Path(tmp) / f"{ident}.json"
            copy.write_bytes((ROOT / "looks" / ident / "look.json")
                             .read_bytes())
            entry = stats.setdefault(ident, {})
            entry["downloads_base"] = bases[ident]
            save(stats)
            gh("release", "upload", TAG, str(copy), "-R", REPO, "--clobber")
            entry["asset_sha"] = looks[ident]
            save(stats)
    assets = release_assets()
    for ident, sha in looks.items():
        entry = stats.setdefault(ident, {})
        entry["asset_sha"] = sha
        entry["downloads_base"] = bases[ident]
        current = assets.get(f"{ident}.json", {}).get("downloads", 0)
        entry["downloads"] = bases[ident] + current


def existing_discussions(category):
    """{look id: (number, url)} from the markers in the category."""
    owner, name = REPO.split("/")
    data = graphql(
        "query($owner:String!,$name:String!,$cat:ID!){repository(owner:"
        "$owner,name:$name){discussions(first:100,categoryId:$cat){nodes{"
        "number url body}}}}", owner=owner, name=name, cat=category)
    found = {}
    for node in data["repository"]["discussions"]["nodes"]:
        match = re.search(r"<!-- look:([a-z0-9-]+) -->", node["body"])
        if match:
            found[match.group(1)] = (node["number"], node["url"])
    return found


def close_discussion(number):
    owner, name = REPO.split("/")
    data = graphql(
        "query($owner:String!,$name:String!,$n:Int!){repository(owner:"
        "$owner,name:$name){discussion(number:$n){id}}}",
        owner=owner, name=name, n=number)
    graphql("mutation($id:ID!){closeDiscussion(input:{discussionId:$id,"
            "reason:OUTDATED}){discussion{id}}}",
            id=data["repository"]["discussion"]["id"])


def category_ids():
    owner, name = REPO.split("/")
    data = graphql(
        "query($owner:String!,$name:String!){repository(owner:$owner,"
        "name:$name){id discussionCategories(first:50){nodes{id name}}}}",
        owner=owner, name=name)
    repo = data["repository"]
    for node in repo["discussionCategories"]["nodes"]:
        if node["name"] == CATEGORY:
            return repo["id"], node["id"]
    return repo["id"], None


def sync_likes(looks, stats):
    repo_id, category = category_ids()
    if category is None:
        print(f"::warning::No \"{CATEGORY}\" discussion category; "
              "likes are not tracked")
        return
    known = existing_discussions(category)
    for ident in sorted(looks):
        entry = stats.setdefault(ident, {})
        if "discussion" not in entry and ident in known:
            entry["discussion"], entry["like_url"] = known[ident]
            save(stats)
        if "discussion" not in entry:
            look = json.loads((ROOT / "looks" / ident / "look.json")
                              .read_text())
            made = graphql(
                "mutation($repo:ID!,$cat:ID!,$title:String!,$body:String!)"
                "{createDiscussion(input:{repositoryId:$repo,categoryId:$cat,"
                "title:$title,body:$body}){discussion{number url}}}",
                repo=repo_id, cat=category, title=look["look"]["name"],
                body=like_body(look["look"]["name"], look["author"], ident))
            found = made["createDiscussion"]["discussion"]
            entry["discussion"] = found["number"]
            entry["like_url"] = found["url"]
            save(stats)
        owner, name = REPO.split("/")
        data = graphql(
            "query($owner:String!,$name:String!,$n:Int!){repository("
            "owner:$owner,name:$name){discussion(number:$n){"
            "reactionGroups{content reactors{totalCount}}}}}",
            owner=owner, name=name, n=entry["discussion"])
        groups = data["repository"]["discussion"]["reactionGroups"]
        entry["likes"] = next((g["reactors"]["totalCount"] for g in groups
                               if g["content"] == "HEART"), 0)


def main():
    stats = json.loads(STATS.read_text()) if STATS.is_file() else {}
    looks = {p.parent.name: file_sha(p)
             for p in (ROOT / "looks").glob("*/look.json")}
    for gone in sorted(set(stats) - set(looks)):
        number = stats[gone].get("discussion")
        if number is not None:
            try:
                close_discussion(number)
            except RuntimeError as error:
                print(f"::warning::could not close discussion {number}: "
                      f"{error}")
        del stats[gone]
        save(stats)
    try:
        sync_assets(looks, stats)
        sync_likes(looks, stats)
    finally:
        save(stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
