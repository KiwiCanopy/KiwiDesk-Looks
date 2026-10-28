"""Tests for the gallery scripts. Run: python3 -m unittest discover tests"""

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import build_index  # noqa: E402
import lookcheck  # noqa: E402
import looksim  # noqa: E402
import submission  # noqa: E402

LOOK = {
    "format": 2,
    "author": "Anna",
    "look": {
        "name": "Dusk",
        "style": {
            "kiwishelf.thickness": 40,
            "kiwishelf.liquid_glass": True,
            "kiwishelf.font_family": "Avenir Next",
            "border.sheen": -0.3,
            "border.corner_style": "rounded",
            "gap.global": {
                "inner": {"horizontal": 8, "vertical": 8},
                "outer": {"top": 8, "bottom": 8, "left": 8, "right": 8},
            },
        },
        "colors": {
            "kiwishelf.fill_color": "#1A1A2EA5",
            "border.focused_color": "#564AB6",
            "sticky.color": "",
        },
    },
}
META = {"tags": ["dark", "glass"], "description": "A calm violet evening.",
        "submitted_by": "anna"}


def write_folder(root, ident, look=None, meta=None):
    folder = Path(root) / ident
    folder.mkdir(parents=True)
    (folder / "look.json").write_text(json.dumps(look or LOOK))
    (folder / "meta.json").write_text(json.dumps(meta or META))
    return folder


class LookcheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def errors(self, look=None, meta=None, ident="dusk"):
        return lookcheck.check_folder(
            write_folder(self.root, ident, look, meta))

    def broken(self, edit):
        look = copy.deepcopy(LOOK)
        edit(look)
        return self.errors(look)

    def test_valid_folder_passes(self):
        self.assertEqual(self.errors(), [])

    def test_unknown_style_key_is_refused(self):
        errs = self.broken(lambda l: l["look"]["style"].update(
            {"space_bar.visibility": "always"}))
        self.assertIn("style space_bar.visibility is not a look setting", errs)

    def test_lua_or_code_cannot_ride_in(self):
        errs = self.broken(lambda l: l.update({"init_lua": "os.execute()"}))
        self.assertIn("look.json has an unknown key: init_lua", errs)

    def test_wrong_value_types_are_refused(self):
        def edit(look):
            look["look"]["style"]["kiwishelf.liquid_glass"] = "yes"
            look["look"]["style"]["border.corner_style"] = "wavy"
            look["look"]["style"]["kiwishelf.thickness"] = 900
        errs = self.broken(edit)
        self.assertEqual(len(errs), 3, errs)

    def test_bad_colors_are_refused_but_automatic_may_be_empty(self):
        errs = self.broken(lambda l: l["look"]["colors"].update(
            {"border.focused_color": "", "kiwishelf.item_color": "red"}))
        self.assertEqual(len(errs), 2, errs)

    def test_newer_format_is_refused(self):
        errs = self.broken(lambda l: l.update({"format": 99}))
        self.assertTrue(any("newer" in e for e in errs), errs)

    def test_missing_author_is_refused(self):
        errs = self.broken(lambda l: l.pop("author"))
        self.assertIn("author must be a non-empty string", errs)

    def test_bundled_name_is_refused(self):
        def edit(look):
            look["look"]["name"] = "Tiler"
        look = copy.deepcopy(LOOK)
        edit(look)
        errs = self.errors(look, ident="tiler")
        self.assertTrue(any("bundled" in e for e in errs), errs)

    def test_folder_must_match_name(self):
        errs = self.errors(ident="something-else")
        self.assertTrue(any("'dusk'" in e for e in errs), errs)

    def test_links_and_markup_in_text_are_refused(self):
        meta = dict(META, description="<script>x</script>")
        self.assertIn("description must not contain links or markup",
                      self.errors(meta=meta))

    def test_tags_must_be_known(self):
        meta = dict(META, tags=["dark", "spicy"])
        self.assertIn("unknown tag: spicy", self.errors(meta=meta))

    def test_font_url_must_be_https(self):
        meta = dict(META, font_url="http://fonts.example/x")
        self.assertIn("font_url must be a single https:// link",
                      self.errors(meta=meta))

    def test_extra_files_are_refused(self):
        folder = write_folder(self.root, "dusk")
        (folder / "init.lua").write_text("print(1)")
        self.assertIn("unexpected file: init.lua",
                      lookcheck.check_folder(folder))

    def test_non_png_screenshot_is_refused(self):
        folder = write_folder(self.root, "dusk")
        (folder / "screenshot.png").write_bytes(b"GIF89a....")
        self.assertIn("screenshot.png is not a PNG image",
                      lookcheck.check_folder(folder))

    def test_removed_based_on_is_allowed(self):
        self.assertEqual(
            self.broken(lambda l: l.update({"based_on": {"removed": True}})),
            [])

    def test_needs_fonts_lists_only_non_macos_fonts(self):
        self.assertEqual(lookcheck.needs_fonts(LOOK), [])
        look = copy.deepcopy(LOOK)
        look["look"]["style"]["kiwishelf.font_family"] = "Comic Neue"
        self.assertEqual(lookcheck.needs_fonts(look), ["Comic Neue"])

    def test_slug(self):
        self.assertEqual(lookcheck.slug("Black & White Tiler"),
                         "black-and-white-tiler")
        self.assertEqual(lookcheck.slug("Purple Dreams"), "purple-dreams")


