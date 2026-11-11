#!/usr/bin/env python3
"""Build the two-column annotated HTML from paper.json.

    python3 build.py paper.json -o paper.html --source source.txt

The script checks the data before it writes anything. On any error it prints
the errors, exits 1, and leaves an existing output file untouched.
Schema: ../references/schema.md
"""
import argparse
import base64
import html
import json
import re
import sys
import unicodedata
from pathlib import Path

KINDS = {
    "thesis": "核心论点",
    "concept": "关键概念",
    "evidence": "实证证据",
    "concession": "让步/反驳",
    "method": "方法论",
}
STYLES = ("normal", "quote", "formula")
MARK_SHARE_WARN = 0.60   # marked characters / paragraph characters
UNCOVERED_RUN = 200      # normalized characters of source not covered by any block
QUOTES = {"‘": "'", "’": "'", "“": '"', "”": '"'}
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
               ".webp": "image/webp", ".svg": "image/svg+xml"}
DROPPED = set("-­‐‑‒–—")


def esc(text):
    return html.escape(str(text), quote=True)


def normalize(text):
    """Text for source matching: no whitespace, no hyphens or dashes, plain quotes,
    ligatures expanded. Returns the string and, per character, its index in `text`."""
    out, index = [], []
    for i, ch in enumerate(text):
        for c in unicodedata.normalize("NFKC", ch):
            c = QUOTES.get(c, c)
            if c.isspace() or c in DROPPED:
                continue
            out.append(c)
            index.append(i)
    return "".join(out), index


def load(path, errors):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        errors.append("%s: %s" % (path, exc))
        return None


def need(obj, key, where, errors):
    value = obj.get(key) if isinstance(obj, dict) else None
    if not isinstance(value, str) or not value.strip():
        errors.append("%s: `%s` is missing or empty" % (where, key))
        return ""
    return value


def embed(path, where, errors):
    """Read an image file and return it as a data URI, so the page stays one file."""
    kind = IMAGE_TYPES.get(path.suffix.lower())
    if not kind:
        errors.append("%s: image `%s` is not one of %s" % (where, path.name, ", ".join(IMAGE_TYPES)))
        return ""
    try:
        return "data:%s;base64,%s" % (kind, base64.b64encode(path.read_bytes()).decode("ascii"))
    except OSError as exc:
        errors.append("%s: image: %s" % (where, exc))
        return ""


def take(block, paras, where, errors):
    """Fill `en` with the one paragraph of the source that starts with the `from` phrase."""
    phrase = " ".join(str(block["from"]).split())
    if block.get("en"):
        errors.append("%s: give `en` or `from`, not both" % where)
    elif paras is None:
        errors.append("%s: `from` needs --source" % where)
    else:
        hits = [p for p in paras if phrase and p.startswith(phrase)]
        if len(hits) == 1:
            return hits[0]
        errors.append("%s: `from` phrase `%s` starts %d paragraphs of the source; it must start exactly one"
                      % (where, phrase[:60], len(hits)))
    return ""


def place_marks(block, where, errors):
    """Resolve each mark to a (start, end, kind) span inside block['en']."""
    en, spans = block["en"], []
    for n, mark in enumerate(block.get("marks") or [], 1):
        mwhere = "%s mark %d" % (where, n)
        text, kind = mark.get("text", ""), mark.get("kind")
        if kind not in KINDS:
            errors.append("%s: kind `%s` is not one of %s" % (mwhere, kind, ", ".join(KINDS)))
            continue
        if not text:
            errors.append("%s: `text` is empty" % mwhere)
            continue
        nth = mark.get("nth", 1)
        if not isinstance(nth, int) or nth < 1:
            errors.append("%s: `nth` must be a positive integer" % mwhere)
            continue
        start = -1
        for _ in range(nth):
            start = en.find(text, start + 1)
            if start < 0:
                break
        if start < 0:
            errors.append("%s: occurrence %d of `%s` is not in `en` (marks must copy the original exactly)"
                          % (mwhere, nth, text[:60]))
            continue
        spans.append((start, start + len(text), kind))
    spans.sort()
    for a, b in zip(spans, spans[1:]):
        if b[0] < a[1]:
            errors.append("%s: marks overlap at `%s`" % (where, en[b[0]:a[1]][:40]))
    return spans


