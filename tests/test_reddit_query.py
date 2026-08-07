#!/usr/bin/env python3
"""Unit tests for tools/reddit_query.py.

Stdlib only and fully offline — every test either exercises a pure function or
substitutes a fake for the one network call. Run from the repo root:

    python3 -m unittest discover -s tests -p 'test_*.py'

Most of what is covered here is a bug that actually happened. Reddit's transport
layer is where this script keeps breaking (403s, mid-body truncation, gzip), so
that is where the assertions are concentrated rather than on the markdown
formatting, which fails loudly and harmlessly.
"""

import contextlib
import email.message
import gzip
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import reddit_query as rq  # noqa: E402

_stderr = None


def setUpModule():
    """Swallow the script's own progress chatter.

    unittest's runner captured the real stderr when it was constructed, so
    failures and tracebacks still print — only reddit_query's `file=sys.stderr`
    output, which resolves at call time, lands in the sink.
    """
    global _stderr
    _stderr = mock.patch.object(sys, "stderr", io.StringIO())
    _stderr.start()


def tearDownModule():
    _stderr.stop()


def response(payload, headers=None, incomplete_after=None):
    """A stand-in for the object urlopen returns as a context manager."""

    msg = email.message.Message()
    for key, value in (headers or {}).items():
        msg[key] = value

    class FakeResponse:
        def __init__(self):
            self.headers = msg

        def read(self):
            if incomplete_after is not None:
                import http.client

                raise http.client.IncompleteRead(payload[:incomplete_after], 99)
            return payload

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    return FakeResponse()


def gzipped(raw):
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as fh:
        fh.write(raw)
    return buf.getvalue()


ATOM_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Search results</title>
  <entry>
    <author><name>/u/alice</name></author>
    <category term="cscareerquestions" label="r/cscareerquestions"/>
    <content type="html">&lt;p&gt;First body&lt;/p&gt;</content>
    <id>t3_aaa111</id>
    <link href="https://www.reddit.com/r/cscareerquestions/comments/aaa111/a_title/"/>
    <updated>2026-08-01T00:00:00+00:00</updated>
    <title>A title</title>
  </entry>
  <entry>
    <author><name>/u/bob</name></author>
    <category term="leetcode" label="r/leetcode"/>
    <content type="html">&lt;p&gt;Second body&lt;/p&gt;</content>
    <id>t3_bbb222</id>
    <link href="https://www.reddit.com/r/leetcode/comments/bbb222/b_title/"/>
    <updated>2026-08-02T00:00:00+00:00</updated>
    <title>B title</title>
  </entry>
