#!/usr/bin/env python3
"""Cut a figure or table out of a PDF page as a PNG (needs poppler: pdfinfo, pdftoppm).

    python3 figure.py paper.pdf --page 3 -o page3.png                      # whole page, to look at
    python3 figure.py paper.pdf --page 3 --clip 0.2,0.08,0.8,0.52 -o fig1.png

--clip is left,top,right,bottom as fractions of the page (0,0 is the top-left corner).
"""
import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pdf")
    parser.add_argument("--page", type=int, required=True, help="page number, from 1")
    parser.add_argument("--clip", default="0,0,1,1", help="left,top,right,bottom as fractions of the page")
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument("-o", "--output", required=True, help="output .png")
    args = parser.parse_args()

    for tool in ("pdfinfo", "pdftoppm"):
        if not shutil.which(tool):
            print("ERROR %s is not installed (it is part of poppler)" % tool)
            return 1
    try:
        left, top, right, bottom = (float(v) for v in args.clip.split(","))
    except ValueError:
        left = top = right = bottom = -1.0
    if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
        print("ERROR --clip must be left,top,right,bottom with 0 <= left < right <= 1 and 0 <= top < bottom <= 1")
        return 1
    info = subprocess.run(["pdfinfo", "-f", str(args.page), "-l", str(args.page), args.pdf],
                          capture_output=True, text=True)
    size = re.search(r"Page\s+%d size:\s+([\d.]+) x ([\d.]+) pts" % args.page, info.stdout)
    if not size:
        print("ERROR page %d was not found in %s %s" % (args.page, args.pdf, info.stderr.strip()))
        return 1
    scale = args.dpi / 72.0
    width, height = float(size.group(1)) * scale, float(size.group(2)) * scale
    out = Path(args.output)
    stem = out.with_suffix("")
    done = subprocess.run(
        ["pdftoppm", "-png", "-singlefile", "-r", str(args.dpi), "-f", str(args.page), "-l", str(args.page),
         "-x", str(round(left * width)), "-y", str(round(top * height)),
         "-W", str(round((right - left) * width)), "-H", str(round((bottom - top) * height)),
         args.pdf, str(stem)], capture_output=True, text=True)
    if done.returncode != 0:
        print("ERROR pdftoppm: " + done.stderr.strip())
        return 1
    made = Path(str(stem) + ".png")
    if made != out:
        made.replace(out)
    print("OK: page %d, clip %s -> %s" % (args.page, args.clip, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
