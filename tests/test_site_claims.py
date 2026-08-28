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

# Employer-proprietary detail: throughput figures, internal org scope, and
# internal business process. Every one of these was live on the `main` branch
# until it was deleted on 2026-08-28 — in the HTML *and* in the resume PDF
# tracked alongside it — so this is a regression guard with a real history,
# not a hypothetical.
#
# The throughput rules deliberately require an explicit *rate* context rather
# than banning a bare number. Jonathan's own open-source figures are his to
# publish, and two of them live on these very pages: boost's "10,000-resample
# paired bootstrap" and its index of "10,000+ publicly available skills". A
# guard stricter than his own resume is a broken guard, and
# `test_open_source_numbers_are_not_flagged` pins that distinction.
PROPRIETARY_DETAIL = [
    (re.compile(r"\d[\d,.]*\s*\+?\s*(?:requests?|apps?|applications?|events?"
                r"|transactions?|calls?|messages?)\s*(?:/|\s+per\s+)"
                r"\s*(?:hour|hr|min|minute|second|sec|day)", re.I),
     "a proprietary throughput rate"),
    (re.compile(r"(?:requests?|apps?|applications?|events?|transactions?|calls?"
                r"|messages?)\s*(?:/|\s+per\s+)\s*(?:hour|hr|min|minute"
                r"|second|sec)", re.I),
     "a proprietary throughput rate"),
    # The noun can also come *before* the number ("processing requests at
    # 10,000+ per hour"), which the two rules above both miss — they anchor
    # the unit to the noun. Found by the mutation test below, not by reading.
    (re.compile(r"\d[\d,.]*\s*\+?\s*(?:per|/)\s*"
                r"(?:hour|hr|min|minute|second|sec)", re.I),
     "a proprietary throughput rate"),
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


    def test_no_page_carries_proprietary_throughput_or_internal_scope(self):
        """The figures that were live on `main` until it was deleted.

        "10,000+ requests/hour", "10K / Loan apps per hour", "all
        communications between Capital One, its dealership partners and
        internal messaging systems", "every technology organization at Capital
        One", "dealership marketing targets" — none of these had ever been
        asserted by a test, which is exactly why they survived on a public
        branch for a month after being scrubbed from the live pages.
        """
        for page in LIVE_PAGES:
            for pattern, why in PROPRIETARY_DETAIL:
                with self.subTest(page=page, why=why):
                    hit = pattern.search(read(page))
                    self.assertIsNone(
                        hit, f"{page} states {why}: "
                             f"{hit.group(0)!r}" if hit else "")

    def test_open_source_numbers_are_not_flagged(self):
        """boost's own public figures must pass. They are Jonathan's to publish.

        This is not decoration. The first draft of this guard banned a bare
        "10,000" and flagged four true positives on this repo's own pages,
        which would have made the suite stricter than the resume it protects.
        """
        for allowed in [
            "a seeded <b>10,000-resample paired bootstrap</b>, so a regression",
            "paired bootstrap · 10,000 resamples · no significant regression",
            "indexes more than 10,000 publicly available skills",
            "a 70+ command Python CLI with its own MCP server",
        ]:
            for pattern, why in PROPRIETARY_DETAIL:
                with self.subTest(allowed=allowed[:40], why=why):
                    self.assertIsNone(
                        pattern.search(allowed),
                        f"guard fires on Jonathan's own open-source figure "
                        f"({why}): {allowed!r}")

    def test_guard_catches_the_wordings_that_were_live_on_main(self):
        """Break it on purpose. Verbatim strings from the deleted branch."""
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
                    any(p.search(sample) for p, _ in PROPRIETARY_DETAIL),
                    f"guard would not catch: {sample!r}")


class ResumePdfIsGoverned(unittest.TestCase):
    """The PDF had no test at all before this, and no workflow watched it."""

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
            "that is the headline, and this is the one page recruiters "
            "verify. Fix the Google Doc and re-export.")

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

        Worth stating plainly: the PDF is the artifact that leaves Jonathan's
        control. A page can be corrected after the fact; a PDF someone
        forwarded to a recruiter three weeks ago cannot.
        """
        stale = sorted(name for name, pattern in RETIRED_CLAIMS.items()
                       if pattern.search(self.text))
        self.assertEqual(
            stale, [],
            f"the resume PDF has regained retired claim(s): {stale}. Fix the "
            "Google Doc and re-export — the PDF cannot be patched from this "
            "repo, and it is what gets forwarded.")

    def test_pdf_agrees_with_the_pages_on_why_the_pipeline_was_rebuilt(self):
        # index.html and resume.html both have to say image submissions
        # defeated OCR. The PDF is the third copy of that story, and the one a
        # reader is most likely to be holding while looking at the other two.
        self.assertRegex(
            self.text, r"(image-based|phone-camera)\s+submissions",
            "the resume PDF no longer gives image submissions as the cause of "
            "the re-architecture, so it now contradicts both live pages.")

    def test_pdf_carries_no_proprietary_throughput_or_internal_scope(self):
        """The PDF tracked on `main` carried six of these while the HTML beside
        it had already been scrubbed — it is binary, so every text-level guard
        that existed simply did not look at it."""
        for pattern, why in PROPRIETARY_DETAIL:
            with self.subTest(why=why):
                hit = pattern.search(self.text)
                self.assertIsNone(
                    hit, f"the resume PDF states {why}: {hit.group(0)!r}. Fix "
                         "the Google Doc and re-export." if hit else "")

    def test_pdf_does_not_name_a_serving_stack(self):
        # "VLM" is a vision-language model; "vLLM" is a serving engine. An
        # earlier draft of the source document said "self-hosted vLLM with
        # Llama", which claims infrastructure that was never run and invites
        # an interview question about a different subject entirely.
        for stack in ("vLLM", "TGI", "Ollama", "SageMaker", "Triton"):
            with self.subTest(stack=stack):
                self.assertNotIn(
                    stack, self.text,
                    f"the resume PDF names a serving stack ({stack}). The "
                    "approved phrasing is 'vision-language model (Llama)'.")


if __name__ == "__main__":
    unittest.main()