</feed>
"""


class ThrottleTest(unittest.TestCase):
    def setUp(self):
        self._saved = rq.MIN_INTERVAL[0], rq._last_call[0]

    def tearDown(self):
        rq.MIN_INTERVAL[0], rq._last_call[0] = self._saved

    def test_sleeps_the_remainder_of_the_interval(self):
        rq.MIN_INTERVAL[0] = 10.0
        with mock.patch.object(rq.time, "monotonic", return_value=100.0):
            rq._last_call[0] = 96.0
            with mock.patch.object(rq.time, "sleep") as slept:
                rq._throttle()
        slept.assert_called_once()
        self.assertAlmostEqual(slept.call_args[0][0], 6.0)

    def test_does_not_sleep_when_the_interval_has_already_passed(self):
        rq.MIN_INTERVAL[0] = 1.0
        with mock.patch.object(rq.time, "monotonic", return_value=100.0):
            rq._last_call[0] = 50.0
            with mock.patch.object(rq.time, "sleep") as slept:
                rq._throttle()
        slept.assert_not_called()


class RequestTest(unittest.TestCase):
    """The transport. Every assertion here corresponds to an observed failure."""

    def setUp(self):
        # Stop these individually rather than with mock.patch.stopall, which
        # would also tear down the module-level stderr sink.
        for attr, target, name in (
            ("throttle", rq, "_throttle"),
            ("sleep", rq.time, "sleep"),
        ):
            patcher = mock.patch.object(target, name)
            setattr(self, attr, patcher.start())
            self.addCleanup(patcher.stop)

    def test_always_requests_gzip(self):
        # Uncompressed Reddit JSON runs 200-300KB and was truncated in transit
        # every single time; asking for gzip is the fix, so it must not regress.
        body = gzipped(b'{"ok": true}')
        with mock.patch.object(rq.urllib.request, "urlopen") as urlopen:
            urlopen.return_value = response(body, {"Content-Encoding": "gzip"})
            rq._request("https://example.test/x", {"User-Agent": "t"})
        sent = urlopen.call_args[0][0]
        self.assertEqual(sent.get_header("Accept-encoding"), "gzip")

    def test_decompresses_a_gzip_response(self):
        with mock.patch.object(rq.urllib.request, "urlopen") as urlopen:
            urlopen.return_value = response(
                gzipped(b'{"data": {"children": []}}'), {"Content-Encoding": "gzip"}
            )
            out = rq._request("https://example.test/x", {})
        self.assertEqual(out, {"data": {"children": []}})

    def test_passes_through_an_uncompressed_response(self):
        with mock.patch.object(rq.urllib.request, "urlopen") as urlopen:
            urlopen.return_value = response(b'{"n": 1}')
            self.assertEqual(rq._request("https://example.test/x", {}), {"n": 1})

    def test_retries_truncated_json_and_succeeds_on_a_later_attempt(self):
        good = gzipped(b'{"n": 2}')
        attempts = [
            response(b'{"n": ', {"Content-Encoding": "gzip"}),  # cut-off gzip
            response(good, {"Content-Encoding": "gzip"}),
        ]
        with mock.patch.object(rq.urllib.request, "urlopen", side_effect=attempts):
            out = rq._request("https://example.test/x", {})
        self.assertEqual(out, {"n": 2})
        self.sleep.assert_called()

    def test_gives_up_on_json_that_never_arrives_intact(self):
        bad = [response(b'{"unterminated') for _ in range(3)]
        with mock.patch.object(rq.urllib.request, "urlopen", side_effect=bad):
            with self.assertRaises(SystemExit):
                rq._request("https://example.test/x", {}, max_retries=3)

    def test_incomplete_read_keeps_the_partial_body_for_rss(self):
        # RSS is salvageable, so a short read must be returned rather than raised.
        raw = b"<feed><entry>one</entry><entry>tw"
        with mock.patch.object(rq.urllib.request, "urlopen") as urlopen:
            urlopen.return_value = response(raw, incomplete_after=len(raw))
            out = rq._request("https://example.test/x", {}, parse="text")
        self.assertTrue(out.endswith("<entry>tw"))

    def test_sleeps_when_the_rate_limit_budget_is_spent(self):
        headers = {
            "Content-Encoding": "gzip",
            "X-Ratelimit-Remaining": "0.0",
            "X-Ratelimit-Reset": "38",
        }
        with mock.patch.object(rq.urllib.request, "urlopen") as urlopen:
            urlopen.return_value = response(gzipped(b"{}"), headers)
            rq._request("https://example.test/x", {})
        self.assertIn(39.0, [call[0][0] for call in self.sleep.call_args_list])

    def http_error(self, code, reason, headers=None):
        err = rq.urllib.error.HTTPError(
            "https://example.test/x", code, reason, headers or email.message.Message(), None
        )
        self.addCleanup(err.close)
        return err

    def test_403_explains_the_anonymous_json_situation(self):
        err = self.http_error(403, "Forbidden")
        with mock.patch.object(rq.urllib.request, "urlopen", side_effect=err):
            with self.assertRaises(SystemExit) as caught:
                rq._request("https://example.test/x", {})
        self.assertIn("REDDIT_CLIENT_ID", str(caught.exception))

    def test_429_honors_retry_after_then_succeeds(self):
        headers = email.message.Message()
        headers["Retry-After"] = "7"
        err = self.http_error(429, "Too Many Requests", headers)
        with mock.patch.object(
            rq.urllib.request,
            "urlopen",
            side_effect=[err, response(gzipped(b'{"n": 3}'), {"Content-Encoding": "gzip"})],
        ):
            out = rq._request("https://example.test/x", {})
        self.assertEqual(out, {"n": 3})
        self.assertIn(8.0, [call[0][0] for call in self.sleep.call_args_list])


class GunzipPartialTest(unittest.TestCase):
    def test_recovers_the_intact_prefix_of_a_cut_stream(self):
        # Sized like the payloads that actually get cut. A stream small enough
        # that half of it is still the gzip header decodes to nothing, which is
        # correct but says nothing about the case this exists for.
        raw = b"".join(f"line {i} of the body\n".encode() for i in range(5000))
        blob = gzipped(raw)
        out = rq._gunzip_partial(blob[: len(blob) // 2])
        self.assertTrue(out.startswith(b"line 0 of the body\n"))
        self.assertLess(len(out), len(raw))

    def test_returns_empty_for_something_that_is_not_gzip(self):
        self.assertEqual(rq._gunzip_partial(b"not gzip at all"), b"")


class AuthTest(unittest.TestCase):
    def setUp(self):
        self._saved = rq.MIN_INTERVAL[0]
        self.addCleanup(lambda: rq.MIN_INTERVAL.__setitem__(0, self._saved))

    def test_falls_back_to_rss_without_credentials(self):
        with mock.patch.dict(rq.os.environ, {}, clear=True):
            base, headers = rq.get_auth()
        self.assertEqual(base, rq.RSS_BASE)
        self.assertEqual(headers["User-Agent"], rq.BROWSER_UA)

    def test_rss_fallback_widens_the_throttle(self):
        rq.MIN_INTERVAL[0] = 1.2
        with mock.patch.dict(rq.os.environ, {}, clear=True):
            rq.get_auth()
        self.assertGreaterEqual(rq.MIN_INTERVAL[0], 20)

    def test_accepts_the_short_credential_names(self):
        # This machine's profile exports REDDIT_CLIENT / REDDIT_SECRET, not the
        # REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET pair the script first wanted.
        env = {"REDDIT_CLIENT": "id", "REDDIT_SECRET": "shh"}
        with mock.patch.dict(rq.os.environ, env, clear=True):
            with mock.patch.object(rq, "_request", return_value={"access_token": "tok"}):
                base, headers = rq.get_auth()
        self.assertEqual(base, rq.OAUTH_BASE)
        self.assertEqual(headers["Authorization"], "bearer tok")

    def test_accepts_the_long_credential_names(self):
        env = {"REDDIT_CLIENT_ID": "id", "REDDIT_CLIENT_SECRET": "shh"}
        with mock.patch.dict(rq.os.environ, env, clear=True):
            with mock.patch.object(rq, "_request", return_value={"access_token": "tok"}):
                base, _ = rq.get_auth()
        self.assertEqual(base, rq.OAUTH_BASE)

    def test_raises_when_reddit_returns_no_token(self):
        env = {"REDDIT_CLIENT": "id", "REDDIT_SECRET": "shh"}
        with mock.patch.dict(rq.os.environ, env, clear=True):
            with mock.patch.object(rq, "_request", return_value={"error": "bad"}):
                with self.assertRaises(SystemExit):
                    rq.get_auth()


class HtmlToTextTest(unittest.TestCase):
    def test_unescapes_twice(self):
        # Feed content is escaped HTML inside escaped XML, so &amp;#39; is an
        # apostrophe two unescapes down.
        self.assertEqual(rq.html_to_text("it&amp;#39;s"), "it's")

    def test_breaks_and_paragraphs_become_newlines(self):
        out = rq.html_to_text("&lt;p&gt;one&lt;/p&gt;&lt;p&gt;two&lt;br/&gt;three&lt;/p&gt;")
        self.assertEqual(out, "one\n\ntwo\nthree")

    def test_list_items_become_dashes(self):
        out = rq.html_to_text("&lt;ul&gt;&lt;li&gt;a&lt;/li&gt;&lt;li&gt;b&lt;/li&gt;&lt;/ul&gt;")
        self.assertEqual(out, "- a\n- b")

    def test_strips_remaining_tags_and_collapses_blank_runs(self):
        self.assertEqual(rq.html_to_text("<b>bold</b>\n\n\n\ntail"), "bold\n\ntail")

    def test_empty_input(self):
        self.assertEqual(rq.html_to_text(""), "")
        self.assertEqual(rq.html_to_text(None), "")


class PostIdTest(unittest.TestCase):
    def test_full_url(self):
        url = "https://www.reddit.com/r/leetcode/comments/r8de52/affirm_sucks/"
        self.assertEqual(rq.extract_post_id(url), "r8de52")

    def test_permalink(self):
        self.assertEqual(rq.extract_post_id("/r/x/comments/abc123/title/"), "abc123")

    def test_bare_id(self):
        self.assertEqual(rq.extract_post_id("abc123"), "abc123")

    def test_fullname_prefix(self):
        self.assertEqual(rq.extract_post_id("t3_abc123"), "abc123")

    def test_comment_permalink_still_resolves_to_the_post(self):
        link = "/r/x/comments/abc123/title/def456/"
        self.assertEqual(rq.extract_post_id(link), "abc123")


class EntryFieldsTest(unittest.TestCase):
    def setUp(self):
        self.root = rq.ET.fromstring(ATOM_FEED)
        self.first = rq._entry_fields(self.root.findall(f"{rq.ATOM}entry")[0])

    def test_strips_the_u_prefix_from_the_author(self):
        self.assertEqual(self.first["author"], "alice")

    def test_reads_the_subreddit_from_the_category_term(self):
        self.assertEqual(self.first["subreddit"], "cscareerquestions")

    def test_permalink_is_the_path_only(self):
        self.assertEqual(
            self.first["permalink"], "/r/cscareerquestions/comments/aaa111/a_title/"
        )

    def test_body_is_flattened(self):
        self.assertEqual(self.first["body"], "First body")

    def test_missing_author_falls_back(self):
        entry = rq.ET.fromstring(
            '<entry xmlns="http://www.w3.org/2005/Atom"><title>t</title></entry>'
        )
        self.assertEqual(rq._entry_fields(entry)["author"], "[deleted]")


class RssFetchTest(unittest.TestCase):
    def fetch(self, text):
        with mock.patch.object(rq, "_request", return_value=text):
            return rq._rss_fetch("/search.rss", {"q": "x"}, {})

    def test_parses_a_whole_feed(self):
        root = self.fetch(ATOM_FEED)
        self.assertEqual(len(root.findall(f"{rq.ATOM}entry")), 2)

    def test_salvages_a_feed_cut_mid_entry(self):
        cut = ATOM_FEED.index("Second body")
        root = self.fetch(ATOM_FEED[:cut])
        entries = root.findall(f"{rq.ATOM}entry")
        self.assertEqual(len(entries), 1)
        self.assertEqual(rq._entry_fields(entries[0])["author"], "alice")

    def test_gives_up_when_not_even_one_entry_survived(self):
        with self.assertRaises(SystemExit):
            self.fetch("<?xml version=")


class ParseFeedTest(unittest.TestCase):
    BILLION_LAUGHS = """<?xml version="1.0"?>
