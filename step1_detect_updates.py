"""
Step 1: EPR Legislation Detection
----------------------------------
Runs on a schedule (recommend monthly, same cadence as Step 3/4, or more often
if you want faster alerts). Searches for US state EPR packaging legislation
changes, focused on "bagging" (poly, plastic film, paper, mesh) but not
excluding other packaging materials.

This script NEVER touches master_matrix.csv. It only writes suggested_updates.csv
for human review (Step 2). This is a frozen design decision.

REQUIRES: an Anthropic API key (set as the ANTHROPIC_API_KEY secret in your
GitHub repo) because this script uses Claude + the web_search tool to do the
actual research. Web search from a plain Python script has no research
judgment on its own - Claude is doing the reading and evaluating here, not
just returning raw search hits.

Output: suggested_updates.csv (one row per state with a notable finding this run)
         detection_summary.txt (short human-readable summary of what changed)

Both are written fresh each run - this script does not merge, dedupe against,
or compare to previous runs. Step 2 (human review) is where judgment calls
about "is this new / already known / a duplicate" happen.
"""

import csv
import json
import os
import re
import urllib.request

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]  # required - will KeyError if missing
API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-6"

MASTER_CSV = "master_matrix.csv"
SUGGESTED_CSV = "suggested_updates.csv"
SUMMARY_TXT = "detection_summary.txt"
REJECTED_LOG = "rejected_log.csv"

# All 50 states - detection scans broadly; master_matrix.csv only needs to
# contain states with actual EPR activity, so most will simply come back
# "no notable activity" and won't appear in the output.
ALL_STATES = [
    "Alabama","Alaska","Arizona","Arkansas","California","Colorado","Connecticut",
    "Delaware","Florida","Georgia","Hawaii","Idaho","Illinois","Indiana","Iowa",
    "Kansas","Kentucky","Louisiana","Maine","Maryland","Massachusetts","Michigan",
    "Minnesota","Mississippi","Missouri","Montana","Nebraska","Nevada",
    "New Hampshire","New Jersey","New Mexico","New York","North Carolina",
    "North Dakota","Ohio","Oklahoma","Oregon","Pennsylvania","Rhode Island",
    "South Carolina","South Dakota","Tennessee","Texas","Utah","Vermont",
    "Virginia","Washington","West Virginia","Wisconsin","Wyoming"
]

STATE_ABBR = {
    "Alabama":"AL","Alaska":"AK","Arizona":"AZ","Arkansas":"AR","California":"CA",
    "Colorado":"CO","Connecticut":"CT","Delaware":"DE","Florida":"FL","Georgia":"GA",
    "Hawaii":"HI","Idaho":"ID","Illinois":"IL","Indiana":"IN","Iowa":"IA",
    "Kansas":"KS","Kentucky":"KY","Louisiana":"LA","Maine":"ME","Maryland":"MD",
    "Massachusetts":"MA","Michigan":"MI","Minnesota":"MN","Mississippi":"MS",
    "Missouri":"MO","Montana":"MT","Nebraska":"NE","Nevada":"NV",
    "New Hampshire":"NH","New Jersey":"NJ","New Mexico":"NM","New York":"NY",
    "North Carolina":"NC","North Dakota":"ND","Ohio":"OH","Oklahoma":"OK",
    "Oregon":"OR","Pennsylvania":"PA","Rhode Island":"RI","South Carolina":"SC",
    "South Dakota":"SD","Tennessee":"TN","Texas":"TX","Utah":"UT","Vermont":"VT",
    "Virginia":"VA","Washington":"WA","West Virginia":"WV","Wisconsin":"WI",
    "Wyoming":"WY"
}

# Frozen source allowlist. Kept in one place so it's easy to update without
# touching the prompt logic below.
ALLOWED_SOURCES = """
- Official state legislature websites and government sites
- Major news outlets
- Environmental agencies (state or federal)
- NCSL (National Conference of State Legislatures)
- Circular Action Alliance (CAA)
- Sustainable Packaging Coalition (SPC)
- Industry law firm / compliance client alerts: Holland & Knight, Mayer Brown,
  Proskauer, Beveridge & Diamond, O'Melveny, Faegre Drinker, White & Case,
  Compliance & Risks, and comparable firms
- Industry associations PMMI and MHI (include MHI only if content is actually
  relevant to EPR packaging, not just general material handling)

EXPLICITLY EXCLUDED - do not cite or rely on:
- Competitor packaging company blogs/resources (e.g., EcoEnclose)
- Opinion/commentary sites (e.g., RealClearMarkets), even if cited alongside
  legitimate sources or if the content looks credible
"""

SCOPE_NOTE = """
Research scope: "bagging" broadly - poly bags, plastic film, paper bagging,
and mesh bagging used in shipping/packaging. Do not limit the search to
poly bags only. You do not need to separately flag or categorize bagging vs.
other packaging materials - just make sure the search itself is not
artificially narrowed to poly bags alone.
"""

PROMPT_TEMPLATE = """You are researching US state Extended Producer Responsibility (EPR) \
packaging legislation for {state}, on behalf of a compliance monitoring system.

{scope_note}

Only use these source types, and follow these exclusions:
{sources}

Search for the CURRENT status of EPR packaging legislation in {state} as of today. \
Look specifically for:
1. Any new bill introduced, amended, passed, or repealed since a monitoring system \
   last checked (assume last check was roughly 30 days ago).
2. Any change in status of legislation already known to be pending or passed.
3. Any bill number corrections, conflicts, or renumbering (e.g., a bill reintroduced \
   in a new legislative session under a different number).

Respond ONLY with a JSON object, no other text, no markdown fences, in this exact \
shape:

{{
  "has_notable_finding": true or false,
  "status": "passed" or "pending" or "none",
  "law_passed": "brief plain statement of the law/bill and its current status, no hedging language, no meta-commentary about research process",
  "status_detail": "1-3 sentence current-state summary, plain facts only",
  "milestones": ["short milestone 1", "short milestone 2"],
  "sources": [{{"label": "source name", "url": "source url"}}]
}}

If there is nothing notable to report for {state}, set has_notable_finding to false \
and leave other fields empty. Do not fabricate sources or bill numbers - if you \
are not confident in a detail, omit it rather than guess.
"""


