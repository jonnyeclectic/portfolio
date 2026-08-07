#!/usr/bin/env python3
"""
reddit_query.py — search Reddit and dump threads + comments as paste-ready markdown.

Why this exists: Reddit refuses Anthropic's web crawler, so Claude Code cannot fetch
reddit.com directly. Run this yourself and paste the output back into the conversation.

Stdlib only — nothing to pip install.

TRANSPORTS (picked automatically, best first)
  1. OAuth JSON  — used when REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET are set.
                   Full fidelity: scores, comment nesting, ~100 req/min.
  2. Atom RSS    — the anonymous fallback. As of 2026 Reddit returns 403 on every
                   public .json endpoint regardless of User-Agent, but the .rss feeds
                   still serve full post and comment bodies. Costs: no scores, no
                   comment nesting (the feed is flat), and a brutal rate limit of
                   roughly one request per 40s window, which this script rides out
                   automatically by honoring the x-ratelimit-* headers.

USAGE
  # search all of Reddit
  ./reddit_query.py search "Vervoe assessment software engineer"

  # restrict to subreddits, sort by newest, last year only
  ./reddit_query.py search "Vervoe" -r AusPublicService -r cscareerquestions --sort new -t year

  # pull a thread's full comment tree (accepts a URL, permalink, or bare post id)
  ./reddit_query.py thread https://www.reddit.com/r/AusPublicService/comments/abc123/...

  # search, then auto-fetch comments for every hit, into one file
  ./reddit_query.py search "Lumen Vervoe" --with-comments -o lumen.md

  # run several searches in one go, deduped, into one file (cheapest way to spend
  # a tight anonymous rate-limit budget)
  ./reddit_query.py batch -q "Affirm interview" -q "Affirm staff engineer" -o affirm.md

AUTH (optional but strongly recommended — restores scores, nesting, and ~100 req/min)
  Create a "script" app at https://www.reddit.com/prefs/apps, then:
    export REDDIT_CLIENT_ID=...
    export REDDIT_CLIENT_SECRET=...

  Reddit asks for a descriptive User-Agent including your username:
    export REDDIT_USER_AGENT="python:reddit-query:0.2 (by /u/YOUR_USERNAME)"
"""

import argparse
import base64
import gzip
import html
import http.client
import json
import os
import zlib
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

UA = os.environ.get(
    "REDDIT_USER_AGENT", "python:reddit-query:0.2 (personal research script)"
)

# The RSS feeds are served by the www frontend and are happier with a browser UA than
# with an API-style one; the OAuth API is the opposite. Keep them separate.
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

PUBLIC_BASE = "https://www.reddit.com"
OAUTH_BASE = "https://oauth.reddit.com"
RSS_BASE = "rss"  # sentinel, not a URL

ATOM = "{http://www.w3.org/2005/Atom}"

# Reddit's own guidance is <=100 req/min authenticated. Anonymous RSS is far tighter —
# observed as ~1 request per 40s window — so the two modes get different floors.
MIN_INTERVAL = [float(os.environ.get("REDDIT_MIN_INTERVAL", "1.2"))]
_last_call = [0.0]


def _gunzip_partial(blob):
    """Decompress as much of a cut-short gzip stream as is intact."""
    d = zlib.decompressobj(zlib.MAX_WBITS | 16)
    try:
        return d.decompress(blob)
    except zlib.error:
        return b""


def _throttle():
    """Space out calls so we stay under Reddit's rate limit without being told to."""
    elapsed = time.monotonic() - _last_call[0]
    if elapsed < MIN_INTERVAL[0]:
        time.sleep(MIN_INTERVAL[0] - elapsed)
    _last_call[0] = time.monotonic()


ALLOWED_HOSTS = frozenset({"www.reddit.com", "oauth.reddit.com"})


def _check_host(url):
    """Enforce the invariant that every URL is built from one of the two bases.

    Nothing here should ever be able to reach another host — user input only
    becomes urlencoded query params or a validated post id — so this asserts
    that rather than leaving it to be re-derived by reading the callers.
    """
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    if host not in ALLOWED_HOSTS:
        raise SystemExit(f"refusing to request a non-Reddit host: {host!r}")


