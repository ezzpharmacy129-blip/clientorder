#!/usr/bin/env python3
"""Build production CSS from the readable source using only Python stdlib."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "static" / "style.css"
DST = ROOT / "static" / "style.min.css"

def minify_css(source: str) -> str:
    out = []
    i = 0
    in_string = False
    quote = ""
    in_comment = False
    prev = ""

    while i < len(source):
        c = source[i]
        n = source[i + 1] if i + 1 < len(source) else ""

        if in_comment:
            if c == "*" and n == "/":
                in_comment = False
                i += 2
            else:
                i += 1
            continue

        if not in_string and c == "/" and n == "*":
            in_comment = True
            i += 2
            continue

        if c in ("'", '"') and prev != "\\":
            if not in_string:
                in_string = True
                quote = c
            elif quote == c:
                in_string = False
            out.append(c)
            prev = c
            i += 1
            continue

        if not in_string and c.isspace():
            if out and not out[-1].isspace():
                out.append(" ")
            i += 1
            continue

        out.append(c)
        prev = c
        i += 1

    value = "".join(out)
    value = re.sub(r"\s*([{}:;,>+~])\s*", r"\1", value)
    value = value.replace(";}", "}")
    value = re.sub(r"\s*!important", "!important", value)
    return value.strip()

source = SRC.read_text(encoding="utf-8")
minified = minify_css(source)
DST.write_text(minified + "\n", encoding="utf-8")
print(f"Built {DST} ({len(minified)} bytes) from {len(source)} bytes")
