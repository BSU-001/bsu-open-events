"""
Rebuilds index.html (the "Upcoming Open Days" card) from the live
Bath Spa Open Days page: https://www.bathspa.ac.uk/open-days/

Reads two blocks:
  - Postgraduate Open Days  (anchor d.en.88220)
  - PGCE Open Events        (anchor d.en.88221)

For each date it:
  - names the event: "Postgraduate Open Day", or "PGCE Open Morning /
    Afternoon / Evening" depending on the start time
  - works out the year (the page doesn't give one): the next time that
    day and date fall on that weekday, from today
  - drops it once the date has passed, and any date struck through on the page
Then lists everything in date order.

If the page can't be read, the script stops with an error and the last
published card stays live.

Usage:  python build.py                 (fetch the live page)
        python build.py saved-page.html (use a saved copy, for testing)
"""
import datetime as dt
import html
import re
import sys
import urllib.request
from bs4 import BeautifulSoup

SOURCE_URL = "https://www.bathspa.ac.uk/open-days/"

# (anchor ID, heading on the page, how to name the events)
BLOCKS = [
    ("d.en.88220", "Postgraduate Open Days", "pg"),
    ("d.en.88221", "PGCE Open Events",       "pgce"),
]

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], start=1)}
WEEKDAYS = {d: i for i, d in enumerate(
    ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"])}


def load_source():
    if len(sys.argv) > 1:
        with open(sys.argv[1], encoding="utf-8") as f:
            return f.read()
    req = urllib.request.Request(SOURCE_URL, headers={
        "User-Agent": "Mozilla/5.0 (BSU open events embed updater)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def find_block(soup, anchor_id, heading):
    anchor = soup.find(id=anchor_id)
    if anchor is not None:
        block = anchor.parent.find(class_="rich-text-block")
        if block is not None:
            return block
    for block in soup.find_all(class_="rich-text-block"):
        h = block.find("h3")
        if h and h.get_text(strip=True).lower() == heading.lower() and block.find("ul"):
            return block
    return None


def parse_date(text, today):
    """'Saturday 30 January' -> the next matching date on or after today."""
    words = re.findall(r"[a-z]+|\d+", text.lower())
    day = next((int(w) for w in words if w.isdigit() and int(w) <= 31), None)
    month = next((MONTHS[w] for w in words if w in MONTHS), None)
    weekday = next((WEEKDAYS[w] for w in words if w in WEEKDAYS), None)
    year_given = next((int(w) for w in words if w.isdigit() and len(w) == 4), None)
    if day is None or month is None:
        return None
    if year_given:
        return dt.date(year_given, month, day)
    for year in range(today.year, today.year + 3):
        try:
            d = dt.date(year, month, day)
        except ValueError:
            continue
        if d >= today and (weekday is None or d.weekday() == weekday):
            return d
    return None


def start_hour(text):
    """'10 - 12pm' -> 10, '1.30 - 4pm' -> 13.5, '6pm - 8pm' -> 18. None if unclear."""
    m = re.match(r"\s*(\d{1,2})(?:[.:](\d{2}))?\s*(am|pm)?\s*[-–to]+\s*(\d{1,2})(?:[.:]\d{2})?\s*(am|pm)?",
                 text.lower())
    if not m:
        m1 = re.match(r"\s*(\d{1,2})(?:[.:](\d{2}))?\s*(am|pm)", text.lower())
        if not m1:
            return None
        h = int(m1.group(1)) % 12 + (12 if m1.group(3) == "pm" else 0)
        return h + int(m1.group(2) or 0) / 60
    h, mins, s_suffix, end_h, e_suffix = m.groups()
    h, end_h = int(h), int(end_h)
    if s_suffix:
        pm = s_suffix == "pm"
    elif e_suffix == "pm":
        # "1.30 - 4pm" is afternoon; "10 - 12pm" and "9 - 1pm" start in the morning
        pm = h <= end_h and end_h != 12
    else:
        pm = False
    return h % 12 + (12 if pm else 0) + int(mins or 0) / 60


def event_name(kind, hour):
    if kind == "pg":
        return "Postgraduate Open Day"
    if hour is None:
        return "PGCE Open Day"
    if hour < 12:
        return "PGCE Open Morning"
    if hour < 17:
        return "PGCE Open Afternoon"
    return "PGCE Open Evening"


def collect(soup, today):
    events = []
    for anchor_id, heading, kind in BLOCKS:
        block = find_block(soup, anchor_id, heading)
        if block is None:
            raise SystemExit(f"Could not find the '{heading}' block ({anchor_id})")
        items = block.find("ul").find_all("li", recursive=False) if block.find("ul") else []
        if not items:
            raise SystemExit(f"No dates found in '{heading}'")
        for li in items:
            if li.find("s"):                       # struck through = past
                continue
            lines = [t.strip() for t in li.get_text("\n").split("\n") if t.strip()]
            date = parse_date(lines[0], today) if lines else None
            if date is None or date < today:
                continue
            hour = start_hour(lines[1]) if len(lines) > 1 else None
            events.append((date, hour or 0, 0 if kind == "pg" else 1, event_name(kind, hour)))
    events.sort()
    return events


def render(events):
    if not events:
        return '<li class="none">New dates coming soon</li>'
    rows = []
    for date, _, _, name in events:
        label = f"{date.strftime('%A')} {date.day} {date.strftime('%B %Y')}"
        rows.append(f"<li>{html.escape(name)} | {label}</li>")
    return "\n      ".join(rows)


def main():
    today = dt.date.today()
    soup = BeautifulSoup(load_source(), "html.parser")
    with open("template.html", encoding="utf-8") as f:
        page = f.read()
    page = page.replace("{{EVENTS}}", render(collect(soup, today)))
    if "{{" in page:
        raise SystemExit("Some placeholders in template.html weren't filled - "
                         "check build.py and template.html are the matching versions")
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(page)
    print("index.html rebuilt")


if __name__ == "__main__":
    main()
