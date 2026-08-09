#!/usr/bin/env python3
"""Guards what the site *claims*, as opposed to how it is worded.

`test_site_positioning.py` checks one string against another. These tests
check something harder to see in a diff: whether the pages assert things that
are not true, that overreach the record, or that quietly contradict each other.

Three classes of defect are covered, all of them found in a real review rather
than imagined:

  * **A retired claim coming back.** The document-intelligence re-architecture
    was driven by input format — image submissions defeated OCR. An earlier
    draft attributed it to a data-classification review instead. That is both
    the wrong cause and a far more sensitive statement to publish under a named
    employer, so the phrasing is banned outright rather than left to memory.
  * **Two pages telling different stories.** index.html and resume.html are one
    click apart and a reader opens both. When they disagreed about why the
    pipeline was rebuilt, whichever page a reader believed, the other one
    looked written-to-impress. Consistency is asserted, not assumed.
  * **Skill chips that outrun the record.** A bare tag in a skills table reads
    as "I ship this." LangChain was a hackathon prototype and the Kubernetes
    is OpenShift from 2017–2019, so neither may stand unqualified.

The resume PDF is checked too, and that is new. It is the highest-distribution
artifact here — it goes into ATS parsers and gets forwarded beyond his control
— and until now it was the least governed: no workflow watched `images/` at
all. It is a Google Docs export with subsetted fonts, so see `pdftext.py` for
why reading it takes more than a substring search.

Stdlib only and fully offline. Run from the repo root:

    python3 -m unittest discover -s tests -p 'test_*.py'
"""

import re
import unittest
from pathlib import Path

from pdftext import extract_text

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "images" / "Jonathan Reyes Resume.pdf"

LIVE_PAGES = ["index.html", "resume.html", "contact.html", "docs/index.html"]

# Dealership networks the platform dispatches to. None has ever appeared on the
# site; this is a regression guard, not a cleanup.
PARTNER_NAMES = ["RouteOne", "DealerTrack", "Dealertrack", "CarMax",
                 "Carvana", "Cox Automotive"]

# Wordings that were removed on purpose and must not return. Keyed by a short
# name so the PDF-lag test below can talk about them.
RETIRED_CLAIMS = {
    "wrong-cause": re.compile(r"data\s+classification\s+surfaced", re.I),
    "langchain-skill": re.compile(r"\bLangChain\s*\(RAG\)", re.I),
}

# The resume PDF is exported from Google Docs by hand, so it lags the pages
# whenever a claim changes. This pins exactly how far it lags: the test fails
# if a *new* retired claim shows up in it, and it also fails once the PDF is
# regenerated — at which point this set should shrink to empty and then be
# deleted along with the test. It is a ratchet, not a permanent exemption.
KNOWN_PDF_LAG = {"wrong-cause", "langchain-skill"}

_CHIP = re.compile(r"<code[^>]*>(.*?)</code>", re.S)


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def skill_chips(page):
    """The <code> tags inside the skills table rows, which read as claims."""
    chips = []
    for row in re.findall(r'<div class="v">(.*?)</div>', read(page), re.S):
        chips += [re.sub(r"\s+", " ", c).strip() for c in _CHIP.findall(row)]
    return chips


class RetiredClaimsStayRetired(unittest.TestCase):

    def test_no_live_page_attributes_the_rebuild_to_data_classification(self):
        # The real driver was input format. Beyond being inaccurate, this
        # phrasing has a named bank employee publicly describing what a data
        # classification review found inside a production system he owns.
        pattern = RETIRED_CLAIMS["wrong-cause"]
        for page in LIVE_PAGES:
            with self.subTest(page=page):
                hit = pattern.search(read(page))
                self.assertIsNone(
                    hit, f"{page}: the re-architecture is attributed to a "
                         "data-classification review again. The driver was "
                         "image submissions defeating OCR; the classification "
                         "work is a separate accomplishment and belongs in its "
                         "own sentence.")

    def test_skills_tables_do_not_claim_langchain_or_bare_kubernetes(self):
        # A bare chip in a skills table reads as "I ship this". LangChain was
        # an internal hackathon prototype, and the Kubernetes is OpenShift at
        # IBM in 2017–2019, which the IBM role entry already dates.
        chips = skill_chips("resume.html")
        self.assertTrue(chips, "resume.html skills chips not found — regex broke")

        # Substring, not list membership. Checking `"LangChain" not in chips`
        # compares whole elements, so the chip that actually shipped —
        # "LangChain (RAG)" — sailed straight through the first version of
        # this test. A guard that only catches the exact wording you already
        # removed is not a guard.
        langchain = [c for c in chips if "langchain" in c.lower()]
        self.assertEqual(
            langchain, [],
            f"resume.html claims LangChain as a skill ({langchain}); it was an "
            "internal hackathon prototype and was never shipped. The honest "
            "version of this claim lives in the contact.html FAQ.")

        # "OpenShift (Kubernetes)" is fine — it is qualified, and the IBM role
        # entry dates it. A chip that *leads* with Kubernetes is the claim of
        # current EKS work, which is not the record: the platform runs on ECS.
        bare_k8s = [c for c in chips if re.match(r"kubernetes\b", c, re.I)]
        self.assertEqual(
            bare_k8s, [],
            f"resume.html lists Kubernetes unqualified ({bare_k8s}). The "
            "experience is OpenShift at IBM, 2017–2019; the current platform "
            "is ECS. Write it as 'OpenShift (Kubernetes)'.")