def validate(paper, base, errors, warnings, paras=None):
    meta = paper.get("meta") or {}
    need(meta, "title", "meta", errors)
    sections = paper.get("sections")
    if not isinstance(sections, list) or not sections:
        errors.append("sections: at least one section is required")
        sections = []
    blocks, ids, resolved = [], {}, []
    for s, section in enumerate(sections, 1):
        if isinstance(section, str):          # a section kept in its own file
            section = load(base / section, errors) or {}
        swhere = "section %d" % s
        need(section, "title", swhere, errors)
        if not section.get("blocks"):
            errors.append("%s: `blocks` is empty" % swhere)
        resolved.append(section)
        for block in section.get("blocks") or []:
            number = len(blocks) + 1
            where = "block %d (%s)" % (number, block.get("id") or "no id")
            block["_n"], block["_anchor"] = number, block.get("id") or "b%d" % number
            if block["_anchor"] in ids:
                errors.append("%s: id `%s` is used twice" % (where, block["_anchor"]))
            ids[block["_anchor"]] = number
            kind = block.get("type", "para")
            if kind == "figure":
                for key in ("label", "caption_en", "caption_zh"):
                    need(block, key, where, errors)
                if block.get("image"):
                    block["_image"] = embed(base / block["image"], where, errors)
            elif kind == "para":
                style = block.get("style", "normal")
                if style not in STYLES:
                    errors.append("%s: style `%s` is not one of %s" % (where, style, ", ".join(STYLES)))
                if "from" in block:
                    block["en"] = take(block, paras, where, errors)
                else:
                    block["en"] = need(block, "en", where, errors)
                block["_spans"] = place_marks(block, where, errors)
                if style != "formula":
                    need(block, "zh", where, errors)
                    note = block.get("note") or {}
                    need(note, "function", where + " note", errors)
                    need(note, "role", where + " note", errors)
                marked = sum(b - a for a, b, _ in block["_spans"])
                if block["en"] and marked / len(block["en"]) > MARK_SHARE_WARN:
                    warnings.append("%s: %d%% of the paragraph is highlighted; keep only what carries the argument"
                                    % (where, round(100 * marked / len(block["en"]))))
            else:
                errors.append("%s: type `%s` is not `para` or `figure`" % (where, kind))
            blocks.append(block)

    overview = paper.get("overview") or {}
    skeleton = overview.get("skeleton")
    if not isinstance(skeleton, list) or len(skeleton) < 3:
        errors.append("overview.skeleton: at least three stages are required")
        skeleton = []
    refs = []
    for i, stage in enumerate(skeleton, 1):
        need(stage, "stage", "overview.skeleton %d" % i, errors)
        need(stage, "text", "overview.skeleton %d" % i, errors)
        refs += [("overview.skeleton %d" % i, r) for r in stage.get("refs") or []]
    need(overview, "claim", "overview", errors)
    for key in ("strongest", "weakest"):
        item = overview.get(key) or {}
        need(item, "text", "overview.%s" % key, errors)
        refs.append(("overview.%s" % key, need(item, "ref", "overview.%s" % key, errors)))
    for where, ref in refs:
        if ref and ref not in ids:
            errors.append("%s: ref `%s` is not the id of any block" % (where, ref))
    for i, term in enumerate(paper.get("glossary") or [], 1):
        need(term, "en", "glossary %d" % i, errors)
        need(term, "zh", "glossary %d" % i, errors)
    return resolved, blocks, ids


