#!/usr/bin/env python3
"""Extract readable text from the resume PDF, stdlib only.

The PDF is a Google Docs export (``/Producer (Skia/PDF … Google Docs
Renderer)``) with subsetted fonts, so the page content streams hold *glyph
ids*, not characters. Two consequences shape this module:

  * Pulling ``(literal) Tj`` strings the naive way returns zero characters.
    A diff of two exports then looks reassuringly "identical" while the text
    has in fact changed completely. Every glyph id has to be mapped back
    through the font's **ToUnicode CMap** (``beginbfchar`` / ``beginbfrange``).
  * Those CMaps are themselves inside compressed streams, so the whole file
    has to be inflated before the mapping can even be read.

The renderer also emits ``Td``/``TD`` between individual glyphs to place them,
so treating those as line breaks shreds words into "F o r t". Only ``T*`` and
``ET`` are treated as breaks here, and the result is whitespace-normalised
into one flat string — enough to assert which claims a given export carries,
which is all the tests need. It is not a layout-preserving extractor.
"""

import re
import zlib
from pathlib import Path

# <hex> Tj  |  [ <hex> kern <hex> ] TJ  |  a line break
_TOKEN = re.compile(rb"\[([^\]]*)\]\s*TJ|<([0-9A-Fa-f]+)>\s*Tj|\b(?:T\*|ET)\b")
_HEX = re.compile(rb"<([0-9A-Fa-f]+)>")
_STREAM = re.compile(rb"stream\r?\n(.*?)\r?\nendstream", re.S)
_BFCHAR = re.compile(rb"beginbfchar(.*?)endbfchar", re.S)
_BFRANGE = re.compile(rb"beginbfrange(.*?)endbfrange", re.S)
_PAIR = re.compile(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>")
_TRIPLE = re.compile(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>")


def _inflate(raw):
    """Every stream we can decompress. Images and the like simply fail."""
    out = []
    for m in _STREAM.finditer(raw):
        try:
            out.append(zlib.decompress(m.group(1)))
        except zlib.error:
            continue
    return out


def _build_cmap(streams):
    """glyph id -> character, from the ToUnicode CMaps."""
    cmap = {}
    for data in streams:
        for m in _BFCHAR.finditer(data):
            for src, dst in _PAIR.findall(m.group(1)):
                cmap[int(src, 16)] = chr(int(dst, 16))
        for m in _BFRANGE.finditer(data):
            for lo, hi, dst in _TRIPLE.findall(m.group(1)):
                lo, hi, dst = int(lo, 16), int(hi, 16), int(dst, 16)
                for i in range(lo, hi + 1):
                    cmap[i] = chr(dst + i - lo)
    return cmap


def extract_text(path):
    """The PDF's text as one whitespace-normalised string.

    Raises ValueError if the ToUnicode CMap cannot be read, rather than
    returning empty text. A silent "" here would make every "this claim is
    absent" assertion pass for the wrong reason, which is precisely the
    failure this module exists to prevent.
    """
    streams = _inflate(Path(path).read_bytes())
    cmap = _build_cmap(streams)
    if not cmap:
        raise ValueError(
            f"{path}: no ToUnicode CMap found, so glyph ids cannot be decoded. "
            "If the PDF was re-exported from a different tool its text may be "
            "encoded another way, and this extractor needs updating — do not "
            "treat the absence of text as the absence of a claim.")

    def decode(hex_str):
        return "".join(cmap.get(int(hex_str[i:i + 4], 16), "")
                       for i in range(0, len(hex_str), 4))

    parts = []
    for data in streams:
        if _BFCHAR.search(data) or _BFRANGE.search(data):
            continue  # a CMap, not page content
        for tok in _TOKEN.finditer(data):
            array, single = tok.group(1), tok.group(2)
            if array is not None:
                parts.append("".join(decode(h.decode())
                                     for h in _HEX.findall(array)))
            elif single is not None:
                parts.append(decode(single.decode()))
            else:
                parts.append(" ")
    return re.sub(r"\s+", " ", "".join(parts)).strip()
