# Inventory Cash Planner implementation plan

Goal: connect an offline, traceable five-year working-capital comparison to a retail ordering-policy experiment.

Architecture: Python 3.12 CLI, standard-library calculation and simulation modules, Pillow PNG output and a self-contained HTML report. openpyxl is used only to rebuild the UCI sample. No database or web server is needed for this small cached extract.

The supplied build specification is the design. Use the latest five complete annual periods available in each downloaded SEC snapshot; preserve the snapshot date and source facts. Annual ratios use average opening/closing balances and inclusive period lengths. Prefer facts from one filing; use latest eligible restated facts with explicit provenance. Incompatible facts fail visibly.

- [x] Write and run financial extraction and ratio tests, including amended filings, duplicates, missing openings and zero denominators; implement extraction and ratios.
- [x] Write and run simulation tests for arrivals, inventory position, lost sales, zero days and conservation; implement weekly order-up-to and daily reorder-point policies.
- [x] Implement identified, throttled, retrying public downloads and deterministic privacy-minimized extracts. Bundle a small sample and source manifest.
- [x] Build offline HTML with assumptions, financial trends, source audit, interactive scenario controls and policy results. Generate three labeled PNG figures from the same calculations.
- [x] Reconcile a company-year against its annual report. Run all tests, CLI and showcase; inspect images and size limits. Document scope and limitations.

Review focus: no forecast lookahead; no same-day arrival for positive lead times; no missing calendar dates; no cross-year balance matching by calendar year; no silent substitution of differently defined XBRL concepts. Historical filings and retail periods are not directly comparable businesses or currencies.

Verified: 22 offline tests; three 1440 x 940 charts; default and alternate CLI scenarios; embedded report JavaScript syntax; all intended repository files below 5 MB. A read-only reviewer reproduced bundled financial and retail extracts from their raw public inputs and found no actionable core defects. Browser rendering was not exercised; generated PNGs were visually inspected.
