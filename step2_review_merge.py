"""
Step 2: Review Merge
----------------------
Run this AFTER you've opened suggested_updates.csv and filled in the
"Decision" column for each row with either ACCEPT or REJECT.

- ACCEPT rows: merged into master_matrix.csv (updates the matching state row,
  or adds a new one if the state wasn't tracked before).
- REJECT rows: appended to rejected_log.csv, so Step 1 won't suggest the same
  finding again in a future run.
- Blank Decision: left alone, printed as a warning, not merged either way -
  this is a safety default so nothing gets silently accepted.

This is a manual/local step, not part of the scheduled GitHub Action, since
it requires your judgment call on each row first.
"""

import csv
import datetime
import os

MASTER_CSV = "master_matrix.csv"
SUGGESTED_CSV = "suggested_updates.csv"
REJECTED_LOG = "rejected_log.csv"

MASTER_FIELDS = [
    "Abbr", "State", "Status", "Law Passed", "Status Detail", "Milestones",
    "Last Updated", "Change Flag", "Suggested Status Detail Update",
    "Suggested Milestones Update", "Source Name", "Source URL",
]


def load_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    suggested = load_csv(SUGGESTED_CSV)
    if not suggested:
        print(f"No {SUGGESTED_CSV} found or it's empty - nothing to review.")
        return

    master_rows = load_csv(MASTER_CSV)
    master_by_abbr = {r["Abbr"]: r for r in master_rows}
    rejected_rows = load_csv(REJECTED_LOG)

    today = datetime.date.today().isoformat()
    accepted_count = 0
    rejected_count = 0
    skipped_count = 0

    for row in suggested:
        decision = (row.get("Decision") or "").strip().upper()
        abbr = row.get("Abbr", "")

        if decision == "ACCEPT":
            merged = {field: "" for field in MASTER_FIELDS}
            if abbr in master_by_abbr:
                merged.update(master_by_abbr[abbr])  # keep existing values as defaults
            merged["Abbr"] = abbr
            merged["State"] = row.get("State", merged.get("State", ""))
            merged["Status"] = row.get("Status", "")
            merged["Law Passed"] = row.get("Law Passed", "")
            merged["Status Detail"] = row.get("Status Detail", "")
            merged["Milestones"] = row.get("Milestones", "")
            merged["Last Updated"] = today
            merged["Source Name"] = row.get("Source Name", "")
            merged["Source URL"] = row.get("Source URL", "")
            master_by_abbr[abbr] = merged
            accepted_count += 1

        elif decision == "REJECT":
            rejected_rows.append({
                "Abbr": abbr,
                "Law Passed": row.get("Law Passed", ""),
                "Date Rejected": today,
            })
            rejected_count += 1

        else:
            print(f"  WARNING: {abbr} has no ACCEPT/REJECT decision - left untouched.")
            skipped_count += 1

    # Write updated master_matrix.csv
    with open(MASTER_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MASTER_FIELDS)
        writer.writeheader()
        for r in master_by_abbr.values():
            writer.writerow({field: r.get(field, "") for field in MASTER_FIELDS})

    # Write updated rejected_log.csv
    if rejected_rows:
        with open(REJECTED_LOG, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["Abbr", "Law Passed", "Date Rejected"])
            writer.writeheader()
            writer.writerows(rejected_rows)

    print(f"\nDone: {accepted_count} accepted and merged, {rejected_count} rejected and logged, "
          f"{skipped_count} skipped (no decision marked).")
    print("Next: commit master_matrix.csv and rejected_log.csv, then run the monthly "
          "data-refresh Action manually if you want the map updated right away.")


if __name__ == "__main__":
    main()
