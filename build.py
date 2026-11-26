"""
Rebuilds index.html from the live Bath Spa Open Days page.

Pulls four blocks from https://www.bathspa.ac.uk/open-days/:
  - Postgraduate Open Days dates   (anchor d.en.88220)
  - PGCE Open Events dates         (anchor d.en.88221)
  - Postgraduate Open Days intro   (anchor d.en.110360)
  - PGCE Open Events intro         (anchor d.en.110361)

If anything can't be found, the script stops with an error and the
previously published page stays live, so the embed never goes blank.

Usage:  python build.py                 (fetch the live page)
        python build.py saved-page.html (use a saved copy, for testing)
"""
import sys
import urllib.request
from bs4 import BeautifulSoup

SOURCE_URL = "https://www.bathspa.ac.uk/open-days/"
SITE = "https://www.bathspa.ac.uk"

BLOCKS = {
    "PG_DATES":   ("d.en.88220",  "Postgraduate Open Days", True),
    "PGCE_DATES": ("d.en.88221",  "PGCE Open Events",       True),
    "PG_INTRO":   ("d.en.110360", "Postgraduate Open Days", False),
    "PGCE_INTRO": ("d.en.110361", "PGCE Open Events",       False),
}


def load_source():
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as f:
            return f.read()
    req = urllib.request.Request(SOURCE_URL, headers={
        "User-Agent": "Mozilla/5.0 (BSU open events embed updater)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def find_block(soup, anchor_id, heading, want_list):
    # 1. By the CMS anchor ID
    anchor = soup.find(id=anchor_id)
    if anchor is not None:
        block = anchor.parent.find(class_="rich-text-block")
        if block is not None:
            return block
    # 2. Fallback: by heading, choosing the dates block (has a list) or the intro block (no list)
    for block in soup.find_all(class_="rich-text-block"):
        h = block.find("h3")
        if not h or h.get_text(strip=True).lower() != heading.lower():
            continue
        if bool(block.find("ul")) == want_list:
            return block
    return None


def absolutise(tag):
    for a in tag.find_all("a", href=True):
        if a["href"].startswith("/"):
            a["href"] = SITE + a["href"]


def extract(soup, anchor_id, heading, want_list):
    block = find_block(soup, anchor_id, heading, want_list)
    if block is None:
        raise SystemExit(f"Could not find the '{heading}' block ({anchor_id})")
    if want_list:
        ul = block.find("ul")
        items = ul.find_all("li", recursive=False) if ul else []
        if not items:
            raise SystemExit(f"No dates found in '{heading}'")
        for li in items:
            absolutise(li)
        return "\n      ".join(str(li) for li in items)
    paras = block.find_all("p", recursive=False)
    if not paras:
        raise SystemExit(f"No intro text found in '{heading}'")
    for p in paras:
        absolutise(p)
    return "\n      ".join(str(p) for p in paras)


def main():
    soup = BeautifulSoup(load_source(), "html.parser")
    with open("template.html", encoding="utf-8") as f:
        page = f.read()
    for key, (anchor_id, heading, want_list) in BLOCKS.items():
        page = page.replace("{{" + key + "}}", extract(soup, anchor_id, heading, want_list))
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(page)
    print("index.html rebuilt")


if __name__ == "__main__":
    main()