<!DOCTYPE lolz [
 <!ENTITY lol "lol">
 <!ENTITY lol1 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
 <!ENTITY lol2 "&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;&lol1;">
]>
<feed>&lol2;</feed>"""

    def test_refuses_a_dtd(self):
        # ElementTree expands internal entities, so a DTD is an amplification
        # vector. Reddit never sends one.
        with self.assertRaises(rq.ET.ParseError):
            rq.parse_feed(self.BILLION_LAUGHS)

    def test_a_dtd_is_not_salvaged_as_a_truncated_feed(self):
        hostile = self.BILLION_LAUGHS.replace("<feed>", "<feed><entry>x</entry>")
        with mock.patch.object(rq, "_request", return_value=hostile):
            with self.assertRaises(SystemExit):
                rq._rss_fetch("/search.rss", {}, {})

    def test_still_parses_an_ordinary_feed(self):
        self.assertEqual(len(rq.parse_feed(ATOM_FEED).findall(f"{rq.ATOM}entry")), 2)


class RssSearchTest(unittest.TestCase):
    def test_maps_entries_onto_post_dicts_with_no_score(self):
        with mock.patch.object(rq, "_rss_fetch", return_value=rq.ET.fromstring(ATOM_FEED)):
            posts = rq.rss_search({}, "affirm interview")
        self.assertEqual([p["subreddit"] for p in posts], ["cscareerquestions", "leetcode"])
        self.assertTrue(all(p["score"] is None for p in posts))

    def test_one_request_per_subreddit(self):
        with mock.patch.object(
            rq, "_rss_fetch", return_value=rq.ET.fromstring(ATOM_FEED)
        ) as fetch:
            rq.rss_search({}, "q", subreddits=["a", "b"])
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(fetch.call_args_list[0][0][0], "/r/a/search.rss")


THREAD_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Comments on: A title</title>
  <entry>
    <author><name>/u/alice</name></author>
    <category term="leetcode" label="r/leetcode"/>
    <content type="html">the post body</content>
    <link href="https://www.reddit.com/r/leetcode/comments/aaa111/a_title/"/>
    <title>A title</title>
  </entry>
  <entry>
    <author><name>/u/bob</name></author>
    <content type="html">a reply</content>
    <link href="https://www.reddit.com/r/leetcode/comments/aaa111/a_title/ccc333/"/>
    <title>bob's comment</title>
  </entry>
</feed>
"""


