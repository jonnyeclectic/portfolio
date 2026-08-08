#!/usr/bin/env python3
"""Guards the one distinction the site makes about Jonathan's title.

There are two different claims on these pages that read almost identically:

  * the *headline* — how he positions himself, which is "AI Lead Software
    Engineer". It appears in the hero badge, the footer byline on every page,
    the cerebro project byline, and two meta descriptions.
  * the *employer job title* — what Capital One actually calls the role, which
    is "Lead Software Engineer", plain. It appears as the role heading in the
    experience timeline on index.html and resume.html.

The resume PDF keeps them apart for a reason: the header reads "AI LEAD
SOFTWARE ENGINEER" while the experience entry reads "Lead Software Engineer |
CAPITAL ONE". Collapsing the two would turn a self-description into a claim
about what an employer conferred, on a page recruiters check.

A site-wide find-and-replace is the obvious way to break this, and it would
look completely reasonable in a diff. Hence these tests.

Stdlib only and fully offline. Run from the repo root:

    python3 -m unittest discover -s tests -p 'test_*.py'
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

HEADLINE = "AI Lead Software Engineer"
ROLE_TITLE = "Lead Software Engineer"

# Every page carrying the shared footer byline. CLAUDE.md requires shared
# components to stay in lockstep across pages, since there is no shared
# stylesheet or template to edit once.
BRAND_PAGES = ["index.html", "resume.html", "contact.html", "docs/index.html"]

CEREBRO_PAGES = sorted(p.name for p in (ROOT / "cerebro").glob("*.html"))

# The redirect stubs are meta-refresh + robots noindex + canonical, so their
# <title> reaches neither a reader nor a crawler. They are deliberately out of
# scope; listed here so the exclusion is a decision rather than an oversight.
LEGACY_STUBS = ["2index.html", "about.html", "m.index.html",
                "portfolio.html", "samplepage.html"]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


class HeadlineIsConsistent(unittest.TestCase):
    """The positioning line must read the same wherever it appears."""

    def test_footer_byline_is_byte_identical_across_pages(self):
        lines = {}
        for page in BRAND_PAGES:
            found = re.findall(r'<p class="brand">.*?</p>', read(page))
            self.assertEqual(
                len(found), 1, f"{page}: expected exactly one .brand line")
            lines[page] = found[0]
        self.assertEqual(
            len(set(lines.values())), 1,
            "footer byline drifted between pages:\n" +
            "\n".join(f"  {k}: {v}" for k, v in lines.items()))
        self.assertIn(HEADLINE, next(iter(lines.values())))

    def test_cerebro_byline_carries_the_headline(self):
        self.assertTrue(CEREBRO_PAGES, "no cerebro pages found — glob broke")
        for page in CEREBRO_PAGES:
            with self.subTest(page=page):
                self.assertIn(
                    f"An independent project by Jonathan Reyes · {HEADLINE}",
                    read(f"cerebro/{page}"))

    def test_hero_badge_carries_the_headline(self):
        badge = re.search(r'<span class="badge">(.*?)</span>', read("index.html"))
        self.assertIsNotNone(badge, "index.html lost its hero badge")
        self.assertTrue(
            badge.group(1).startswith(HEADLINE),
            f"hero badge no longer leads with the headline: {badge.group(1)!r}")

    def test_meta_descriptions_carry_the_headline(self):
        for page in ("resume.html", "contact.html"):
            with self.subTest(page=page):
                meta = re.search(
                    r'<meta name="description" content="(.*?)">', read(page))
                self.assertIsNotNone(meta, f"{page} lost its meta description")
                self.assertIn(HEADLINE, meta.group(1))


class EmployerTitleIsNotInflated(unittest.TestCase):
    """The experience timeline must keep the title Capital One actually gave."""

    def test_capital_one_role_heading_has_no_ai_prefix(self):
        # Both pages render the Feb 2023 – Present role as an <h4>. The PDF
        # spells this "Lead Software Engineer | CAPITAL ONE", and so must we.
        for page in ("index.html", "resume.html"):
            with self.subTest(page=page):
                headings = re.findall(r"<h4>(.*?)</h4>", read(page))
                self.assertIn(
                    ROLE_TITLE, headings,
                    f"{page}: the plain '{ROLE_TITLE}' role heading is gone — "
                    "if a site-wide replace prefixed it with 'AI', revert that; "
                    "the headline and the employer title are different claims")
                self.assertNotIn(
                    HEADLINE, headings,
                    f"{page}: an experience heading now claims the employer "
                    f"title is '{HEADLINE}'. It is not.")

    def test_headline_is_never_bound_to_the_employer(self):
        # "AI Lead Software Engineer · Capital One" would read as an assertion
        # about what Capital One calls him. Nothing may put the two adjacent.
        pattern = re.compile(
            re.escape(HEADLINE) + r"[^<]{0,12}Capital\s*One", re.I)
        pages = BRAND_PAGES + [f"cerebro/{p}" for p in CEREBRO_PAGES]
        for page in pages:
            with self.subTest(page=page):
                hit = pattern.search(read(page))
                self.assertIsNone(
                    hit, f"{page}: headline bound to the employer: "
                         f"{hit.group(0)!r}" if hit else "")


class ScopeIsDeliberate(unittest.TestCase):
    """The pages left alone were left alone on purpose."""

    def test_legacy_stubs_stay_out_of_scope_because_they_are_noindex(self):
        for page in LEGACY_STUBS:
            with self.subTest(page=page):
                html = read(page)
                self.assertIn('name="robots" content="noindex"', html)
                self.assertIn('http-equiv="refresh"', html)


if __name__ == "__main__":
    unittest.main()