def _request(url, headers, data=None, max_retries=6, parse="json"):
    """GET/POST with exponential backoff on 429 and 5xx, honoring Retry-After."""
    _check_host(url)
    delay = 5.0
    last_err = None
    for attempt in range(max_retries):
        _throttle()
        # Ask for gzip and a non-persistent connection. Reddit's uncompressed search
        # JSON runs to ~300KB and gets truncated in transit; compressed it is small
        # enough to arrive intact.
        hdrs = dict(headers, **{"Accept-Encoding": "gzip", "Connection": "close"})
        req = urllib.request.Request(url, data=data, headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=45) as resp:
                truncated = False
                try:
                    payload = resp.read()
                except http.client.IncompleteRead as e:
                    payload, truncated = e.partial, True
                if resp.headers.get("Content-Encoding") == "gzip":
                    try:
                        payload = gzip.decompress(payload)
                    except (OSError, EOFError):
                        # A truncated gzip stream still decodes up to the cut point.
                        payload = _gunzip_partial(payload)
                        truncated = True
                body = payload.decode("utf-8", "replace")
                # Proactively back off when Reddit says we're nearly out of budget.
                remaining = resp.headers.get("X-Ratelimit-Remaining")
                if remaining is not None:
                    try:
                        if float(remaining) < 1:
                            reset = float(resp.headers.get("X-Ratelimit-Reset", 10))
                            print(
                                f"  [budget spent, sleeping {reset:.0f}s]",
                                file=sys.stderr,
                            )
                            time.sleep(reset + 1)
                            _last_call[0] = time.monotonic()
                    except ValueError:
                        pass
                if parse != "json":
                    # RSS survives truncation — the caller salvages whole <entry> blocks.
                    return body
                try:
                    return json.loads(body)
                except json.JSONDecodeError:
                    # A cut-off body is a transport failure, not a real payload. JSON
                    # can't be salvaged the way RSS can, so ask for it again.
                    if attempt < max_retries - 1:
                        print(
                            f"  [{'truncated' if truncated else 'malformed'} JSON "
                            f"({len(body)} bytes), retry {attempt + 1} in {delay:.0f}s]",
                            file=sys.stderr,
                        )
                        time.sleep(delay)
                        _last_call[0] = time.monotonic()
                        delay = min(delay * 2, 90)
                        continue
                    raise SystemExit(f"could not parse JSON from {url}")
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
                wait = delay
                for header in ("Retry-After", "X-Ratelimit-Reset"):
                    value = e.headers.get(header)
                    if value:
                        try:
                            wait = max(float(value) + 1, 1.0)
                            break
                        except ValueError:
                            pass
                print(
                    f"  [HTTP {e.code}, retry {attempt + 1}/{max_retries - 1} in {wait:.0f}s]",
                    file=sys.stderr,
                )
                time.sleep(wait)
                _last_call[0] = time.monotonic()
                delay = min(delay * 2, 90)
                continue
            if e.code in (403, 404):
                raise SystemExit(
                    f"HTTP {e.code} from Reddit for {url}\n"
                    "  403 on a .json endpoint is now the norm for anonymous clients —\n"
                    "  set REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET, or let the script\n"
                    "  fall back to RSS (it does so automatically when creds are absent)."
                )
            raise
        except (urllib.error.URLError, TimeoutError, http.client.HTTPException) as e:
            last_err = e
            if attempt < max_retries - 1:
                print(f"  [network error: {e}; retry in {delay:.0f}s]", file=sys.stderr)
                time.sleep(delay)
                delay = min(delay * 2, 90)
                continue
            raise
    raise SystemExit(f"giving up after {max_retries} attempts: {last_err}")