def call_claude(prompt):
    body = {
        "model": MODEL,
        "max_tokens": 1500,
        "messages": [{"role": "user", "content": prompt}],
        "tools": [{"type": "web_search_20250305", "name": "web_search"}],
    }
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())

    # Concatenate all text blocks (there may be several interleaved with tool use)
    text_parts = [b["text"] for b in data.get("content", []) if b.get("type") == "text"]
    return "\n".join(text_parts)


def extract_json(text):
    """Claude may wrap JSON in prose despite instructions - pull out the first
    {...} block defensively."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def load_master():
    """Returns dict of abbr -> row, for comparing against new findings."""
    if not os.path.exists(MASTER_CSV):
        return {}
    with open(MASTER_CSV, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return {r["Abbr"]: r for r in rows if r.get("Abbr")}


def load_rejected_log():
    """Returns list of {abbr, law_passed} previously rejected, so we don't
    re-suggest the same thing every run."""
    if not os.path.exists(REJECTED_LOG):
        return []
    with open(REJECTED_LOG, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def normalize(text):
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def is_same_as_master(finding, master_row):
    """True if the finding doesn't meaningfully differ from what's already
    on file - compares law_passed and status_detail, ignoring whitespace/case."""
    if not master_row:
        return False
    return (
        normalize(finding.get("law_passed")) == normalize(master_row.get("Law Passed"))
        and normalize(finding.get("status_detail")) == normalize(master_row.get("Status Detail"))
    )


def was_previously_rejected(finding, abbr, rejected_rows):
    """True if this finding closely matches something already rejected for
    this state. Simple substring/equality check on law_passed - good enough
    since rejections are about specific bills, not vague phrasing drift."""
    target = normalize(finding.get("law_passed"))
    if not target:
        return False
    for row in rejected_rows:
        if row.get("Abbr") == abbr and normalize(row.get("Law Passed")) == target:
            return True
    return False


def research_state(state):
    prompt = PROMPT_TEMPLATE.format(state=state, scope_note=SCOPE_NOTE, sources=ALLOWED_SOURCES)
    try:
        raw = call_claude(prompt)
    except Exception as e:
        print(f"  [{state}] API error: {e}")
        return None
    result = extract_json(raw)
    if result is None:
        print(f"  [{state}] Could not parse a JSON result; skipping.")
        return None
    return result


def main():
    print(f"Scanning {len(ALL_STATES)} states for EPR bagging-relevant legislative activity...")
    master = load_master()
    rejected_rows = load_rejected_log()
    print(f"Loaded {len(master)} existing state row(s) from master_matrix.csv and "
          f"{len(rejected_rows)} previously-rejected entr(y/ies) to filter against.")

    suggested_rows = []
    summary_lines = []
    skipped_unchanged = 0
    skipped_rejected = 0

    for state in ALL_STATES:
        print(f"Researching {state}...")
        result = research_state(state)
        if not result or not result.get("has_notable_finding"):
            continue

        abbr = STATE_ABBR[state]
        master_row = master.get(abbr)

        if is_same_as_master(result, master_row):
            print(f"  [{state}] Matches current master_matrix.csv row - skipping (no real change).")
            skipped_unchanged += 1
            continue

        if was_previously_rejected(result, abbr, rejected_rows):
            print(f"  [{state}] Matches a previously-rejected finding - skipping.")
            skipped_rejected += 1
            continue

        sources = result.get("sources", [])
        source_names = "; ".join(s.get("label", "") for s in sources)
        source_urls = " ; ".join(s.get("url", "") for s in sources)
        milestones = " | ".join(result.get("milestones", []))

        suggested_rows.append({
            "Decision": "",  # fill in ACCEPT or REJECT during Step 2 review
            "Abbr": abbr,
            "State": state,
            "Status": result.get("status", "pending"),
            "Law Passed": result.get("law_passed", ""),
            "Status Detail": result.get("status_detail", ""),
            "Milestones": milestones,
            "Source Name": source_names,
            "Source URL": source_urls,
        })
        summary_lines.append(f"- {state}: {result.get('status_detail', '')[:150]}")

    if suggested_rows:
        with open(SUGGESTED_CSV, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(suggested_rows[0].keys()))
            writer.writeheader()
            writer.writerows(suggested_rows)
        print(f"\nWrote {len(suggested_rows)} genuinely new/changed suggestion(s) to {SUGGESTED_CSV}")
    else:
        print("\nNo new or changed findings this run - suggested_updates.csv not written.")

    print(f"(Filtered out {skipped_unchanged} unchanged-from-master and "
          f"{skipped_rejected} previously-rejected finding(s).)")

    with open(SUMMARY_TXT, "w", encoding="utf-8") as f:
        if summary_lines:
            f.write("EPR Detection Summary - review suggested_updates.csv for full details\n\n")
            f.write("\n".join(summary_lines))
        else:
            f.write("EPR Detection Summary: no new or changed findings this run.")
    print(f"Summary written to {SUMMARY_TXT}")
    print("\nReminder: master_matrix.csv was NOT modified. Fill in the Decision column "
          "in suggested_updates.csv (ACCEPT/REJECT) and run step2_review_merge.py.")


if __name__ == "__main__":
    main()
