# Independent check: Arrow fiscal 2024

Source: [Arrow's 2024 Form 10-K](https://www.sec.gov/Archives/edgar/data/7536/000155837025000781/arw-20241231x10k.htm), accession 0001558370-25-000781, filed February 11, 2025. The consolidated statements of operations are on printed page 49; balance sheets are on printed page 51. These tables were read separately from Company Facts.

The source displays thousands of dollars. Annual revenue is 27,923,324 and cost of sales is 24,630,916. Opening and closing inventory are 5,187,225 and 4,709,706; net accounts receivable are 12,238,073 and 13,030,991; accounts payable are 10,070,015 and 11,047,470. Opening means December 31, 2023 and closing means December 31, 2024.

The year has 366 days. Using the original displayed units, which cancel in the ratios:

```text
DIO = ((5,187,225 + 4,709,706) / 2) / 24,630,916 × 366 = 73.531101 days
DSO = ((12,238,073 + 13,030,991) / 2) / 27,923,324 × 366 = 165.604880 days
DPO = ((10,070,015 + 11,047,470) / 2) / 24,630,916 × 366 = 156.896307 days
CCC = 73.531101 + 165.604880 − 156.896307 = 82.239674 days
Five-day scenario = (24,630,916 × 1,000) / 366 × 5 = USD 336,487,923.50
```

The independent transcription is bundled as `data/sample/arrow-2024-reconciliation.json`. `test_arrow_2024_matches_independent_filing_transcription` checks every extracted input against it, including conversion to dollars, then calculates the ratios separately. Later Company Facts filings currently repeat these figures. If a later refresh changes them, the test requires investigation rather than silently accepting the change.

DPO still approximates purchases with cost of sales. This validates this company-year's inputs and arithmetic; it does not validate every disclosure or certify the entire comparison.