class RssThreadTest(unittest.TestCase):
    def thread(self, feed=THREAD_FEED, **kwargs):
        with mock.patch.object(rq, "_rss_fetch", return_value=rq.ET.fromstring(feed)):
            return rq.rss_thread({}, "aaa111", **kwargs)

    def test_separates_the_submission_from_its_comments(self):
        post, comments = self.thread()
        self.assertEqual(post["author"], "alice")
        self.assertEqual(post["selftext"], "the post body")
        self.assertEqual([c["author"] for c in comments], ["bob"])

    def test_comments_are_flat_and_scoreless(self):
        _, comments = self.thread()
        self.assertEqual(comments[0]["depth"], 0)
        self.assertIsNone(comments[0]["score"])

    def test_truncates_long_bodies(self):
        _, comments = self.thread(max_chars=3)
        self.assertTrue(comments[0]["body"].endswith("[…truncated]"))

    def test_synthesises_a_post_when_the_feed_has_only_comments(self):
        feed = THREAD_FEED.replace(
            '<link href="https://www.reddit.com/r/leetcode/comments/aaa111/a_title/"/>',
            '<link href="https://www.reddit.com/r/leetcode/comments/aaa111/a_title/ddd444/"/>',
        )
        post, comments = self.thread(feed)
        self.assertEqual(len(comments), 2)
        self.assertEqual(post["title"], "Comments on: A title")


