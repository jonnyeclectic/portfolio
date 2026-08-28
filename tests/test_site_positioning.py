#!/usr/bin/env python3
"""Guards the one title distinction the site makes.

There are two different claims on these pages that read almost identically:

  * the headline — the self-description, "AI Lead Software Engineer". It
    appears in the hero badge, the footer byline on every page, the cerebro
    project byline, and two meta descriptions.
  * the job title — "Lead Software Engineer", plain. It appears as the role
    heading in the experience timeline on index.html and resume.html.

The resume PDF keeps them apart: the header reads "AI LEAD SOFTWARE ENGINEER"
while the experience entry reads "Lead Software Engineer | CAPITAL ONE".
Collapsing the two would turn a self-description into a claim about what the
employer conferred.

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
EMPLOYER = r"Capital\s*One"

# Directories that are a vendored W3Layouts template rather than site content.
LEGACY_DIRS = {"mobile", "css", "js", "2images", "node_modules"}

# The redirect stubs are meta-refresh + robots noindex + canonical, so their
# <title> reaches neither a reader nor a crawler. They are deliberately out of
# scope; listed here so the exclusion is a decision rather than an oversight.
LEGACY_STUBS = ["2index.html", "about.html", "m.index.html",
                "portfolio.html", "samplepage.html"]

CEREBRO_PAGES = sorted(p.name for p in (ROOT / "cerebro").glob("*.html"))

_TAG = re.compile(r"<[^>]+>")
_BRAND = re.compile(r'<p class="brand">.*?</p>', re.S)


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def live_pages():
    """Every HTML page that is actually served to a reader.

    Globbed rather than hand-listed. The previous version of this file kept
    a literal list of the pages carrying the footer byline, which meant a page
    added tomorrow was silently uncovered by the strictest test here.
    """
    out = []
    for path in ROOT.rglob("*.html"):
        rel = path.relative_to(ROOT)
        if LEGACY_DIRS & set(rel.parts):
            continue
        if rel.name in LEGACY_STUBS:
            continue
        out.append(rel.as_posix())
    return sorted(out)


def searchable_text(html):
    """Everything a page asserts, flattened — prose *and* metadata.

    Two failure modes to steer between, and the first draft of this hit both.

    Matching raw HTML is what let the old binding test miss almost everything
    it was written to catch: this site writes every byline with markup between
    the parts, so a pattern that cannot span a tag is blind to the site's own
    house style.

    Deleting tags outright is the opposite mistake. It also deletes attribute
    values, and `<meta property="og:title" content="… , Capital One">` is
    precisely the form the claim is most likely to take next — a machine-
    readable assertion aimed at a knowledge panel. So tags are opened out into
    their text rather than dropped: the delimiters become spaces and whatever
    was inside stays searchable, JSON-LD and og tags included.
    """
    return re.sub(r"\s+", " ", html.replace("<", " ").replace(">", " ")).strip()


class HeadlineIsConsistent(unittest.TestCase):
    """The positioning line must read the same wherever it appears."""

    def test_footer_byline_is_byte_identical_across_pages(self):
        lines = {}
        for page in live_pages():
            found = [b for b in _BRAND.findall(read(page))
                     if "Jonathan Reyes" in b]
            if not found:
                continue  # cerebro carries its own project brand, not this one
            self.assertEqual(
                len(found), 1, f"{page}: expected at most one .brand line")
            lines[page] = found[0]
        self.assertGreaterEqual(
            len(lines), 4, "footer byline vanished from the live pages")
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
        # DOTALL plus whitespace collapsing so that reformatting a heading
        # across two lines does not fail a test about its wording.
        for page in ("index.html", "resume.html"):
            with self.subTest(page=page):
                headings = [re.sub(r"\s+", " ", h).strip()
                            for h in re.findall(r"<h4>(.*?)</h4>",
                                                read(page), re.S)]
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
        """Nothing may put the headline and the employer next to each other.

        "AI Lead Software Engineer · Capital One" reads as an assertion about
        what Capital One calls the role, which the resume contradicts.

        Both orderings are checked, on tag-stripped text, because "Capital One
        — AI Lead Software Engineer" is the way a person actually writes a
        title line and the reversed form is no less of a claim.

        The window is deliberately tight. index.html's hero legitimately runs
        the headline badge, then an <h1>, then a lede reading "a lead software
        engineer at Capital One" — lowercase, plain, and correct. That is a
        hundred-odd characters of real prose between the two strings, and it
        is not the defect this guards against. Anything that squeezes them
        into the same phrase is.
        """
        window = 60
        near = re.compile(
            r"(?:%s.{0,%d}?%s|%s.{0,%d}?%s)"
            % (re.escape(HEADLINE), window, EMPLOYER,
               EMPLOYER, window, re.escape(HEADLINE)),
            re.I | re.S)
        for page in live_pages():
            with self.subTest(page=page):
                hit = near.search(searchable_text(read(page)))
                self.assertIsNone(
                    hit, f"{page}: headline bound to the employer: "
                         f"{hit.group(0)!r}" if hit else "")

    def test_binding_guard_actually_catches_the_realistic_mutations(self):
        """The guard above is worthless if its pattern is too narrow.

        An earlier version matched on raw HTML with a 12-character window and
        only one ordering, which let five of these seven through — including
        every form with a tag in the middle, which is how this site writes
        every byline it has. These are the mutations it must catch.
        """
        window = 60
        near = re.compile(
            r"(?:%s.{0,%d}?%s|%s.{0,%d}?%s)"
            % (re.escape(HEADLINE), window, EMPLOYER,
               EMPLOYER, window, re.escape(HEADLINE)),
            re.I | re.S)
        must_catch = [
            f"{HEADLINE} at Capital One",
            f'<meta property="og:title" content="{HEADLINE}, Capital One">',
            f"Capital One — {HEADLINE}",
            f"<b>Jonathan Reyes</b> · {HEADLINE} · <b>Capital One</b>",
            f"<h4>{HEADLINE}</h4><span class='co'>Capital One</span>",
            f"{HEADLINE}, Financial Services — Capital One",
            f'"jobTitle": "{HEADLINE}", "worksFor": {{"name": "Capital One"}}',
        ]
        for sample in must_catch:
            with self.subTest(sample=sample):
                self.assertIsNotNone(
                    near.search(searchable_text(sample)),
                    f"binding guard would not catch: {sample!r}")

        # And it must stay quiet on the hero, which is correct as written.
        hero = ('<span class="badge">AI Lead Software Engineer · Fort Worth, TX '
                '· Remote</span><h1>Production LLM systems <span>and the evals '
                'that keep them honest.</span></h1><p class="lede">I\'m '
                "<b>Jonathan Reyes</b>, a lead software engineer at Capital One.")
        self.assertIsNone(
            near.search(searchable_text(hero)),
            "binding guard fires on the legitimate hero — window is too wide")


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
