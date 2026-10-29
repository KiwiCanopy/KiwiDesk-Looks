# Contributing a look

The easy way is the [**Submit a look**](../../issues/new?template=submit-look.yml)
form: paste your exported look, and a bot checks it and opens the pull
request for you. This page is for people who'd rather open one by hand.

## A look folder

```
looks/<id>/
├── look.json        required
├── meta.json        required
├── screenshot.png   optional, PNG, 2 MB at most
└── preview.png      drawn by CI when there is no screenshot
```

`<id>` is the look's name in lower case, words joined by `-`, and `&`
written as `and`: "Black & White Tiler" lives in `black-and-white-tiler`.
Nothing else may sit in the folder.

### look.json

The file KiwiDesk's **Export…** writes, plus three keys:

```json
{
  "format": 2,
  "author": "Anna",
  "based_on": {"name": "Dusk", "author": "Maya", "id": "dusk"},
  "look": {
    "name": "Dusk Remix",
    "style": {"kiwishelf.thickness": 40, "border.sheen": 0.5},
    "colors": {"border.focused_color": "#564AB6"}
  }
}
```

- `format`: the look format, from `schema/keys.json` ▸ `look_format`.
- `author`: the name shown on the card.
- `based_on`: only if your look started from someone else's and still
  keeps about half of its settings. `id` is the original's folder when
  it came from this gallery.

Every style path and color must be one `schema/keys.json` lists. A look
is data only: no Lua, no scripts, no links.

### meta.json

```json
{
  "tags": ["calm", "pastel"],
  "description": "A calm violet evening.",
  "keywords": ["lavender", "soft"],
  "inspired_by": "nord",
  "submitted_by": "your-github-name",
  "kiwidesk_version": "4.1.0",
  "font_url": "https://example.com/the-font"
}
```

`tags` come from `schema/keys.json` ▸ `tags` (one to five): the ones
a machine can't judge. Tags like dark, glass or rounded
(`auto_tags`) are added from the look file by CI, so don't list them.
`keywords` (optional, up to five) are for search only. `inspired_by`
(optional) names a palette from `schema/keys.json` ▸ `inspired_by`;
describe, never claim an official port.
`submitted_by` must be your GitHub account: it decides who may update
or remove the look. The submission bot also records `submitted_by_id`,
your account's number, so a renamed account keeps its looks. `font_url` only for a font macOS doesn't ship.

## Check before you push

```sh
python3 -m unittest discover tests
python3 scripts/lookcheck.py
```

Don't edit `index.json` or `stats.json`: CI rebuilds them after each
merge and once a day.

## Likes and downloads

After a merge, CI puts each look's file on the `looks` release, where
GitHub counts its downloads, and opens one discussion per look in the
"Looks" category, where each account that leaves a positive reaction
counts as one like (👎 and 😕 never count).

## Review

I review every look before it goes live. CI warns me when a look is
very close to one already here, to one still waiting for review, or
to one that was removed; that's a
prompt to look closer, never an automatic verdict.

By submitting, you share your look under [CC BY 4.0](LICENSE) and
follow the [code of conduct](CODE_OF_CONDUCT.md).

## The key list

`schema/keys.json` mirrors KiwiDesk's own list of look settings
(`LookKeys` and `ColorPaletteKeys`). When KiwiDesk adds a look setting,
that file gains it in the same release.
