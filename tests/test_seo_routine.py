import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.routines import seo_routine as r

HOME = ('<html><head><title>Hi</title><meta name="description" content="D">'
        '<link rel="canonical" href="https://x.test/"><script type="application/ld+json">{"@type":"FAQPage"}</script>'
        '</head><body><h1>Hello</h1></body></html>')


def fake_get(url, **kw):
    pages = {"https://x.test/": HOME, "https://x.test/robots.txt": "User-agent: GPTBot\nUser-agent: ClaudeBot\nDisallow: /\n",
             "https://x.test/sitemap.xml": "<loc>a</loc><lastmod>2026-01-01</lastmod>"}
    return Mock(status_code=200 if url in pages else 404, text=pages.get(url, ""), headers={})


class SeoRoutineTests(unittest.TestCase):
    def test_parse_and_robots(self):
        p = r.parse_page(HOME)
        self.assertEqual((p["title"], p["canonical"], p["jsonld_types"], p["h1"]), ("Hi", "https://x.test/", ["FAQPage"], ["Hello"]))
        self.assertEqual(r.blocked_bots("User-agent: GPTBot\nUser-agent: ClaudeBot\nDisallow: /\nUser-agent: *\nDisallow: /api/"),
                         ["ClaudeBot", "GPTBot"])

    def test_fetch_stays_on_allowed_host(self):
        self.assertIsNone(r.fetch("https://evil.test/", {"x.test"}, fake_get))

    def test_run_writes_drafts_only_and_flags_claims(self):
        site = {"key": "t", "url": "https://x.test", "dir": "t"}
        model = Mock()
        plan = Mock(slug="Good Q!", title="T", question="Q?", why="w", fixes=["f"], geo_actions=["g"], questions=["q"])
        plan.model_dump.return_value = {}
        art = Mock(markdown="# T\n100% placement guarantee")
        model.with_structured_output.side_effect = lambda cls: Mock(invoke=lambda _: plan if cls is r.Plan else art)
        with tempfile.TemporaryDirectory() as d, patch.object(r, "ROOT", Path(d)):
            (Path(d) / "company.json").write_text("{}")
            res = r.run_site(site, model, fake_get)
            self.assertTrue(Path(res["draft"]).read_text().startswith("<!-- DRAFT by Baya"))
            self.assertIn("guarante", res["flags"][0].lower())
            self.assertEqual(res["changes"], ["first snapshot, nothing to compare"])
            second = r.run_site(site, model, fake_get)
            self.assertEqual(second["changes"], [])
            self.assertNotEqual(res["draft"], second["draft"])  # never overwrites

    def test_disabled_by_default(self):
        with patch.dict("os.environ", {}, clear=True), patch.object(r.threading, "Thread") as t:
            r.maybe_run()
            t.assert_not_called()


if __name__ == "__main__":
    unittest.main()
