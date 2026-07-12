name: Monthly EPR Detection Scan

on:
  schedule:
    - cron: "0 13 24 * *"   # Runs 24th of every month, 1pm UTC (about a week before
                             # the data-refresh Action on the 1st, to leave review time)
  workflow_dispatch:         # Lets you also trigger it manually from the Actions tab

permissions:
  contents: write             # Needed so the Action can commit suggested_updates.csv etc.

jobs:
  detect:
    runs-on: ubuntu-latest
    steps:
      - name: Check out repo
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Run detection script
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: python step1_detect_updates.py

      - name: Commit output files
        run: |
          git config user.name "epr-bot"
          git config user.email "epr-bot@users.noreply.github.com"
          git add detection_summary.txt
          if [ -f suggested_updates.csv ]; then
            git add suggested_updates.csv
          fi
          git diff --quiet --cached || git commit -m "Monthly EPR detection scan"
          git push
