"""Tags CI reads from a look file, and the contrast check.

Automatic tags are facts of the file, so nobody ticks them: the
submitter only picks the tags a machine cannot judge (schema/keys.json
▸ tags). Thresholds live here and nowhere else.
"""

import colorsys

ROUNDED_AT = 50       # kiwishelf.corner_roundness, 0-100
SLIM_AT = 30          # kiwishelf.thickness in points, inclusive
MONOCHROME_AT = 0.12  # HSV saturation every colour stays at or under
HIGH_CONTRAST_AT = 7.0
# schema/keys.json ▸ auto_tags holds the same list (a test pins it).
ORDER = ["dark", "light", "glass", "boxed", "glow", "rounded", "square",
         "vertical", "bottom", "slim", "gapless", "monochrome"]


def rgb(hex_color):
    """(r, g, b) in 0-1 from #RRGGBB or #RRGGBBAA, alpha dropped."""
    if not isinstance(hex_color, str) or len(hex_color) not in (7, 9):
        return None
    try:
        return tuple(int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    except ValueError:
        return None


def luminance(color):
    def channel(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in color)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(look):
    """WCAG contrast between the bar's text and its fill, or None."""
    colors = (look.get("look") or {}).get("colors") or {}
    text = rgb(colors.get("kiwishelf.item_color"))
    fill = rgb(colors.get("kiwishelf.fill_color"))
    if text is None or fill is None:
        return None
    high, low = sorted((luminance(text), luminance(fill)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def auto_tags(look):
    """The schema's auto_tags this look earns, in schema order."""
    body = look.get("look") or {}
    style = body.get("style") or {}
    colors = body.get("colors") or {}
    tags = set()
    fill = rgb(colors.get("kiwishelf.fill_color"))
    if fill is not None:
        tags.add("dark" if luminance(fill) < 0.5 else "light")
    if style.get("kiwishelf.liquid_glass") is True:
        tags.add("glass")
    if style.get("kiwishelf.background_style") == "boxed":
        tags.add("boxed")
    if style.get("border.glow") is True:
        tags.add("glow")
    roundness = style.get("kiwishelf.corner_roundness")
    if isinstance(roundness, (int, float)) and roundness >= ROUNDED_AT:
        tags.add("rounded")
    if style.get("border.corner_style") == "square":
        tags.add("square")
    edges = {style.get("space_bar.edge"), style.get("app_bar.edge")}
    if edges & {"left", "right"}:
        tags.add("vertical")
    if "bottom" in edges:
        tags.add("bottom")
    thickness = style.get("kiwishelf.thickness")
    if isinstance(thickness, (int, float)) and 0 < thickness <= SLIM_AT:
        tags.add("slim")
    gaps = style.get("gap.global")
    if isinstance(gaps, dict) and all(
            value == 0 for group in gaps.values() if isinstance(group, dict)
            for value in group.values()):
        tags.add("gapless")
    painted = [rgb(v) for v in colors.values() if rgb(v) is not None]
    if painted and all(colorsys.rgb_to_hsv(*c)[1] <= MONOCHROME_AT
                       for c in painted):
        tags.add("monochrome")
    return [tag for tag in ORDER if tag in tags]
