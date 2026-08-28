#!/usr/bin/env python3
"""Guards what the site claims, as opposed to how it is worded.

`test_site_positioning.py` checks one string against another. These tests
check something harder to see in a diff: whether the pages assert more than
the record supports, or quietly contradict each other.

Three classes of defect are covered:

  * A retired wording returning. Some phrasings are withdrawn on purpose and
    are pinned here rather than left to memory.
  * Two pages telling different stories. index.html and resume.html are one
    click apart and a reader opens both, so agreement between them is
    asserted rather than assumed.
  * Skill chips that outrun the record. A bare tag in a skills table reads as
    a production claim, so some entries have to carry a qualifier.

The resume PDF is held to the same terms. It is a Google Docs export with
subsetted fonts, so see `pdftext.py` for why reading it takes more than a
substring search.

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

# Third-party names that must not appear on the site. None ever has; this is
# a regression guard rather than a cleanup.
PARTNER_NAMES = ["RouteOne", "DealerTrack", "Dealertrack", "CarMax",
                 "Carvana", "Cox Automotive"]

# Wordings that were removed on purpose and must not return. Keyed by a short
# name so the PDF-lag test below can talk about them.
RETIRED_CLAIMS = {
    "wrong-cause": re.compile(r"data\s+classification\s+surfaced", re.I),
    "langchain-skill": re.compile(r"\bLangChain\s*\(RAG\)", re.I),
}

# Phrasings withdrawn from the pages: throughput rates, organisational scope,
# and process detail. These are pinned so an edit cannot reintroduce them.
#
# The throughput rules require an explicit *rate* context rather than banning
# a bare number, because the open-source figures on these pages are meant to
# be here — the eval harness's "10,000-resample paired bootstrap" and boost's
# index of "10,000+ publicly available skills" both read as numbers and both
# must pass. `test_open_source_numbers_are_not_flagged` pins that line.
RESTRICTED_DETAIL = [
    (re.compile(r"\d[\d,.]*\s*\+?\s*(?:requests?|apps?|applications?|events?"
                r"|transactions?|calls?|messages?)\s*(?:/|\s+per\s+)"
                r"\s*(?:hour|hr|min|minute|second|sec|day)", re.I),
     "a throughput rate"),
    (re.compile(r"(?:requests?|apps?|applications?|events?|transactions?|calls?"
                r"|messages?)\s*(?:/|\s+per\s+)\s*(?:hour|hr|min|minute"
                r"|second|sec)", re.I),
     "a throughput rate"),
    # The noun can also precede the number, which the two rules above both
    # miss: they anchor the unit to the noun. Found by the mutation test
    # below rather than by reading.
    (re.compile(r"\d[\d,.]*\s*\+?\s*(?:per|/)\s*"
                r"(?:hour|hr|min|minute|second|sec)", re.I),
     "a throughput rate"),
    (re.compile(r"\b10K\b(?=.{0,40}(?:hour|loan|app))", re.I | re.S),
     "the 10K/hour hero figure"),
    (re.compile(r"loan apps?\s*/", re.I),
     "a throughput figure with the product unit attached"),
    (re.compile(r"every technology organization at", re.I),
     "internal infrastructure scope"),
    (re.compile(r"all communications between", re.I),
     "internal architecture scope — say 'with external dealership partners'"),
    (re.compile(r"dealership marketing targets", re.I),
     "an internal business process"),
]

# The PDF used to lag the pages, and a KNOWN_PDF_LAG set pinned exactly how
# far. It was regenerated from the Google Doc on 2026-08-10 and now carries
# none of the retired wordings, so the ratchet has reached its stop and the
# exemption is gone: the PDF is held to the same standard as the pages.

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
        # The two are separate matters with different consequences, and the
        # withdrawn phrasing welded them together.
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
        # A bare chip in a skills table reads as a production claim. Neither
        # of these is one, so neither may stand unqualified.
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
            f"resume.html lists LangChain as a skill ({langchain}); it needs "
            "the qualifier the contact.html FAQ already gives it.")

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
        # An indexed availability line is not wanted. The contact page's role
        # spec says the same thing to someone who chose to land there.
        for page in LIVE_PAGES:
            with self.subTest(page=page):
                self.assertNotRegex(
                    read(page), r"Open to\s+(lead|principal|senior|new)\b",
                    f"{page}: carries a public availability banner.")


class RestrictedDetailStaysOut(unittest.TestCase):
    """Withdrawn detail, asserted rather than remembered."""

    def test_no_partner_is_named(self):
        for page in LIVE_PAGES:
            for name in PARTNER_NAMES:
                with self.subTest(page=page, partner=name):
                    self.assertNotIn(name, read(page),
                                     f"{page}: names dispatch partner {name}")

    def test_no_page_states_an_input_mix_ratio(self):
        # A stated input mix is an operational statistic. The qualitative
        # form makes the same point.
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


    def test_no_page_carries_restricted_detail(self):
        """None of these had ever been asserted by a test, which is why an
        older copy of the pages kept them long after they were withdrawn."""
        for page in LIVE_PAGES:
            for pattern, why in RESTRICTED_DETAIL:
                with self.subTest(page=page, why=why):
                    hit = pattern.search(read(page))
                    self.assertIsNone(
                        hit, f"{page} states {why}: "
                             f"{hit.group(0)!r}" if hit else "")

    def test_open_source_numbers_are_not_flagged(self):
        """The open-source figures on these pages must pass.

        Not decoration: the first draft of this guard banned a bare "10,000"
        and flagged four of them, which would have made the suite stricter
        than the pages it protects.
        """
        for allowed in [
            "a seeded <b>10,000-resample paired bootstrap</b>, so a regression",
            "paired bootstrap · 10,000 resamples · no significant regression",
            "indexes more than 10,000 publicly available skills",
            "a 70+ command Python CLI with its own MCP server",
        ]:
            for pattern, why in RESTRICTED_DETAIL:
                with self.subTest(allowed=allowed[:40], why=why):
                    self.assertIsNone(
                        pattern.search(allowed),
                        f"guard fires on an open-source figure "
                        f"({why}): {allowed!r}")

    def test_guard_catches_the_withdrawn_wordings(self):
        """Break it on purpose, against the wordings verbatim."""
        for sample in [
            "processing requests at 10,000+ per hour on AWS microservices",
            "processing thousands of loan applications per hour",
            "<b>10K</b><span>Loan apps / hour orchestrated</span>",
            "orchestrating all communications between Capital One, its "
            "dealership partners, and internal messaging systems",
            "the binary repository consumed by every technology organization "
            "at Capital One",
            "findings that analysts use to set dealership marketing targets",
        ]:
            with self.subTest(sample=sample[:50]):
                self.assertTrue(
                    any(p.search(sample) for p, _ in RESTRICTED_DETAIL),
                    f"guard would not catch: {sample!r}")


class ResumePdfIsGoverned(unittest.TestCase):
    """The PDF had no test at all before this, and no workflow watched it.

    It is checked on the same terms as the pages: it is a published artifact
    and cannot be corrected after it has been downloaded.
    """

    @classmethod
    def setUpClass(cls):
        cls.text = extract_text(PDF)

    def test_header_carries_the_headline_and_the_entry_carries_the_title(self):
        # The same distinction test_site_positioning.py guards on the pages.
        self.assertIn("AI LEAD SOFTWARE ENGINEER", self.text.upper())
        self.assertIn("Lead Software Engineer | CAPITAL ONE", self.text)

        # And the entry must not be the *inflated* form. That needs its own
        # assertion because "AI Lead Software Engineer | CAPITAL ONE" contains
        # "Lead Software Engineer | CAPITAL ONE" as a substring, so the
        # assertIn above passes on precisely the mutation it looks like it is
        # guarding. Mutation testing caught this; the identical containment
        # trap had already made the LangChain chip guard vacuous once, which
        # is the argument for breaking every one of these on purpose.
        self.assertIsNone(
            re.search(r"\bAI\s+Lead\s+Software\s+Engineer\s*\|\s*CAPITAL\s+ONE",
                      self.text, re.I),
            "the resume PDF's experience entry now claims Capital One "
            "conferred the title 'AI Lead Software Engineer'. It did not — "
            "that is the headline. Fix the Google Doc and re-export.")

    def test_no_partner_is_named(self):
        for name in PARTNER_NAMES:
            with self.subTest(partner=name):
                self.assertNotIn(name, self.text)

    def test_pdf_carries_no_retired_claim(self):
        """The PDF is held to the same standard as the pages.

        This replaced a ratchet. While the export lagged, the test asserted
        the lag was *exactly* a known set, so a new stale claim failed loudly
        while the two known ones were tolerated. The 2026-08-10 regeneration
        emptied that set, and tolerating nothing is simply the ratchet at its
        stop — the assertion the whole mechanism existed to arrive at.

        A page can be corrected after the fact; a PDF that has already been
        downloaded cannot.
        """
        stale = sorted(name for name, pattern in RETIRED_CLAIMS.items()
                       if pattern.search(self.text))
        self.assertEqual(
            stale, [],
            f"the resume PDF has regained retired claim(s): {stale}. Fix the "
            "Google Doc and re-export — it cannot be patched from this repo.")

    def test_pdf_agrees_with_the_pages_on_why_the_pipeline_was_rebuilt(self):
        # index.html and resume.html both have to say image submissions
        # defeated OCR. The PDF is the third copy of that story, and the one a
        # reader is most likely to be holding while looking at the other two.
        self.assertRegex(
            self.text, r"(image-based|phone-camera)\s+submissions",
            "the resume PDF no longer gives image submissions as the cause of "
            "the re-architecture, so it now contradicts both live pages.")

    def test_pdf_carries_no_restricted_detail(self):
        """An older copy of the PDF carried these long after the pages had
        dropped them: being binary, no text-level guard ever looked at it."""
        for pattern, why in RESTRICTED_DETAIL:
            with self.subTest(why=why):
                hit = pattern.search(self.text)
                self.assertIsNone(
                    hit, f"the resume PDF states {why}: {hit.group(0)!r}. Fix "
                         "the Google Doc and re-export." if hit else "")

    def test_pdf_does_not_name_a_serving_stack(self):
        # "VLM" is a vision-language model; "vLLM" is a serving engine. An
        # earlier draft of the source document confused the two, which claims
        # infrastructure that was never run.
        for stack in ("vLLM", "TGI", "Ollama", "SageMaker", "Triton"):
            with self.subTest(stack=stack):
                self.assertNotIn(
                    stack, self.text,
                    f"the resume PDF names a serving stack ({stack}). The "
                    "approved phrasing is 'vision-language model (Llama)'.")


if __name__ == "__main__":
    unittest.main()
