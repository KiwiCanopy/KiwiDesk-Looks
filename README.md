<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)"
    srcset=".github/assets/dark_logo_wordmark.png">
  <img src=".github/assets/logo_wordmark.png" alt="KiwiDesk" width="220">
</picture>

### Your desk, in someone else's clothes.

**Try a look someone else made, or share your own.** A look is the
colors, bars, glass, gaps, font and focus border KiwiDesk draws.

<br>

[![Validate](https://github.com/KiwiCanopy/KiwiDesk-Looks/actions/workflows/validate.yml/badge.svg)](https://github.com/KiwiCanopy/KiwiDesk-Looks/actions/workflows/validate.yml)
[![License CC BY 4.0](https://img.shields.io/badge/Looks-CC_BY_4.0-8DB354)](LICENSE)
[![KiwiDesk](https://img.shields.io/badge/KiwiDesk-macOS-000000?logo=apple&logoColor=white)](https://github.com/KiwiCanopy/KiwiDesk)

[KiwiDesk](https://github.com/KiwiCanopy/KiwiDesk) · [Website](https://kiwidesk.kiwicanopy.com/) · [Submit a look](../../issues/new?template=submit-look.yml) · [Report a look](../../issues/new?template=report-look.yml)

</div>

## Get a look

Every look lives in its own folder under [`looks/`](looks/). Open one,
download its `look.json`, then in KiwiDesk go to **Settings ▸ Looks &
Animations ▸ Import…** and pick the file.

Importing only adds the look to **My looks**, under a name that
doesn't clash with yours. Nothing changes on your desk until you
apply it, and you can delete it there like any look you saved
yourself.

> The gallery page on the KiwiDesk website, with search, tags and a
> one-click **Get**, is on its way. Until it opens, this folder is the
> gallery.

## Share yours

1. Style your desk in KiwiDesk, then choose **Save current look as…**.
2. Right-click the saved look and choose **Export…**.
3. Open [**Submit a look**](../../issues/new?template=submit-look.yml),
   paste the file's contents, add a screenshot if you like, and send it.

A bot checks the file and turns your submission into a pull request.
I look at every one before it goes live. No screenshot? CI draws a
preview of your look the way KiwiDesk itself does.

If you'd rather use git, open a pull request that adds a folder under
`looks/` — see [CONTRIBUTING.md](CONTRIBUTING.md).

Submitting needs a GitHub account. Getting a look doesn't.

## Credit

Every look names who made it. In an upcoming KiwiDesk release, a look
you start from someone else's will keep their credit while at least
half of its settings are unchanged, and read "based on Dusk by Anna".
Start from one of the looks bundled with KiwiDesk and the look is
yours alone.

## Changing or removing your look

Submit it again under the same name from the same GitHub account, and
it updates in place. To take it down, use
[**Remove my look**](../../issues/new?template=remove-look.yml); you
can ask for your name to come off the looks built on it too.

Removing a look stops new downloads. Copies people already have stay
theirs, because an install is a copy and CC BY can't be taken back.

## Only data, never code

A look file holds settings and colors, nothing else. KiwiDesk reads
each value through its own setters and drops anything it doesn't
know, so a look can change how your desk looks but can never run
anything. Lua configs don't belong here.

## What's in a folder

```
looks/purple-dreams/
├── look.json        the exported look
├── meta.json        tags, a one-line description, optional font link
├── screenshot.png   optional
└── preview.png      drawn by CI when there is no screenshot
```

CI checks every file on each pull request and rebuilds
[`index.json`](index.json), which the gallery page will read.

## License

Every look here is shared under [CC BY 4.0](LICENSE): use it freely,
and credit its author when you pass it on. The KiwiDesk name and logo
are not part of that license. The tooling in `scripts/` and
`.github/` is MIT ([LICENSE-CODE](LICENSE-CODE)).