class SimilarityTests(unittest.TestCase):
    def test_match_counts_only_the_originals_settings(self):
        candidate = copy.deepcopy(LOOK)
        candidate["look"]["style"]["kiwishelf.order"] = "apps_first"
        self.assertEqual(looksim.match(candidate, LOOK), 1.0)

    def test_match_drops_with_each_change(self):
        candidate = copy.deepcopy(LOOK)
        candidate["look"]["style"]["kiwishelf.thickness"] = 30
        candidate["look"]["colors"]["border.focused_color"] = "#000000"
        self.assertAlmostEqual(looksim.match(candidate, LOOK), 7 / 9)

    def test_color_case_does_not_count_as_a_change(self):
        candidate = copy.deepcopy(LOOK)
        candidate["look"]["colors"]["border.focused_color"] = "#564ab6"
        self.assertEqual(looksim.match(candidate, LOOK), 1.0)


class GalleryTestCase(unittest.TestCase):
    """Points every script at a scratch gallery."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.looks = self.root / "looks"
        self.looks.mkdir()
        self.saved = (submission.ROOT, submission.LOOKS, looksim.ROOT)
        submission.ROOT = self.root
        submission.LOOKS = self.looks
        looksim.ROOT = self.root

    def tearDown(self):
        submission.ROOT, submission.LOOKS, looksim.ROOT = self.saved
        self.tmp.cleanup()


def form(look, **extra):
    fields = {
        submission.F_LOOK: "```json\n" + json.dumps(look) + "\n```",
        submission.F_AUTHOR: "",
        submission.F_TAGS: "- [x] dark\n- [ ] light\n- [x] glass",
        submission.F_DESCRIPTION: "A calm violet evening.",
        submission.F_SCREENSHOT: "",
    }
    fields.update(extra)
    return fields


def no_fetch(text, target):
    return None


class SubmissionTests(GalleryTestCase):
    def exported(self):
        """What KiwiDesk's Export… writes today: the look, bare."""
        return {"look": copy.deepcopy(LOOK["look"])}

    def test_sections_parse_an_issue_form_body(self):
        body = "### Look file\n\n```json\n{}\n```\n\n### Font download link\n\n_No response_\n"
        fields = submission.sections(body)
        self.assertEqual(fields["Look file"], "```json\n{}\n```")
        self.assertEqual(fields["Font download link"], "")

    def test_bare_export_is_stamped_and_added(self):
        result = submission.submit(form(self.exported()), "maya", no_fetch)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["action"], "add")
        look = json.loads((self.looks / "dusk" / "look.json").read_text())
        self.assertEqual(look["format"], 2)
        self.assertEqual(look["author"], "maya")
        meta = json.loads((self.looks / "dusk" / "meta.json").read_text())
        self.assertEqual(meta["tags"], ["dark", "glass"])
        self.assertEqual(meta["submitted_by"], "maya")

    def test_invalid_submission_reports_and_writes_nothing(self):
        bad = self.exported()
        bad["look"]["style"]["space_bar.visibility"] = "never"
        result = submission.submit(form(bad), "maya", no_fetch)
        self.assertFalse(result["ok"])
        self.assertIn("not a look setting", result["message"])
        self.assertEqual(list(self.looks.iterdir()), [])

    def test_same_account_updates_other_account_is_refused(self):
        submission.submit(form(self.exported()), "maya", no_fetch)
        again = submission.submit(form(self.exported()), "Maya", no_fetch)
        self.assertEqual(again["action"], "update")
        stranger = submission.submit(form(self.exported()), "otto", no_fetch)
        self.assertFalse(stranger["ok"])
        self.assertIn("already exists", stranger["message"])

    def test_based_on_a_gallery_id_links_the_original(self):
        submission.submit(form(self.exported()), "anna", no_fetch)
        mine = self.exported()
        mine["look"]["name"] = "Dusk Remix"
        result = submission.submit(
            form(mine, **{submission.F_BASED_ON: "dusk"}), "maya", no_fetch)
        self.assertTrue(result["ok"], result)
        look = json.loads((self.looks / "dusk-remix" / "look.json")
                          .read_text())
        self.assertEqual(look["based_on"],
                         {"name": "Dusk", "author": "anna", "id": "dusk"})
        self.assertIn("dusk: 100%", result["close"])

    def test_based_on_free_text_credits_by_name(self):
        based = submission.parse_based_on("Dusk by Anna")
        self.assertEqual(based, {"name": "Dusk", "author": "Anna"})

    def test_screenshot_error_is_reported(self):
        def fetch(text, target):
            return "the screenshot must be a PNG image"
        result = submission.submit(form(self.exported()), "maya", fetch)
        self.assertFalse(result["ok"])
        self.assertIn("PNG", result["message"])

    def test_remove_by_owner_and_drop_name(self):
        submission.submit(form(self.exported()), "anna", no_fetch)
        mine = self.exported()
        mine["look"]["name"] = "Dusk Remix"
        submission.submit(form(mine, **{submission.F_BASED_ON: "dusk"}),
                          "maya", no_fetch)
        stranger = submission.remove({submission.F_REMOVE_ID: "dusk"}, "otto")
        self.assertFalse(stranger["ok"])
        result = submission.remove(
            {submission.F_REMOVE_ID: "dusk",
             submission.F_REMOVE_NAME: "- [x] Also remove my name"},
            "anna")
        self.assertTrue(result["ok"], result)
        self.assertFalse((self.looks / "dusk").exists())
        remix = json.loads((self.looks / "dusk-remix" / "look.json")
                           .read_text())
        self.assertEqual(remix["based_on"], {"removed": True})