def comment(author, body, score=1, replies=None):
    data = {"author": author, "body": body, "score": score}
    if replies:
        data["replies"] = {"data": {"children": replies}}
    return {"kind": "t1", "data": data}


class WalkTest(unittest.TestCase):
    def walk(self, children, min_score=0, max_chars=1500):
        out = []
        rq._walk(children, 0, out, min_score, max_chars)
        return out

    def test_records_nesting_depth(self):
        tree = [comment("a", "top", replies=[comment("b", "mid", replies=[comment("c", "deep")])])]
        self.assertEqual([c["depth"] for c in self.walk(tree)], [0, 1, 2])

    def test_skips_more_stubs(self):
        tree = [comment("a", "kept"), {"kind": "more", "data": {"count": 40}}]
        self.assertEqual([c["author"] for c in self.walk(tree)], ["a"])

    def test_drops_deleted_and_removed_bodies_but_keeps_their_replies(self):
        tree = [comment("a", "[deleted]", replies=[comment("b", "still here")])]
        self.assertEqual([c["author"] for c in self.walk(tree)], ["b"])

    def test_min_score_filters(self):
        tree = [comment("a", "low", score=-3), comment("b", "high", score=9)]
        self.assertEqual([c["author"] for c in self.walk(tree, min_score=1)], ["b"])

    def test_truncates_long_bodies(self):
        out = self.walk([comment("a", "x" * 200)], max_chars=10)
        self.assertTrue(out[0]["body"].endswith("[…truncated]"))
        self.assertLess(len(out[0]["body"]), 40)

    def test_missing_score_is_treated_as_zero(self):
        tree = [{"kind": "t1", "data": {"author": "a", "body": "b", "score": None}}]
        self.assertEqual(self.walk(tree)[0]["score"], 0)