def check_source(blocks, source, errors, warnings):
    """Every block must be found in the source; long uncovered runs are reported."""
    text, index = normalize(source)
    if not text:
        errors.append("source: the file has no text")
        return None
    covered, cursor = bytearray(len(text)), 0
    for block in blocks:
        if block.get("type", "para") == "figure":
            pieces = [block.get("caption_en", "")]
        elif block.get("style") == "formula":
            continue                           # extracted math is not reliable enough to match
        else:
            pieces = [block.get("en", "")]
        for piece in pieces:
            key = normalize(piece)[0]
            if not key:
                continue
            at = text.find(key, cursor)
            if at < 0:
                at = text.find(key)
            if at < 0:
                errors.append("block %d (%s): text is not in the source: `%s...`"
                              % (block["_n"], block["_anchor"], piece[:60]))
                continue
            covered[at:at + len(key)] = b"\x01" * len(key)
            cursor = at + len(key)
    start = None
    for i in range(len(text) + 1):
        free = i < len(text) and not covered[i]
        if free and start is None:
            start = i
        elif not free and start is not None:
            if i - start >= UNCOVERED_RUN:
                snippet = " ".join(source[index[start]:index[start] + 90].split())
                warnings.append("source not covered (%d chars) from: `%s...`" % (i - start, snippet))
            start = None
    return round(100 * sum(covered) / len(text))


def render_en(block):
    en, out, pos = block["en"], [], 0
    for start, end, kind in block["_spans"]:
        out.append(esc(en[pos:start]))
        out.append('<mark class="k-%s" title="%s">%s</mark>' % (kind, KINDS[kind], esc(en[start:end])))
        pos = end
    out.append(esc(en[pos:]))
    return "".join(out)


def render_note(block):
    note = block.get("note")
    if not note:
        return '<aside class="note empty"></aside>'
    kinds = [k for _, _, k in block.get("_spans") or []]
    lead = max(kinds, key=lambda k: (kinds.count(k), -kinds.index(k))) if kinds else "none"
    parts = ['<aside class="note n-%s">' % lead]
    if note.get("function"):
        parts.append('<span class="fn">%s</span>' % esc(note["function"]))
    if note.get("role"):
        parts.append('<p><b>逻辑角色</b>%s</p>' % esc(note["role"]))
    if note.get("technique"):
        parts.append('<p><b>论证技巧</b>%s</p>' % esc(note["technique"]))
    if note.get("doubt"):
        parts.append('<p class="doubt"><b>可疑之处</b>%s</p>' % esc(note["doubt"]))
    parts.append("</aside>")
    return "".join(parts)


def render_block(block):
    head = '<div class="row" id="%s"><div class="text"><a class="num" href="#%s">¶%d</a>' % (
        esc(block["_anchor"]), esc(block["_anchor"]), block["_n"])
    if block.get("type", "para") == "figure":
        image = ('<img src="%s" alt="%s">' % (block["_image"], esc(block["label"]))) if block.get("_image") else ""
        body = ('<div class="figure"><span class="label">%s</span>%s<p class="en">%s</p>'
                '<p class="zh">%s</p></div>'
                % (esc(block["label"]), image, esc(block["caption_en"]), esc(block["caption_zh"])))
    else:
        style = block.get("style", "normal")
        tag = "pre" if style == "formula" else "p"
        body = '<%s class="en %s">%s</%s>' % (tag, style, render_en(block), tag)
        if block.get("zh"):
            body += '<p class="zh">%s</p>' % esc(block["zh"])
    return head + body + "</div>" + render_note(block) + "</div>"


def ref_link(ref, ids):
    return '<a class="ref" href="#%s">¶%d</a>' % (esc(ref), ids[ref])


