#!/usr/bin/env python3
"""One-off helper for this example: turn raw.txt (pdftotext output) into source.txt in reading
order, and merge it with the hand-written annotations in ann-*.json into paper.json + sec-*.json.

The English text is never typed by hand: source.txt gets one paragraph per line, cut out of raw.txt
at the start phrases given in the annotation files, and each block carries that phrase as `from`,
which build.py resolves against source.txt. Fixes applied to the extracted text are listed in FIXES.
"""
import glob
import json
import unicodedata
from pathlib import Path

HERE = Path(__file__).parent
raw = (HERE / "raw.txt").read_text(encoding="utf-8").split("\n")

# line ranges of raw.txt (1-based, inclusive) in reading order; pdftotext interleaves columns,
# page furniture, tables and the box with the body text
BODY = [(9, 38), (40, 57), (63, 64), (66, 81), (86, 113), (116, 149), (201, 214), (216, 253), (256, 278),
        (280, 298), (300, 314), (316, 351), (386, 438), (439, 491), (534, 557), (635, 656), (659, 668),
        (670, 685), (688, 714), (754, 756), (758, 789), (717, 753), (889, 900), (902, 951), (954, 1013),
        (1016, 1028)]
BOX = [(560, 623)]
CAPTIONS = [(172, 172), (353, 353), (492, 492), (527, 532), (627, 633), (790, 791)]
FIXES = [("P ublished", "Published"),                       # drop cap
         ("100fold", "100-fold"), ("1,000fold", "1,000-fold"),  # hyphens lost at line breaks
         ("discoveryoriented", "discovery-oriented"), ("poststudy", "post-study"),
         ("KaplanMeier", "Kaplan-Meier"), ("hypothesisgenerating", "hypothesis-generating"),
         ("βn", "βⁿ"), ("α]n", "α]ⁿ"), ("βi ", "βᵢ "), ("10−4", "10⁻⁴")]  # super/subscripts flattened


def text(ranges):
    words = " ".join(" ".join(raw[a - 1:b]) for a, b in ranges)
    words = unicodedata.normalize("NFKC", words).replace("⁄", "/")   # ligatures; fraction slash
    words = " ".join(words.split())
    for old, new in FIXES:
        words = words.replace(old, new)
    return " ".join(words.split())


used = set()
for a, b in BODY + BOX + CAPTIONS:
    used.update(range(a, b + 1))
T = text(BODY) + " " + text(BOX)

sections = []
for name in sorted(glob.glob(str(HERE / "ann-*.json"))):
    sections += json.loads(Path(name).read_text(encoding="utf-8"))

marks = []                                                   # (position, kind, section index, item index)
for s, section in enumerate(sections):
    paras = [i for i in section["items"] if "p" in i]
    if not section.get("untitled"):
        key = section["title"] + " " + paras[0]["p"]
        assert T.count(key) == 1, "heading not found once: " + key
        marks.append((T.find(key), "h", s, None))
    for i, item in enumerate(section["items"]):
        if "p" in item:
            assert T.count(item["p"]) == 1, "start phrase not found once: " + item["p"]
            marks.append((T.find(item["p"]), "p", s, i))
marks.sort()
assert marks[0][0] == 0, "text before the first start phrase: " + T[:marks[0][0]]
ordered = []
for (pos, kind, s, i), nxt in zip(marks, marks[1:] + [(len(T),)]):
    piece = T[pos:nxt[0]].strip()
    ordered.append(piece)
    if kind == "p":
        sections[s]["items"][i]["en"] = piece

number, out_sections = 0, []
for s, section in enumerate(sections, 1):
    blocks = []
    for item in section["items"]:
        if "p" in item:
            number += 1
            blocks.append({"id": "p%d" % number, "from": item["p"], "zh": item["zh"],
                           "marks": item.get("marks", []), "note": item["note"]})
        else:
            blocks.append(item)
    name = "sec-%02d.json" % s
    (HERE / name).write_text(json.dumps({"title": section["title"], "title_zh": section.get("title_zh", ""),
                                         "blocks": blocks}, ensure_ascii=False, indent=2), encoding="utf-8")
    out_sections.append(name)

top = json.loads((HERE / "top.json").read_text(encoding="utf-8"))
top["sections"] = out_sections
(HERE / "paper.json").write_text(json.dumps(top, ensure_ascii=False, indent=2), encoding="utf-8")

rest = [raw[n - 1] for n in range(1, len(raw) + 1) if n not in used]
(HERE / "source.txt").write_text(
    "\n\n".join(ordered) + "\n\n" + "\n\n".join(text([c]) for c in CAPTIONS)
    + "\n\n---- not part of the running text: title block, page furniture, table cells, references ----\n\n"
    + unicodedata.normalize("NFKC", "\n".join(rest)), encoding="utf-8")
print("paragraphs: %d, sections: %d, body characters: %d" % (number, len(sections), len(T)))