class GetThreadTest(unittest.TestCase):
    def test_routes_to_rss_when_unauthenticated(self):
        with mock.patch.object(rq, "rss_thread", return_value=({}, [])) as rss:
            rq.get_thread(rq.RSS_BASE, {}, "abc123")
        rss.assert_called_once()

    def test_parses_the_two_element_json_listing(self):
        payload = [
            {"data": {"children": [{"data": {"title": "T", "score": 5}}]}},
            {"data": {"children": [comment("a", "hi")]}},
        ]
        with mock.patch.object(rq, "_request", return_value=payload):
            post, comments = rq.get_thread(rq.OAUTH_BASE, {}, "abc123")
        self.assertEqual(post["title"], "T")
        self.assertEqual(comments[0]["body"], "hi")

    def test_rejects_an_unexpected_shape(self):
        with mock.patch.object(rq, "_request", return_value={"error": 404}):
            with self.assertRaises(SystemExit):
                rq.get_thread(rq.OAUTH_BASE, {}, "abc123")

    def test_oauth_urls_carry_no_json_suffix(self):
        payload = [{"data": {"children": [{"data": {}}]}}, {"data": {"children": []}}]
        with mock.patch.object(rq, "_request", return_value=payload) as req:
            rq.get_thread(rq.OAUTH_BASE, {}, "abc123")
        self.assertIn("/comments/abc123?", req.call_args[0][0])


class SearchTest(unittest.TestCase):
    def test_routes_to_rss_when_unauthenticated(self):
        with mock.patch.object(rq, "rss_search", return_value=[]) as rss:
            rq.search(rq.RSS_BASE, {}, "q")
        rss.assert_called_once()

    def test_unwraps_the_listing_children(self):
        payload = {"data": {"children": [{"data": {"title": "T"}}]}}
        with mock.patch.object(rq, "_request", return_value=payload):
            posts = rq.search(rq.OAUTH_BASE, {}, "q")
        self.assertEqual(posts, [{"title": "T"}])

    def test_subreddit_search_restricts_to_the_subreddit(self):
        payload = {"data": {"children": []}}
        with mock.patch.object(rq, "_request", return_value=payload) as req:
            rq.search(rq.OAUTH_BASE, {}, "q", subreddits=["leetcode"])
        url = req.call_args[0][0]
        self.assertIn("/r/leetcode/search?", url)
        self.assertIn("restrict_sr=1", url)

    def test_limit_is_capped_at_the_api_maximum(self):
        payload = {"data": {"children": []}}
        with mock.patch.object(rq, "_request", return_value=payload) as req:
            rq.search(rq.OAUTH_BASE, {}, "q", limit=500)
        self.assertIn("limit=100", req.call_args[0][0])