class PagesAgreeWithEachOther(unittest.TestCase):

    def test_index_and_resume_give_the_same_cause_for_the_rebuild(self):
        # These two pages are one click apart and a reader opens both. When
        # they disagreed, one of them necessarily looked written to impress.
        for page in ("index.html", "resume.html"):
            with self.subTest(page=page):
                html = read(page)
                self.assertRegex(
                    html, r"(image-based|phone-camera)\s+submissions",
                    f"{page}: no longer says image submissions defeated OCR. "
                    "Both pages must give the same cause for the rebuild.")

    def test_no_page_advertises_availability_in_an_indexed_banner(self):
        # A public "I am looking" line, attached to a named employer and a
        # component-level description of its production platform, is the one
        # artifact on this site with a cost measured in something other than
        # interviews. The contact page's role spec says the same thing to
        # someone who has already chosen to land there.
        for page in LIVE_PAGES:
            with self.subTest(page=page):
                self.assertNotRegex(
                    read(page), r"Open to\s+(lead|principal|senior|new)\b",
                    f"{page}: carries a public availability banner.")


class ProprietaryDetailStaysOut(unittest.TestCase):
    """Severance-risk scrubbing, asserted rather than remembered."""

    def test_no_partner_is_named(self):
        for page in LIVE_PAGES:
            for name in PARTNER_NAMES:
                with self.subTest(page=page, partner=name):
                    self.assertNotIn(name, read(page),
                                     f"{page}: names dispatch partner {name}")

    def test_no_page_states_an_input_mix_ratio(self):
        # "A fifth of submissions arrived as phone-camera photos" is an
        # unpublished operational statistic about an employer's pipeline. The
        # qualitative form makes the same point and discloses nothing.
        ratio = re.compile(
            r"\b(a (fifth|third|quarter|half)|\d{1,3}\s*(%|percent))\s+of\s+"
            r"(the\s+)?(submissions|documents|requests|applications)", re.I)
        for page in LIVE_PAGES:
            with self.subTest(page=page):
                hit = ratio.search(read(page))
                self.assertIsNone(
                    hit, f"{page}: states an input-mix ratio "
                         f"({hit.group(0)!r} ) — prefer qualitative framing"
                         if hit else "")


class ResumePdfIsGoverned(unittest.TestCase):
    """The PDF had no test at all before this, and no workflow watched it."""

    @classmethod
    def setUpClass(cls):
        cls.text = extract_text(PDF)

    def test_header_carries_the_headline_and_the_entry_carries_the_title(self):
        # The same distinction test_site_positioning.py guards on the pages.
        self.assertIn("AI LEAD SOFTWARE ENGINEER", self.text.upper())
        self.assertIn("Lead Software Engineer | CAPITAL ONE", self.text)

    def test_no_partner_is_named(self):
        for name in PARTNER_NAMES:
            with self.subTest(partner=name):
                self.assertNotIn(name, self.text)

    def test_pdf_lag_behind_the_pages_is_exactly_the_known_set(self):
        """Pins how far the hand-exported PDF trails the corrected pages.

        Fails two ways, both of them wanted. A retired claim appearing in a
        fresh export fails immediately. And once the PDF is regenerated from
        the Google Doc, the stale set shrinks and this fails too — which is
        the prompt to empty `KNOWN_PDF_LAG` and delete this test.
        """
        stale = {name for name, pattern in RETIRED_CLAIMS.items()
                 if pattern.search(self.text)}
        self.assertEqual(
            stale, KNOWN_PDF_LAG,
            "the resume PDF's known lag has changed.\n"
            f"  still stale: {sorted(stale) or '(none)'}\n"
            f"  expected:    {sorted(KNOWN_PDF_LAG)}\n"
            "If you just regenerated the PDF from the Google Doc: empty "
            "KNOWN_PDF_LAG and delete this test, the ratchet has done its "
            "job. If a retired claim came back, fix the source document — "
            "the PDF is what gets forwarded.")


if __name__ == "__main__":
    unittest.main()