def get_auth():
    """Return (base_url, headers). Falls back to the RSS transport without credentials."""
    # Accept either spelling — this machine exports the shorter pair.
    cid = os.environ.get("REDDIT_CLIENT_ID") or os.environ.get("REDDIT_CLIENT")
    secret = os.environ.get("REDDIT_CLIENT_SECRET") or os.environ.get("REDDIT_SECRET")
    if not (cid and secret):
        MIN_INTERVAL[0] = max(MIN_INTERVAL[0], float(os.environ.get("REDDIT_MIN_INTERVAL", "20")))
        print(
            "  [no credentials: using anonymous RSS — no scores, flat comments, slow]",
            file=sys.stderr,
        )
        return RSS_BASE, {"User-Agent": BROWSER_UA}

    basic = base64.b64encode(f"{cid}:{secret}".encode()).decode()
    body = urllib.parse.urlencode({"grant_type": "client_credentials"}).encode()
    payload = _request(
        f"{PUBLIC_BASE}/api/v1/access_token",
        headers={
            "Authorization": f"Basic {basic}",
            "User-Agent": UA,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data=body,
    )
    token = payload.get("access_token")
    if not token:
        raise SystemExit(f"OAuth failed: {payload}")
    print("  [authenticated: ~100 req/min]", file=sys.stderr)
    return OAUTH_BASE, {"Authorization": f"bearer {token}", "User-Agent": UA}


# --------------------------------------------------------------------------- RSS

TAG_RE = re.compile(r"<[^>]+>")


def html_to_text(raw):
    """Flatten Reddit's escaped-HTML feed content into readable plain text."""
    if not raw:
        return ""
    s = html.unescape(raw)  # feed content arrives HTML-escaped inside the XML
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</p\s*>", "\n\n", s)
    s = re.sub(r"(?i)<li[^>]*>", "\n- ", s)
    s = re.sub(r"(?i)</(ul|ol|blockquote|div|h[1-6]|pre)\s*>", "\n", s)
    s = TAG_RE.sub("", s)
    s = html.unescape(s)  # entities that were double-escaped (&amp;#39;)
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _entry_fields(entry):
    link = entry.find(f"{ATOM}link")
    href = link.get("href") if link is not None else ""
    author = entry.findtext(f"{ATOM}author/{ATOM}name") or "[deleted]"
    category = entry.find(f"{ATOM}category")
    return {
        "title": (entry.findtext(f"{ATOM}title") or "").strip(),
        "author": author.removeprefix("/u/"),
        "subreddit": category.get("term") if category is not None else "",
        "href": href,
        "permalink": urllib.parse.urlparse(href).path,
        "body": html_to_text(entry.findtext(f"{ATOM}content") or ""),
        "updated": entry.findtext(f"{ATOM}updated") or "",
    }


DOCTYPE_RE = re.compile(r"<!DOCTYPE", re.I)


def parse_feed(text):
    """Parse an Atom feed, refusing any document that declares a DTD.

    ElementTree expands internal entities, so a document with a hostile internal
    subset can blow up memory exponentially ("billion laughs"). Reddit's feeds
    never carry a DOCTYPE, so refusing one costs nothing and closes the hole.
    """
    if DOCTYPE_RE.search(text):
        raise ET.ParseError("refusing a feed that declares a DTD")
    return ET.fromstring(text)


def _rss_fetch(path, params, headers):
    url = f"{PUBLIC_BASE}{path}?{urllib.parse.urlencode(params)}"
    text = _request(url, headers, parse="text")
    try:
        return parse_feed(text)
    except ET.ParseError:
        pass
    # A truncated feed still holds every entry that arrived intact — salvage those
    # by cutting back to the last complete </entry> and closing the document.
    cut = text.rfind("</entry>")
    if cut != -1:
        try:
            root = parse_feed(text[: cut + len("</entry>")] + "</feed>")
            print("  [feed was truncated; recovered complete entries]", file=sys.stderr)
            return root
        except ET.ParseError:
            pass
    raise SystemExit(f"could not parse RSS from {url}")


def rss_search(headers, query, subreddits=None, sort="relevance", time_filter="all", limit=25):
    posts = []
    for sub in subreddits or [None]:
        params = {
            "q": query,
            "sort": sort,
            "t": time_filter,
            "limit": min(limit, 100),
            "type": "link",
        }
        if sub:
            path, params["restrict_sr"] = f"/r/{sub}/search.rss", 1
        else:
            path = "/search.rss"
        print(f"  searching {sub or 'all of reddit'} (rss)...", file=sys.stderr)
        root = _rss_fetch(path, params, headers)
        for entry in root.findall(f"{ATOM}entry"):
            f = _entry_fields(entry)
            posts.append(
                {
                    "title": f["title"],
                    "subreddit": f["subreddit"],
                    "author": f["author"],
                    "score": None,
                    "num_comments": None,
                    "permalink": f["permalink"],
                    "selftext": f["body"],
                    "created_utc_iso": f["updated"],
                }
            )
    return posts


def rss_thread(headers, ref, limit=200, max_chars=1500):
    """Fetch a thread's comments over RSS. The feed is flat — depth is always 0."""
    post_id = extract_post_id(ref)
    print(f"  fetching thread {post_id} (rss)...", file=sys.stderr)
    root = _rss_fetch(f"/comments/{post_id}.rss", {"limit": limit}, headers)

    feed_title = (root.findtext(f"{ATOM}title") or "").strip()
    entries = [_entry_fields(e) for e in root.findall(f"{ATOM}entry")]

    # The submission itself appears as the entry whose permalink has no comment id
    # appended after the post id; everything else is a comment.
    post, comments = None, []
    for f in entries:
        segments = [s for s in f["permalink"].split("/") if s]
        is_post = not (len(segments) > 5 and segments[-1] != post_id)
        if is_post and post is None:
            post = f
        else:
            body = f["body"]
            if len(body) > max_chars:
                body = body[:max_chars].rstrip() + " […truncated]"
            comments.append(
                {"depth": 0, "author": f["author"], "score": None, "body": body}
            )

    if post is None:
        post = {
            "title": feed_title,
            "subreddit": "",
            "author": "[unknown]",
            "permalink": f"/comments/{post_id}/",
            "body": "",
        }
    return (
        {
            "title": post["title"] or feed_title,
            "subreddit": post["subreddit"],
            "author": post["author"],
            "score": None,
            "num_comments": len(comments),
            "permalink": post["permalink"],
            "selftext": post["body"],
        },
        comments,
    )


# -------------------------------------------------------------------------- JSON


def search(base, headers, query, subreddits=None, sort="relevance", time_filter="all", limit=25):
    """Search Reddit. Returns a list of post dicts."""
    if base == RSS_BASE:
        return rss_search(headers, query, subreddits, sort, time_filter, limit)
    params = {
        "q": query,
        "sort": sort,
        "t": time_filter,
        "limit": min(limit, 100),
        "raw_json": 1,
        "type": "link",
    }
    posts = []
    targets = subreddits or [None]
    for sub in targets:
        p = dict(params)
        if sub:
            path = f"/r/{sub}/search"
            p["restrict_sr"] = 1
        else:
            path = "/search"
        suffix = "" if base == OAUTH_BASE else ".json"
        url = f"{base}{path}{suffix}?{urllib.parse.urlencode(p)}"
        print(f"  searching {sub or 'all of reddit'}...", file=sys.stderr)
        payload = _request(url, headers)
        for child in payload.get("data", {}).get("children", []):
            posts.append(child.get("data", {}))
    return posts


POST_ID_RE = re.compile(r"/comments/([a-z0-9]+)", re.I)
BARE_ID_RE = re.compile(r"[a-z0-9]+\Z", re.I)


def extract_post_id(ref):
    """Accept a full URL, a permalink, or a bare id like 'abc123' / 't3_abc123'.

    The result is interpolated straight into a request path, so anything that
    is not a plain id is rejected rather than passed along — otherwise a '?' or
    '#' in the argument silently rewrites the query string of the request.
    """
    m = POST_ID_RE.search(ref)
    if m:
        return m.group(1)
    candidate = ref.strip().removeprefix("t3_").rstrip("/").split("/")[-1]
    if not BARE_ID_RE.fullmatch(candidate):
        raise SystemExit(f"not a usable Reddit post id or link: {ref!r}")
    return candidate


def _walk(children, depth, out, min_score, max_chars):
    for child in children:
        if child.get("kind") != "t1":
            continue  # skip 'more' stubs and anything that isn't a comment
        d = child.get("data", {})
        score = d.get("score") or 0
        body = (d.get("body") or "").strip()
        if body and body not in ("[deleted]", "[removed]") and score >= min_score:
            if len(body) > max_chars:
                body = body[:max_chars].rstrip() + " […truncated]"
            out.append(
                {
                    "depth": depth,
                    "author": d.get("author") or "[deleted]",
                    "score": score,
                    "body": body,
                }
            )
        replies = d.get("replies")
        if isinstance(replies, dict):
            _walk(replies.get("data", {}).get("children", []), depth + 1, out, min_score, max_chars)


def get_thread(base, headers, ref, limit=200, min_score=0, max_chars=1500):
    """Fetch a post plus its comment tree (nested over JSON, flat over RSS)."""
    if base == RSS_BASE:
        return rss_thread(headers, ref, limit=limit, max_chars=max_chars)
    post_id = extract_post_id(ref)
    suffix = "" if base == OAUTH_BASE else ".json"
    params = urllib.parse.urlencode({"limit": limit, "raw_json": 1, "depth": 10})
    url = f"{base}/comments/{post_id}{suffix}?{params}"
    print(f"  fetching thread {post_id}...", file=sys.stderr)
    payload = _request(url, headers)
    if not isinstance(payload, list) or len(payload) < 2:
        raise SystemExit(f"unexpected response shape for {post_id}")
    post = payload[0]["data"]["children"][0]["data"]
    comments = []
    _walk(payload[1]["data"]["children"], 0, comments, min_score, max_chars)
    return post, comments


# ---------------------------------------------------------------------- format


def fmt_post_header(p):
    meta = [f"**r/{p.get('subreddit')}**", f"u/{p.get('author')}"]
    if p.get("score") is not None:
        meta.append(f"score {p['score']}")
    if p.get("num_comments") is not None:
        meta.append(f"{p['num_comments']} comments")
    lines = [
        f"## {p.get('title', '(no title)')}",
        "",
        "- " + " · ".join(meta),
        f"- https://www.reddit.com{p.get('permalink', '')}",
    ]
    body = (p.get("selftext") or "").strip()
    if body and body not in ("[deleted]", "[removed]"):
        if len(body) > 4000:
            body = body[:4000].rstrip() + " […truncated]"
        lines += ["", "> " + body.replace("\n", "\n> ")]
    return "\n".join(lines)


def fmt_comments(comments):
    if not comments:
        return "\n_(no comments matched)_"
    out = ["", "### Comments", ""]
    for c in comments:
        indent = "  " * min(c["depth"], 6)
        score = "" if c.get("score") is None else f" ({c['score']})"
        out.append(f"{indent}- **u/{c['author']}**{score}:")
        for line in c["body"].split("\n"):
            if line.strip():
                out.append(f"{indent}  {line}")
        out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(
        description="Search Reddit / dump threads as paste-ready markdown.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", help="search for posts")
    s.add_argument("query")

    b = sub.add_parser("batch", help="run several searches, deduped, into one document")
    b.add_argument("-q", "--query", action="append", dest="queries", required=True,
                   help="a search query (repeatable)")

    for p in (s, b):
        p.add_argument("-r", "--subreddit", action="append", dest="subreddits",
                       help="restrict to a subreddit (repeatable)")
        p.add_argument("--sort", default="relevance",
                       choices=["relevance", "hot", "top", "new", "comments"])
        p.add_argument("-t", "--time", default="all", dest="time_filter",
                       choices=["hour", "day", "week", "month", "year", "all"])
        p.add_argument("-n", "--limit", type=int, default=25)
        p.add_argument("--with-comments", action="store_true",
                       help="also fetch the full comment tree for every result")

    th = sub.add_parser("thread", help="dump one thread's comments")
    th.add_argument("refs", nargs="+", help="URL(s), permalink(s), or post id(s)")

    for p in (s, b, th):
        p.add_argument("-o", "--out", help="write markdown here (also prints to stdout)")
        p.add_argument("--min-score", type=int, default=0,
                       help="drop comments below this score (JSON transport only)")
        p.add_argument("--max-chars", type=int, default=1500,
                       help="truncate each comment body (default 1500)")
        p.add_argument("--json", action="store_true", help="emit raw JSON instead")

    args = ap.parse_args()

    base, headers = get_auth()
    chunks, raw = [], []

    def emit(posts, heading):
        chunks.append(heading)
        for p in posts:
            raw.append(p)
            chunks.append(fmt_post_header(p))
            if args.with_comments:
                try:
                    _, comments = get_thread(base, headers, p.get("permalink", ""),
                                             min_score=args.min_score,
                                             max_chars=args.max_chars)
                    chunks.append(fmt_comments(comments))
                except SystemExit as e:
                    chunks.append(f"\n_(comments unavailable: {e})_")
            chunks.append("\n---\n")

    if args.cmd == "search":
        posts = search(base, headers, args.query, args.subreddits,
                       args.sort, args.time_filter, args.limit)
        if not posts:
            print("No results.", file=sys.stderr)
            return
        emit(posts, f"# Reddit search: {args.query!r} ({len(posts)} results)\n")

    elif args.cmd == "batch":
        seen, fresh = set(), []
        for q in args.queries:
            try:
                found = search(base, headers, q, args.subreddits,
                               args.sort, args.time_filter, args.limit)
            except SystemExit as e:
                print(f"  [query {q!r} failed: {e}]", file=sys.stderr)
                continue
            new = [p for p in found if p.get("permalink") not in seen]
            seen.update(p.get("permalink") for p in found)
            print(f"  [{q!r}: {len(found)} hits, {len(new)} new]", file=sys.stderr)
            fresh.extend(new)
        if not fresh:
            print("No results.", file=sys.stderr)
            return
        emit(fresh, f"# Reddit batch: {len(args.queries)} queries, "
                    f"{len(fresh)} unique posts\n")

    else:
        chunks.append(f"# Reddit threads ({len(args.refs)})\n")
        for ref in args.refs:
            post, comments = get_thread(base, headers, ref,
                                        min_score=args.min_score,
                                        max_chars=args.max_chars)
            raw.append({"post": post, "comments": comments})
            chunks.append(fmt_post_header(post))
            chunks.append(fmt_comments(comments))
            chunks.append("\n---\n")

    text = json.dumps(raw, indent=2) if args.json else "\n".join(chunks)
    print(text)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"\n  [wrote {args.out}]", file=sys.stderr)


if __name__ == "__main__":
    main()
