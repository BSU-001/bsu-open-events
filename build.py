"""
Rebuilds index.html from the live Bath Spa Open Days page.

Pulls the event name, dates and times from two blocks on
https://www.bathspa.ac.uk/open-days/:
  - Postgraduate Open Days  (anchor d.en.88220)
  - PGCE Open Events        (anchor d.en.88221)
Dates struck through on the page (past events) are left out.

If anything can't be found, the script stops with an error and the
previously published page stays live, so the embed never goes blank.

Usage:  python build.py                 (fetch the live page)
        python build.py saved-page.html (use a saved copy, for testing)
"""
import html
import sys
import urllib.request
from bs4 import BeautifulSoup

SOURCE_URL = "https://www.bathspa.ac.uk/open-days/"

BLOCKS = {
    "PG":   ("d.en.88220", "Postgraduate Open Days"),
    "PGCE": ("d.en.88221", "PGCE Open Events"),
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


def extract(soup, anchor_id, heading):
    """Returns (event name, list of (date, time)) from one dates block."""
    block = find_block(soup, anchor_id, heading, True)
    if block is None:
        raise SystemExit(f"Could not find the '{heading}' block ({anchor_id})")
    name = block.find("h3").get_text(" ", strip=True)
    events = []
    for li in block.find("ul").find_all("li", recursive=False):
        if li.find("s"):                      # skip dates struck through as past
            continue
        # Each item is: <strong>date</strong><br>time<br>location
        lines = [t.strip() for t in li.get_text("\n").split("\n") if t.strip()]
        if not lines:
            continue
        events.append((lines[0], lines[1] if len(lines) > 1 else ""))
    if not events:
        raise SystemExit(f"No dates found in '{heading}'")
    return name, events


def render(events):
    rows = []
    for date, time in events:
        time_html = f'<span class="event-time">{html.escape(time)}</span>' if time else ""
        rows.append(f'<li><span class="event-date">{html.escape(date)}</span>{time_html}</li>')
    return "\n      ".join(rows)


def main():
    soup = BeautifulSoup(load_source(), "html.parser")
    with open("template.html", encoding="utf-8") as f:
        page = f.read()
    for key, (anchor_id, heading) in BLOCKS.items():
        name, events = extract(soup, anchor_id, heading)
        page = page.replace("{{" + key + "_NAME}}", html.escape(name))
        page = page.replace("{{" + key + "_EVENTS}}", render(events))
    if "{{" in page:
        raise SystemExit("Some placeholders in template.html weren't filled - "
                         "check build.py and template.html are the matching versions")
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(page)
    print("index.html rebuilt")


if __name__ == "__main__":
    main()
