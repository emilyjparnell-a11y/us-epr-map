# EPR Map — Reviewer Instructions (Step 2)

This is the human review step in the automated pipeline. Once a month, an
automated scan produces a file called `suggested_updates.csv` in the
`us-epr-map` GitHub repo. Your job is to review it and mark each row
ACCEPT or REJECT before anything reaches the live map.

## What you're reviewing

Each row in `suggested_updates.csv` represents a state where the automated
scan found something it believes is new or changed — a new bill, a status
change, a bill renumbering, etc. It is AI-generated research, not a
guarantee of accuracy.

## Your task, step by step

1. Open `suggested_updates.csv` in the repo (or download it).
2. For each row, read the `Law Passed`, `Status Detail`, `Milestones`, and
   `Source URL` columns.
3. **Click through at least one source link per row.** Confirm the bill
   number, status, and date actually match what's claimed. Do not accept a
   row on the strength of the AI's summary alone.
4. Fill in the `Decision` column with exactly `ACCEPT` or `REJECT` (all
   caps, no other values — the merge script only recognizes these two).
5. Once every row has a decision, commit the file back to the repo.
6. Run `step2_review_merge.py` (locally, or ask [Emily/whoever manages the
   repo] to run it if you don't have Python set up). This merges ACCEPT
   rows into `master_matrix.csv` and logs REJECT rows so they aren't
   suggested again next month.
7. Commit the updated `master_matrix.csv` and `rejected_log.csv`.
8. If you want the live map updated immediately rather than waiting for the
   next scheduled run, go to the repo's **Actions** tab → **Monthly EPR
   Data Refresh** → **Run workflow**.

## Caveats — please read before your first review

- **The AI can be wrong.** It can misread a bill number, misattribute a
  status, or occasionally cite a source that doesn't actually say what the
  summary claims. Verifying at least one link per row is not optional.
- **Only use approved sources.** The scan is instructed to stick to a
  specific allowlist (legislative/government sites, major news outlets,
  environmental agencies, NCSL, Circular Action Alliance, Sustainable
  Packaging Coalition, named law firm/compliance alerts, PMMI, and MHI when
  relevant) and to avoid competitor blogs and opinion/commentary sites. If
  a source looks off — a blog, an opinion piece, a competitor's site —
  reject the row even if the underlying fact seems plausible, and flag it
  so the source list can be reviewed.
- **Keep customer-facing text clean.** `Status Detail` and `Milestones`
  should read as plain, current-state facts only. If a suggested row
  contains hedging or research-process language ("not yet confirmed,"
  "prior note referenced," "secondary source says"), edit it down to a
  clean statement before accepting, or reject and note why.
- **No em dashes** in any accepted/edited text — house style rule.
- **Matching against existing data is exact-text based**, not fuzzy. If a
  bill's status is only slightly reworded between runs, it may appear
  again even though nothing substantively changed. Use judgment — if
  it's the same underlying fact, reject it as a duplicate rather than
  double-entering it.
- **This step never touches the live map directly.** Nothing you do here
  is visible to site visitors until the merge script runs AND the map's
  data-refresh Action runs (either on its own schedule, or triggered
  manually per step 8 above).
- **When in doubt, reject.** A missed update gets caught next month. A bad
  update goes live on a page customers are relying on for compliance
  information — the disclaimer on the map covers you, but accuracy is
  still the goal.

## Who to contact

Questions about the pipeline itself (not a specific bill) go to
[Emily / Tension Automation contact info].