def render(paper, sections, ids, coverage):
    meta, overview = paper["meta"], paper["overview"]
    sub = [esc(meta[k]) for k in ("title_zh", "authors", "source", "course") if meta.get(k)]
    header = "<h1>%s</h1>" % esc(meta["title"])
    if sub:
        header += '<p class="sub">%s</p>' % " · ".join(sub)
    legend = "".join('<button class="chip k-%s" data-kind="%s" aria-pressed="true">%s</button>' % (k, k, v)
                     for k, v in KINDS.items())
    nav = "".join('<a href="#s%d">%s</a>' % (i, esc(s["title"])) for i, s in enumerate(sections, 1))
    nav += '<a href="#overview">论证结构总览</a>'
    body = []
    for i, section in enumerate(sections, 1):
        title = esc(section["title"])
        if section.get("title_zh"):
            title += ' <span class="zh-title">%s</span>' % esc(section["title_zh"])
        body.append('<section id="s%d"><h2>%s</h2>%s</section>'
                    % (i, title, "".join(render_block(b) for b in section["blocks"])))
    ov = ['<ol class="skeleton">']
    for stage in overview["skeleton"]:
        links = " ".join(ref_link(r, ids) for r in stage.get("refs") or [])
        ov.append('<li><b>%s</b><span>%s %s</span></li>' % (esc(stage["stage"]), esc(stage["text"]), links))
    ov.append('</ol><p class="claim"><b>一句话主张</b>%s</p><div class="verdict">' % esc(overview["claim"]))
    for key, label in (("strongest", "论证最强处"), ("weakest", "论证最弱处")):
        item = overview[key]
        ov.append('<div class="%s"><b>%s</b><p>%s %s</p></div>'
                  % (key, label, esc(item["text"]), ref_link(item["ref"], ids)))
    ov.append("</div>")
    if paper.get("glossary"):
        ov.append('<h3>术语表</h3><table class="glossary">')
        for term in paper["glossary"]:
            ov.append("<tr><td>%s</td><td>%s</td><td>%s</td></tr>"
                      % (esc(term["en"]), esc(term["zh"]), esc(term.get("note", ""))))
        ov.append("</table>")
    if coverage is not None:
        ov.append('<p class="coverage">本页收录的原文占所给全文的 %d%%（按字符计，已核对逐段出自原文）。</p>' % coverage)
    page = (Path(__file__).resolve().parent.parent / "assets" / "template.html").read_text(encoding="utf-8")
    for key, value in (("{{TITLE}}", esc(meta["title"])), ("{{HEADER}}", header), ("{{LEGEND}}", legend),
                       ("{{NAV}}", nav), ("{{BODY}}", "".join(body)), ("{{OVERVIEW}}", "".join(ov))):
        page = page.replace(key, value)
    return page


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paper")
    parser.add_argument("-o", "--output", required=True)
    parser.add_argument("--source", help="plain text of the paper; every block is checked against it")
    args = parser.parse_args()

    errors, warnings, coverage, source = [], [], None, None
    if args.source:
        try:
            source = Path(args.source).read_text(encoding="utf-8")
        except (OSError, ValueError) as exc:
            errors.append("%s: %s" % (args.source, exc))
    paper = load(args.paper, errors)
    if isinstance(paper, dict):
        paras = None if source is None else [" ".join(p.split()) for p in re.split(r"\n\s*\n", source)]
        sections, blocks, ids = validate(paper, Path(args.paper).parent, errors, warnings, paras)
        if source is not None:
            coverage = check_source(blocks, source, errors, warnings)
    elif paper is not None:
        errors.append("%s: the top level must be an object" % args.paper)
    for line in warnings:
        print("WARN  " + line)
    if errors:
        for line in errors:
            print("ERROR " + line)
        print("FAILED: %d error(s); nothing was written" % len(errors))
        return 1
    Path(args.output).write_text(render(paper, sections, ids, coverage), encoding="utf-8")
    summary = "OK: %d sections, %d blocks -> %s" % (len(sections), len(blocks), args.output)
    if coverage is not None:
        summary += " | source coverage %d%%" % coverage
    else:
        summary += " | source not checked (no --source)"
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