class IndexTests(GalleryTestCase):
    def test_index_lists_looks_and_reverse_credits(self):
        write_folder(self.looks, "dusk")
        remix = copy.deepcopy(LOOK)
        remix["look"]["name"] = "Dusk Remix"
        remix["based_on"] = {"name": "Dusk", "author": "Anna", "id": "dusk"}
        write_folder(self.looks, "dusk-remix", remix)
        index = build_index.build(self.looks)
        by_id = {look["id"]: look for look in index["looks"]}
        self.assertEqual(by_id["dusk"]["built_on"], ["dusk-remix"])
        self.assertEqual(by_id["dusk"]["needs_fonts"], [])
        self.assertIsNone(by_id["dusk"]["image"])
        self.assertEqual(build_index.render(index),
                         build_index.render(build_index.build(self.looks)))

    def test_index_refuses_an_invalid_folder(self):
        bad = copy.deepcopy(LOOK)
        bad.pop("author")
        write_folder(self.looks, "dusk", bad)
        with self.assertRaises(ValueError):
            build_index.build(self.looks)


class ReviewFixTests(GalleryTestCase):
    def exported(self, name="Dusk"):
        body = copy.deepcopy(LOOK["look"])
        body["name"] = name
        return {"look": body}

    def test_non_latin_name_gets_a_stable_id(self):
        ident = lookcheck.slug("夜")
        self.assertTrue(lookcheck.ID.match(ident), ident)
        self.assertEqual(ident, lookcheck.slug("夜"))
        result = submission.submit(form(self.exported("夜")), "maya", no_fetch)
        self.assertTrue(result["ok"], result)

    def test_bundled_name_is_refused_by_slug(self):
        result = submission.submit(form(self.exported("Glass!")), "maya",
                                   no_fetch)
        self.assertFalse(result["ok"])
        self.assertIn("bundled", result["message"])

    def test_echoed_text_lands_in_a_code_block(self):
        bad = self.exported()
        bad["look"]["style"]["@everyone `x`"] = 1
        result = submission.submit(form(bad), "maya", no_fetch)
        self.assertTrue(result["message"].startswith("```text\n"))
        self.assertEqual(result["message"].count("```"), 2)

    def test_account_number_beats_a_reclaimed_login(self):
        submission.submit(form(self.exported()), "anna", no_fetch, account=7)
        thief = submission.submit(form(self.exported()), "anna", no_fetch,
                                  account=8)
        self.assertFalse(thief["ok"])
        owner = submission.submit(form(self.exported()), "anna-renamed",
                                  no_fetch, account=7)
        self.assertEqual(owner["action"], "update")
        self.assertFalse(submission.remove(
            {submission.F_REMOVE_ID: "dusk"}, "anna", 8)["ok"])

    def test_failed_download_is_a_message_not_a_crash(self):
        text = ("https://github.com/user-attachments/assets/"
                "00000000-0000-0000-0000-000000000000")
        import urllib.request
        saved = urllib.request.urlopen

        def refuse(*args, **kwargs):
            raise OSError("offline")
        urllib.request.urlopen = refuse
        try:
            error = submission.download_screenshot(
                text, self.root / "shot.png")
        finally:
            urllib.request.urlopen = saved
        self.assertIn("couldn't be downloaded", error)

    def test_tiny_original_never_warns(self):
        tiny = {"look": {"name": "T", "style": {"border.width": 4},
                         "colors": {}}}
        self.assertEqual(looksim.match(tiny, tiny), 0.0)


