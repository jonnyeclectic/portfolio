# tools

Standalone scripts used while working on the site and on job applications. None
of this is served to visitors — like `tests/`, it is developer tooling that
happens to live in the same repo.

Stdlib-only Python 3, no virtualenv, nothing to install.

## `reddit_query.py`

Searches Reddit and dumps threads plus comment trees as paste-ready markdown.
It exists because Reddit refuses Anthropic's crawler, so WebFetch cannot read
reddit.com at all — this fetches the same content over Reddit's own APIs.

```sh
tools/reddit_query.py search "Affirm interview process"
tools/reddit_query.py search "Affirm" -r leetcode -r cscareerquestions --sort new -t year
tools/reddit_query.py thread https://www.reddit.com/r/leetcode/comments/abc123/...
tools/reddit_query.py batch -q "Affirm interview" -q "Affirm system design" -o affirm.md
```

`--with-comments` pulls the full comment tree for every search hit; `-o FILE`
writes the markdown as well as printing it; `--json` emits the raw structures
instead.

### Two transports, picked automatically

**OAuth JSON**, used when credentials are present. Full fidelity: scores,
nested comment trees, ~100 requests/minute.

```sh
export REDDIT_CLIENT_ID=...        # REDDIT_CLIENT and REDDIT_SECRET also work
export REDDIT_CLIENT_SECRET=...
```

Create a "script" app at <https://www.reddit.com/prefs/apps> to get a pair.
Reddit also asks for a descriptive User-Agent:
`export REDDIT_USER_AGENT="python:reddit-query:0.2 (by /u/YOUR_USERNAME)"`.

**Atom RSS**, the anonymous fallback. As of 2026 Reddit returns 403 on every
public `.json` endpoint regardless of User-Agent — `old.reddit.com`,
`api.reddit.com` and a browser User-Agent all fail the same way — but the
`.rss` feeds still serve full post and comment bodies. It costs: no scores (so
`--min-score` is inert), a flat comment list instead of a tree, and a rate limit
of roughly one request per 40-second window, which the script rides out by
honoring the `x-ratelimit-*` headers. A long RSS run is best started in the
background.

RSS also under-reports comments — one thread returned 5 over RSS against 22 over
the API. Authenticate whenever comment detail matters.

### Things that broke before, so they have tests

- **Always request gzip.** Uncompressed Reddit search JSON runs 200-300KB and
  gets truncated in transit; retrying uncompressed never succeeds. Compressed,
  it arrives intact.
- **Truncated JSON is a transport failure, not a payload**, so it is retried
  with backoff. Truncated RSS is different — it is salvaged in place by cutting
  back to the last complete `</entry>`, because a partial feed still holds every
  entry that arrived whole.
- **Feed content is escaped HTML inside escaped XML**, so it needs unescaping
  twice before `&amp;#39;` becomes an apostrophe.
- **A feed that declares a DTD is refused.** `xml.etree` expands internal
  entities, which makes a hostile internal subset an amplification vector.
  Reddit's feeds never carry a DOCTYPE, so rejecting one costs nothing.
- **A post id that is not a plain id is refused**, because it is interpolated
  into a request path — a `?` in the argument would otherwise rewrite the query
  string rather than name a post.
- **Every request is checked against a two-host allow-list.** Nothing can reach
  another host by construction; the check makes that an enforced invariant
  rather than one you have to re-derive by reading the callers.

### Snyk

`snyk code test tools/` reports five findings, all reviewed and none actionable:

- **Insecure Xml Parser (Python < 3.11)** — the rule's own title is the answer;
  this runs on 3.14, and the DTD refusal above closes it on older runtimes too.
- **SSRF ×4** — the taint is a CLI argument reaching `urlopen`, which is what a
  Reddit fetcher does. Every URL is built from a constant base with urlencoded
  params, and `_check_host` enforces it. Snyk does not model that as a
  sanitizer, so the findings persist; making them disappear would mean
  restructuring for the taint engine rather than for correctness.
- **Path Traversal (Low)** — `-o` writes where the person running it says to.

## Tests

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
```

77 tests, fully offline — every one either exercises a pure function or
substitutes a fake for `urlopen`. Nothing here touches the network, so the suite
is safe to run against a spent rate-limit budget.
