"""
Step 3+4: Monthly Data Refresh + Email Digest
-----------------------------------------------
Runs on a monthly GitHub Actions schedule AFTER Step 2 (human ACCEPT/REJECT
review) has been merged into master_matrix.csv.

Inputs:
    master_matrix.csv  - the approved, current-state matrix

Outputs:
    outputs/epr-data.json            - the live data feed the map reads via its
                                        "dataUrl" prop. Commit this file
                                        somewhere with a stable public URL (e.g.
                                        GitHub Pages, or raw.githubusercontent.com).
    outputs/monthly_digest_email.html - draft email copy (simple HTML, links
                                        open in a new window), for your review/
                                        approval before you send it on.

This script does NOT auto-send anything and does NOT touch the map's HTML/CSS.
A human reviews and sends the digest email; the map just re-fetches
epr-data.json on next load.

"""

import csv
import datetime
import json
import os

# NOTE: epr-data.json is written to the repo ROOT (not a subfolder) so the
# raw.githubusercontent.com URL you already gave to Claude Design keeps working
# without changes.
MASTER_CSV = "master_matrix.csv"
DATA_OUTPUT_PATH = "epr-data.json"
DIGEST_OUTPUT_PATH = "monthly_digest_email.html"
DAYS_LOOKBACK = 30

DISCLAIMER = (
  "Data subject to change as legislation develops. Check state legislation "
    "and Producer Responsibility Organizations (PROs) for the most "
    "up-to-date information. This map reflects legislative research "
    "compiled from public sources and is provided for informational "
    "purposes only."
)


def load_matrix(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def recent_changes(rows, days=DAYS_LOOKBACK):
    cutoff = datetime.date.today() - datetime.timedelta(days=days)
    recent = []
    for row in rows:
        raw_date = (row.get("Last Updated") or "").strip()
        if not raw_date:
            continue
        try:
            updated = datetime.datetime.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError:
            continue
        if updated >= cutoff:
            recent.append(row)
    return recent


def split_sources(name_field, url_field):
    """
    Splits ';'-delimited source names and ';'-delimited URLs into paired
    {label, url} entries. Falls back gracefully if counts don't match.
    """
    names = [n.strip() for n in (name_field or "").split(";") if n.strip()]
    urls = [u.strip() for u in (url_field or "").split(";") if u.strip()]

    if not names or not urls:
        return []

    if len(names) == len(urls):
        return [{"label": n, "url": u} for n, u in zip(names, urls)]

    # Mismatched counts: don't guess pairings, just attach all urls to a joined label
    return [{"label": " / ".join(names), "url": u} for u in urls]


def build_epr_data_json(rows):
    """
    Converts master_matrix.csv rows into the map's JSON schema, plus the
    bagging-scope fields the current map schema doesn't define yet.
    Adjust the CSV column names below (left side) if yours differ.
    """
    out = []
    for r in rows:
        milestones_raw = (r.get("Milestones") or "").strip()
        milestones = [m.strip() for m in milestones_raw.split("|") if m.strip()]

        sources = split_sources(r.get("Source Name"), r.get("Source URL"))

        out.append({
            "abbr": (r.get("Abbr") or "").strip(),
            "name": (r.get("State") or "").strip(),
            "stage": "passed" if "pass" in (r.get("Status") or "").lower() else "pending",
            "lastUpdated": (r.get("Last Updated") or "").strip(),
            "lawPassed": (r.get("Law Passed") or "").strip(),
            "status": (r.get("Status Detail") or "").strip(),
            "milestones": milestones,
            "sources": sources
        })
    return out


def build_digest_email(changed_rows):
    if not changed_rows:
        return None

    bullets = []
    footnotes = []
    footnote_num = 1

    for r in changed_rows:
        state = r.get("State", "")
        detail = (r.get("Status Detail") or "").strip()
        milestone = (r.get("Milestones") or "").strip()
        takeaway = milestone if milestone else detail

        sources = split_sources(r.get("Source Name"), r.get("Source URL"))
        markers = []
        for s in sources:
            markers.append(f'<sup><a href="{s["url"]}" target="_blank" rel="noopener">[{footnote_num}]</a></sup>')
            footnotes.append(
                f'<li id="fn{footnote_num}">[{footnote_num}] {s["label"]}: '
                f'<a href="{s["url"]}" target="_blank" rel="noopener">{s["url"]}</a></li>'
            )
            footnote_num += 1

        marker_str = " " + "".join(markers) if markers else ""
        bullets.append(f"<li><strong>{state}:</strong> {takeaway}{marker_str}</li>")

    body = (
        "<!DOCTYPE html>\n<html>\n<head><meta charset=\"utf-8\"></head>\n<body "
        "style=\"font-family: Arial, sans-serif; font-size: 14px; color: #222;\">\n"
        "<p><strong>Subject: US EPR Packaging Update - Monthly Digest</strong></p>\n"
        "<p>Here's what changed in the last 30 days:</p>\n"
        "<ul>\n" + "\n".join(bullets) + "\n</ul>\n"
        + ("<p><strong>Sources:</strong></p>\n<ol>\n" + "\n".join(footnotes) + "\n</ol>\n" if footnotes else "")
        + f"<p style=\"font-size: 12px; color: #666;\">{DISCLAIMER}</p>\n"
        + "<p style=\"font-size: 12px; color: #999;\"><em>(Draft only - review and edit before sending to customers.)</em></p>\n"
        "</body>\n</html>"
    )
    return body


def main():
    rows = load_matrix(MASTER_CSV)

    # Step 3: refresh the live data feed the map reads (no HTML regeneration)
    data = build_epr_data_json(rows)
    with open(DATA_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"Data feed refreshed: {DATA_OUTPUT_PATH}")

    # Step 4: draft monthly digest email (only for rows changed in last 30 days)
    changed = recent_changes(rows)
    digest = build_digest_email(changed)
    if digest:
        with open(DIGEST_OUTPUT_PATH, "w", encoding="utf-8") as f:
            f.write(digest)
        print(f"Digest drafted: {DIGEST_OUTPUT_PATH} - open this file in the repo and read it, then send yourself.")
    else:
        print("No changes in the last 30 days; no digest generated.")


if __name__ == "__main__":
    main()