class FormatTest(unittest.TestCase):
    def test_header_includes_score_and_comment_count_when_known(self):
        post = {
            "subreddit": "leetcode",
            "author": "alice",
            "score": 42,
            "num_comments": 7,
            "title": "T",
            "permalink": "/r/leetcode/comments/x/",
        }
        out = rq.fmt_post_header(post)
        self.assertIn("score 42", out)
        self.assertIn("7 comments", out)

    def test_header_omits_score_over_rss(self):
        # RSS carries no score; a None must not render as "score None".
        post = {"subreddit": "r", "author": "a", "score": None, "num_comments": None,
                "title": "T", "permalink": "/p/"}
        self.assertNotIn("score", rq.fmt_post_header(post))

    def test_header_omits_a_deleted_body(self):
        post = {"subreddit": "r", "author": "a", "title": "T", "permalink": "/p/",
                "selftext": "[deleted]"}
        self.assertNotIn("[deleted]", rq.fmt_post_header(post))

    def test_body_is_quoted_line_by_line(self):
        post = {"subreddit": "r", "author": "a", "title": "T", "permalink": "/p/",
                "selftext": "one\ntwo"}
        self.assertIn("> one\n> two", rq.fmt_post_header(post))

    def test_comments_indent_by_depth(self):
        out = rq.fmt_comments([
            {"depth": 0, "author": "a", "score": 3, "body": "top"},
            {"depth": 2, "author": "b", "score": 1, "body": "nested"},
        ])
        self.assertIn("- **u/a** (3):", out)
        self.assertIn("    - **u/b** (1):", out)

    def test_comment_score_is_omitted_over_rss(self):
        out = rq.fmt_comments([{"depth": 0, "author": "a", "score": None, "body": "x"}])
        self.assertIn("- **u/a**:", out)

    def test_indentation_stops_at_six_levels(self):
        out = rq.fmt_comments([{"depth": 20, "author": "a", "score": 1, "body": "x"}])
        self.assertTrue(out.splitlines()[3].startswith(" " * 12 + "-"))

    def test_no_comments_says_so(self):
        self.assertIn("no comments matched", rq.fmt_comments([]))


class BatchTest(unittest.TestCase):
    """The batch subcommand exists to spend a tight rate-limit budget well."""

    def run_main(self, argv, search_results):
        """Run main() with the network stubbed out; return what it wrote to stdout."""
        out = io.StringIO()
        with mock.patch.object(sys, "argv", argv), \
             mock.patch.object(rq, "get_auth", return_value=(rq.OAUTH_BASE, {})), \
             mock.patch.object(rq, "search", side_effect=search_results), \
             contextlib.redirect_stdout(out), \
             contextlib.redirect_stderr(io.StringIO()):
            rq.main()
        return out.getvalue()

    def test_dedupes_the_same_post_across_queries(self):
        shared = {"permalink": "/p/1", "title": "T", "subreddit": "r", "author": "a"}
        other = {"permalink": "/p/2", "title": "U", "subreddit": "r", "author": "b"}
        text = self.run_main(
            ["reddit_query.py", "batch", "-q", "one", "-q", "two"],
            [[shared], [shared, other]],
        )
        self.assertIn("2 unique posts", text)
        self.assertEqual(text.count("/p/1"), 1)

    def test_a_failing_query_does_not_abort_the_rest(self):
        good = {"permalink": "/p/1", "title": "T", "subreddit": "r", "author": "a"}
        text = self.run_main(
            ["reddit_query.py", "batch", "-q", "one", "-q", "two"],
            [SystemExit("boom"), [good]],
        )
        self.assertIn("/p/1", text)

    def test_json_output_is_machine_readable(self):
        post = {"permalink": "/p/1", "title": "T", "subreddit": "r", "author": "a"}
        text = self.run_main(["reddit_query.py", "batch", "-q", "one", "--json"], [[post]])
        self.assertEqual(json.loads(text)[0]["permalink"], "/p/1")

    def test_writes_the_output_file_when_asked(self):
        post = {"permalink": "/p/1", "title": "T", "subreddit": "r", "author": "a"}
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "out.md")
            self.run_main(
                ["reddit_query.py", "batch", "-q", "one", "-o", path], [[post]]
            )
            self.assertIn("/p/1", Path(path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
