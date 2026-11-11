#!/bin/bash
# Acceptance run for build.py against the fictional sample in examples/sample.
# Run: bash tests/build_e2e.sh
#
# Ways the builder can fail, each covered below:
#   fidelity:  a paragraph reworded against the source, a mark that is not a verbatim substring,
#              overlapping marks, `nth` past the last occurrence, a dropped paragraph going unnoticed
#   structure: missing translation, missing note role, unknown mark kind, duplicate id,
#              overview ref to an id that does not exist, a section file that is missing
#   from:      the wrong paragraph taken, a phrase that is ambiguous or absent, `from` used with
#              `en` or without a source
#   figures:   an image left as an external file reference, an image file that is missing,
#              a file type that is not an image; figure.py cutting the wrong region or size
#   output:    a failed build overwrites the previous HTML; markup in paper text is not escaped;
#              `nth` highlights the wrong occurrence; a mark is lost or doubled in the page
# Expected values come from the sample data as written (13 marks, 10 blocks, 3 sections),
# not from a previous run of the builder.
ROOT=$(cd "$(dirname "$0")/.." && pwd)
BUILD="python3 $ROOT/paper-annotation/scripts/build.py"
W=$(mktemp -d "${TMPDIR:-/tmp}/paperann.XXXX"); cp "$ROOT"/examples/sample/*.json "$ROOT"/examples/sample/*.png "$ROOT"/examples/sample/source.txt "$W"; cd "$W" || exit 1
pass=0; fail=0
ok() { pass=$((pass+1)); echo "PASS $1"; }
no() { fail=$((fail+1)); echo "FAIL $1"; [ -n "$2" ] && echo "$2" | sed 's/^/    /'; }
# mutate <file> <python statement on d> : writes mutant.json (and keeps sec-02.json reachable)
mutate() { python3 - "$1" "$2" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
exec(sys.argv[2])
json.dump(d, open("mutant.json" if sys.argv[1] == "paper.json" else "sec-02.json", "w", encoding="utf-8"), ensure_ascii=False)
PY
}
# rejected <name> <expected error text> [paper file]
rejected() {
  out=$($BUILD "${3:-mutant.json}" -o out.html --source source.txt 2>&1); code=$?
  if [ $code -eq 1 ] && echo "$out" | grep -q "$2" && cmp -s out.html good.html; then ok "$1"; else no "$1" "exit $code: $out"; fi
}

out=$($BUILD paper.json -o out.html --source source.txt 2>&1); code=$?
[ $code -eq 0 ] && echo "$out" | grep -q "OK: 3 sections, 10 blocks" && ok "sample builds" || no "sample builds" "$out"
cp out.html good.html
[ "$(grep -o '<mark ' out.html | wc -l | tr -d ' ')" = 13 ] && ok "13 marks rendered" || no "13 marks rendered"
[ "$(grep -o 'class="row"' out.html | wc -l | tr -d ' ')" = 10 ] && ok "10 rows rendered" || no "10 rows rendered"
grep -q '<a class="ref" href="#p7">¶9</a>' out.html && ok "overview ref links to the ninth block" || no "overview ref links to the ninth block"
echo "$out" | grep -q "source not covered.*References" && ok "uncovered references reported" || no "uncovered references reported" "$out"
echo "$out" | grep -Eq "source coverage [0-9]+%" && ok "coverage reported" || no "coverage reported" "$out"

# a dropped paragraph must show up as an uncovered passage naming its opening words
mutate paper.json 'del d["sections"][2]["blocks"][1]; d["overview"]["weakest"]["ref"]="p6"; d["overview"]["skeleton"][3]["refs"]=["p6"]'
out=$($BUILD mutant.json -o dropped.html --source source.txt 2>&1)
echo "$out" | grep -q "source not covered.*This objection has force" && ok "dropped paragraph reported" || no "dropped paragraph reported" "$out"

mutate paper.json 'd["sections"][0]["blocks"][0]["en"]=d["sections"][0]["blocks"][0]["en"].replace("surprisingly little","little")'
rejected "reworded paragraph rejected" "block 1 (p1): text is not in the source"
mutate paper.json 'd["sections"][0]["blocks"][2]["marks"][0]["text"]="annotation improves understanding"'
rejected "non-verbatim mark rejected" "is not in .en."
mutate paper.json 'd["sections"][0]["blocks"][1]["marks"][0]["nth"]=2'
rejected "overlapping marks rejected" "marks overlap"
mutate paper.json 'd["sections"][0]["blocks"][1]["marks"][0]["nth"]=3'
rejected "nth past last occurrence rejected" "occurrence 3"
mutate paper.json 'd["sections"][0]["blocks"][0]["zh"]=""'
rejected "missing translation rejected" "block 1 (p1): .zh. is missing"
mutate paper.json 'del d["sections"][0]["blocks"][0]["note"]["role"]'
rejected "missing note role rejected" "note: .role. is missing"
mutate paper.json 'd["sections"][0]["blocks"][0]["marks"][0]["kind"]="important"'
rejected "unknown mark kind rejected" "kind .important."
mutate paper.json 'd["sections"][0]["blocks"][1]["id"]="p1"'
rejected "duplicate id rejected" "id .p1. is used twice"
mutate paper.json 'd["overview"]["strongest"]["ref"]="p99"'
rejected "dangling overview ref rejected" "ref .p99. is not the id"
cp sec-02.json sec-02.keep
mutate sec-02.json 'd["blocks"][2]["image"]="gone.png"'
rejected "missing image rejected" "block 6 (t1): image" paper.json
mutate sec-02.json 'd["blocks"][2]["image"]="source.txt"'
rejected "non-image file rejected" "is not one of" paper.json
cp sec-02.keep sec-02.json
mutate paper.json 'd["sections"][1]="sec-missing.json"'
rejected "missing section file rejected" "sec-missing.json"

# `from`: the paragraph text is taken from the source, so the page must come out identical to the
# one built from the typed `en`; a phrase that starts no paragraph or several is rejected
mutate paper.json 'b=d["sections"][0]["blocks"][2]; del b["en"]; b["from"]="We argue that"'
$BUILD mutant.json -o from.html --source source.txt >/dev/null 2>&1
cmp -s from.html good.html && ok "from takes the paragraph from the source" || no "from takes the paragraph from the source"
mutate paper.json 'b=d["sections"][0]["blocks"][2]; del b["en"]; b["from"]="We "'
rejected "from phrase starting several paragraphs rejected" "starts 3 paragraphs"
mutate paper.json 'b=d["sections"][0]["blocks"][2]; del b["en"]; b["from"]="marginal annotation improves"'
rejected "from phrase from the middle of a paragraph rejected" "starts 0 paragraphs"
mutate paper.json 'd["sections"][0]["blocks"][2]["from"]="We argue that"'
rejected "en together with from rejected" "not both"
mutate paper.json 'b=d["sections"][0]["blocks"][2]; del b["en"]; b["from"]="We argue that"'
out=$($BUILD mutant.json -o nosource.html 2>&1); [ $? -eq 1 ] && [ ! -e nosource.html ] && echo "$out" | grep -q "needs --source" && ok "from without --source rejected" || no "from without --source rejected" "$out"

# nth selects the second occurrence; markup in the text is escaped
mutate paper.json 'b=d["sections"][0]["blocks"][1]; b["marks"]=[{"text":"argument map","kind":"concept","nth":2}]; d["sections"][0]["blocks"][0]["zh"]="<script>alert(1)</script>"'
$BUILD mutant.json -o nth.html --source source.txt >/dev/null 2>&1
grep -q 'claim. An <mark class="k-concept" title="关键概念">argument map</mark> is not' nth.html && ok "nth marks the second occurrence" || no "nth marks the second occurrence"
grep -q '&lt;script&gt;alert(1)&lt;/script&gt;' nth.html && ! grep -q '<script>alert' nth.html && ok "markup in text escaped" || no "markup in text escaped"

grep -q '<img src="data:image/png;base64,' good.html && ! grep -q 'table1.png' good.html && ok "figure image embedded in the page" || no "figure image embedded in the page"

# figure.py: a 612 x 792 pt page cut to the right half of its middle band at 72 dpi is 306 x 396 px,
# and that region of the fixture is solid red
FIG="python3 $ROOT/paper-annotation/scripts/figure.py"
if python3 -c "import PIL" 2>/dev/null && command -v pdftoppm >/dev/null; then
  python3 -c "
from PIL import Image, ImageDraw
im = Image.new('RGB', (612, 792), 'white'); ImageDraw.Draw(im).rectangle([306, 198, 611, 593], fill=(255, 0, 0))
im.save('page.pdf', resolution=72)"
  $FIG page.pdf --page 1 --clip 0.5,0.25,1,0.75 --dpi 72 -o cut.png >/dev/null 2>&1
  got=$(python3 -c "
from PIL import Image
im = Image.open('cut.png').convert('RGB'); print(im.size, im.getpixel((5, 5))[0] > 200, im.getpixel((300, 390))[1] < 60)")
  [ "$got" = "(306, 396) True True" ] && ok "figure.py cuts the requested region" || no "figure.py cuts the requested region" "$got"
  out=$($FIG page.pdf --page 1 --clip 0.8,0.2,0.3,0.9 -o bad.png 2>&1); [ $? -eq 1 ] && [ ! -e bad.png ] && ok "figure.py rejects an inverted clip" || no "figure.py rejects an inverted clip" "$out"
  out=$($FIG page.pdf --page 9 -o bad.png 2>&1); [ $? -eq 1 ] && ok "figure.py rejects a page that does not exist" || no "figure.py rejects a page that does not exist" "$out"
else
  echo "SKIP figure.py checks (need PIL and poppler)"
fi

echo "$pass passed, $fail failed  (workdir $W)"
[ $fail -eq 0 ]