class PendingTests(unittest.TestCase):
    """Two submissions waiting for review see each other."""

    def setUp(self):
        import subprocess
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.run = lambda *a, cwd=None: subprocess.run(
            ["git", *a], cwd=cwd, check=True, capture_output=True)
        self.run("init", "-q", "--bare", str(base / "origin.git"))
        self.repo = base / "repo"
        self.run("clone", "-q", str(base / "origin.git"), str(self.repo))
        for key, value in (("user.name", "t"), ("user.email", "t@t")):
            self.run("config", key, value, cwd=self.repo)
        (self.repo / "looks").mkdir()
        (self.repo / "looks" / ".gitkeep").write_text("")
        self.run("add", ".", cwd=self.repo)
        self.run("commit", "-qm", "init", cwd=self.repo)
        self.run("push", "-q", "origin", "HEAD:main", cwd=self.repo)
        self.run("checkout", "-qb", "submission/dusk", cwd=self.repo)
        write_folder(self.repo / "looks", "dusk")
        self.run("add", ".", cwd=self.repo)
        self.run("commit", "-qm", "dusk", cwd=self.repo)
        self.run("push", "-q", "origin", "submission/dusk", cwd=self.repo)
        self.run("checkout", "-q", "main", cwd=self.repo)
        self.saved = looksim.ROOT
        looksim.ROOT = self.repo

    def tearDown(self):
        looksim.ROOT = self.saved
        self.tmp.cleanup()

    def test_a_waiting_submission_is_compared(self):
        hits = looksim.close_matches(copy.deepcopy(LOOK), skip="dusk-again")
        self.assertEqual([(i, k) for i, _, k in hits],
                         [("dusk", looksim.PENDING)])

    def test_its_own_branch_is_skipped(self):
        self.assertEqual(looksim.close_matches(copy.deepcopy(LOOK),
                                               skip="dusk"), [])

    def test_a_merged_branch_counts_once_as_current(self):
        write_folder(self.repo / "looks", "dusk")
        hits = looksim.close_matches(copy.deepcopy(LOOK), skip="other")
        self.assertEqual([(i, k) for i, _, k in hits],
                         [("dusk", looksim.CURRENT)])


class FormLabelTests(unittest.TestCase):
    """submission.py reads the forms by label, so a renamed label in
    .github/ISSUE_TEMPLATE would silently empty that field."""

    def labels(self, name):
        path = (Path(__file__).resolve().parent.parent / ".github"
                / "ISSUE_TEMPLATE" / name)
        import re
        return set(re.findall(r"^      label: (.+)$", path.read_text(), re.M))

    def test_submit_form_carries_every_label_the_script_reads(self):
        wanted = {submission.F_LOOK, submission.F_AUTHOR,
                  submission.F_BASED_ON, submission.F_TAGS,
                  submission.F_DESCRIPTION, submission.F_FONT_URL,
                  submission.F_VERSION, submission.F_SCREENSHOT}
        self.assertLessEqual(wanted, self.labels("submit-look.yml"))

    def test_remove_form_carries_every_label_the_script_reads(self):
        wanted = {submission.F_REMOVE_ID, submission.F_REMOVE_NAME}
        self.assertLessEqual(wanted, self.labels("remove-look.yml"))

    def test_tag_options_are_the_schema_tags(self):
        path = (Path(__file__).resolve().parent.parent / ".github"
                / "ISSUE_TEMPLATE" / "submit-look.yml")
        text = path.read_text().split("id: tags", 1)[1].split("- type:", 1)[0]
        import re
        options = re.findall(r"- label: (.+)$", text, re.M)
        self.assertEqual(options, lookcheck.SCHEMA["tags"])


if __name__ == "__main__":
    unittest.main()
