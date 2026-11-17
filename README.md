# Payment Reconciliation System ⚖️

A production-grade, automated **Payment Reconciliation Dashboard** built with **Python**, **Pandas**, **Plotly**, and **Streamlit**.

This system bridges the gap between a payments platform's immediate customer transaction logs and acquiring bank settlement statements (which settle on a T+1 to T+2 day cycle), automatically identifying discrepancies, calculating aggregate differences using exact Decimal arithmetic, and generating actionable exception reports.

---

## 1. Project Architecture & Structure

```
OneLab_assessment/
├── app.py                      # Interactive Streamlit dashboard with UI/UX polish
├── reconciliation.py           # Core reconciliation engine (Decimal arithmetic & gap detection)
├── data_generator.py           # Synthetic dataset generator with 4 planted gaps & templates
├── config.py                   # Centralized design tokens, theme palette & constants
├── requirements.txt            # Dependency specifications
├── pytest.ini                  # Pytest configuration
├── create_submission_zip.py    # Submission packager script
├── .streamlit/
│   └── config.toml             # Streamlit light-theme & server configuration
├── data/
│   ├── platform_transactions.csv   # Platform sales & refund records
│   └── bank_settlements.csv        # Bank settlement credits & references
├── tests/
│   └── test_reconciliation.py  # 17 automated pytest test cases
└── README.md                   # Comprehensive documentation & methodology
```

---

## 2. Key Objectives & Detected Gaps

At month-end, the company's recorded transactions and the bank's actual credits should match. When they don't, this system identifies exactly why and categorizes every discrepancy:

### The 4 Required Planted Gaps (Intentionally Planted & Verified)
1. **Next-Month Settlement (Timing Difference / Float)**:
   - *Scenario*: A transaction recorded on the final day of the target month (e.g., Oct 31 at 21:45) is settled by the bank on Nov 02 on a standard T+2 business cycle.
   - *Detection*: The engine checks transaction timestamps against bank settlement dates. Rather than flagging this as a missing settlement, it identifies it as an in-transit timing difference and recommends carrying it forward into the month-end float ledger.
2. **Rounding Difference (Item-Level & Aggregate Sum)**:
   - *Scenario*: Individual amounts look nearly identical (e.g., platform ₹1,499.50 vs bank ₹1,499.48 due to 2 paise fractional interchange / MDR rounding), but when summing thousands of records, an aggregate difference accumulates.
   - *Detection*: Employs Python `decimal.Decimal` (quantized to `0.01`). Variances within a configurable tolerance (default `₹0.05`) are classified as rounding differences, and the aggregate net rounding drift is computed across all batches.
3. **Duplicate Entry**:
   - *Scenario*: A settlement entry or platform charge is duplicated in the dataset (e.g., duplicate bank batch upload settling `TXN_202610_0010` twice).
   - *Detection*: Pre-processing deduplication flags subsequent occurrences as duplicate entries and isolates them from primary ledger summation, preventing artificial inflation of company asset books.
4. **Orphan Refund**:
   - *Scenario*: A refund record (`REFUND` type) issued without a corresponding parent payment transaction in the platform sales ledger.
   - *Detection*: Verifies `original_transaction_id` against all successful primary payments. Unlinked refunds are flagged with **HIGH** severity for fraud/operational investigation.

### Additional Real-World Gaps Detected
5. **Unsettled / Missing Settlements**: Platform successful transactions that were never credited by the acquiring bank after the settlement window.
6. **Unmatched Bank Credits (Ghost Deposits)**: Bank deposits received without any corresponding transaction ID in the platform ledger (offline wires or missed webhooks).
7. **Amount Mismatches**: Transaction ID matches, but the variance exceeds the rounding threshold (e.g., unexpected bank deduction or fee dispute).

---

## 3. Financial Metrics & Formulas

- **Net Reconciliation Difference**:
  $$\text{Net Difference} = \sum \text{Platform Recorded Amount} - \sum \text{Bank Settled Amount}$$
  Represents the net timing float and missing credits between internal books and bank receipts.
- **Gross Exception Exposure**:
  $$\text{Gross Exposure} = \sum_{\text{exceptions}} |\text{Discrepancy Amount}|$$
  Total absolute monetary exposure currently under investigation or requiring accounting adjustment.
- **Match Rate Percentage**:
  $$\text{Match Rate} = \frac{\text{Successfully Matched Unique Count}}{\text{Total Unique Platform Transactions}} \times 100$$

---

## 4. Documented Assumptions

1. **Currency**: All amounts are in Indian Rupees (**INR**, `₹`).
2. **Settlement Timing Cycle**: Standard settlement occurs in **T+1 to T+2 business days**.
3. **Month-End Cutoff**: Reconciliations are evaluated against a target calendar month (e.g., `2026-10`, `2026-09`). Transactions on the last day of the month settling in the following month are classified as `TIMING_DIFFERENCE_NEXT_MONTH` rather than missing records.
4. **Rounding Rules**: Differences $\le ₹0.05$ (5 paise) are categorized as `ROUNDING_DIFFERENCE` (standard fractional MDR / GST calculation variances). Any variance $> ₹0.05$ is categorized as an `AMOUNT_MISMATCH`.
5. **Decimal Precision**: All currency operations are calculated using `decimal.Decimal(ROUND_HALF_UP)` to avoid IEEE 754 floating-point inaccuracies.
6. **Deduplication Treatment**: When duplicate transaction IDs or settlement IDs appear, the first instance is treated as the primary candidate; subsequent occurrences are isolated as `DUPLICATE_ENTRY` and omitted from matched volume totals.
7. **Refund Integrity**: Every refund must reference an active, non-duplicate `original_transaction_id` matching an existing sales payment.

---

## 5. Getting Started & Installation

### Prerequisites
- Python 3.10+ (tested on Python 3.11)
- `pip` package manager

### 1. Set Up Virtual Environment
```bash
# Navigate to project directory
cd OneLab_assessment

# Create and activate virtual environment (optional but recommended)
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Generate Sample Datasets
```bash
python data_generator.py
```
This generates `data/platform_transactions.csv` and `data/bank_settlements.csv` containing realistic INR payments and all 4 planted discrepancies.

### 3. Run Automated Tests
```bash
pytest
```
Expected output: **17 passed in under 1 second**.

### 4. Launch the Streamlit Dashboard
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501`.

---

## 6. Dashboard Features & Capabilities

- **Executive KPI Cards**: 6 clear financial metrics: Total Platform Transactions, Total Bank Settlements, Successfully Matched Volume, Net Reconciliation Difference, Settled After Period End (Float), and Gross Exception Exposure.
- **Dynamic Executive Reconciliation Insight**: Narrative summary automatically generated for auditors highlighting match performance, timing float, and open action items.
- **Side-by-Side Transaction Inspector**: Deep-dive investigation view that compares the platform transaction record and bank settlement record side-by-side with root-cause analysis and recommended accounting actions.
- **Dual Ingestion Modes**:
  - *📤 Upload My Files*: Strict schema validation, file metadata preview, and downloadable CSV templates (`platform_transactions_template.csv` and `bank_settlements_template.csv`).
  - *🧪 Use Sample Demo Data*: Configurable demo periods (`2026-10`, `2026-09`, `2026-08`, etc.) with an expandable **Data Issue Manifest** verification key.
- **High-Contrast Professional UI/UX**: Soft earthy aesthetic with pistachio green (`#B7C99A`, `#82966A`), faint warm brown (`#7A624E`, `#6B5644`), cream background (`#FAF9F5`), and high-contrast visible text across all toolbars, tables, and tooltips.
- **Actionable Exception Management**: Filter by Exception Type, Severity (HIGH, MEDIUM, LOW), or search by Transaction ID / Reason.
- **Comprehensive Reports**: 7 downloadable CSV audit reports including complete reconciliation ledger, matched records, exceptions, delayed settlements, duplicates, orphan refunds, and executive summary.

---

## 7. Automated Testing Verification

The test suite in `tests/test_reconciliation.py` contains 17 dedicated test cases:

| Test Case | Scenario Verified | Status |
|---|---|:---:|
| `test_next_month_settlement` | Oct 31 transaction settling Nov 02 classified as timing difference | ✅ PASSED |
| `test_rounding_difference` | 2 paise & 3 paise variances detected; aggregate delta computed | ✅ PASSED |
| `test_duplicate_entry` | Bank settlement duplicate isolated; ledger double-counting prevented | ✅ PASSED |
| `test_orphan_refund` | Refund with non-existent parent ID flagged as high-severity orphan | ✅ PASSED |
| `test_successfully_matched_transactions` | Exact matches produce zero discrepancy and zero exceptions | ✅ PASSED |
| `test_unsettled_missing_settlement` | Unsettled transactions correctly flagged when bank drops batch | ✅ PASSED |
| `test_empty_datasets` | Validation error raised on empty data | ✅ PASSED |
| `test_invalid_csv_schema` | Descriptive error when required columns are missing | ✅ PASSED |
| `test_full_generated_dataset` | All 4 planted problems verified on end-to-end generated dataset | ✅ PASSED |
| `test_decimal_precision` | Verifies Decimal arithmetic prevents floating-point drift | ✅ PASSED |
| `test_multi_date_multi_amount_batch` | Batch across multiple dates and diverse amounts | ✅ PASSED |
| `test_amount_mismatch_exceeding_tolerance` | Discrepancies $> ₹0.05$ correctly flagged as Amount Mismatch | ✅ PASSED |
| `test_unmatched_bank_credit` | Unidentified bank credits detected | ✅ PASSED |
| `test_duplicate_platform_record` | Duplicate platform transaction entries isolated from ledger | ✅ PASSED |
| `test_multiple_records_with_same_amount` | Matches strictly on stable ID, never false-matching on amount alone | ✅ PASSED |
| `test_incorrect_dates_and_invalid_financial_values` | Robust handling of corrupt strings, negative numbers, or invalid dates | ✅ PASSED |
| `test_data_issue_manifest_verification` | Verifies all 8 planted test cases in synthetic generator match expected verdicts | ✅ PASSED |

---

## 8. What This System Would Get Wrong in Production

*(Mandatory Assessment Submission Deliverable: 3 sentences on what it would get wrong in production)*

1. **Net Settlement Batching & MDR Deductions**: In production, acquiring banks rarely settle transactions 1:1; instead, they batch hundreds of transactions into a single lump-sum net credit minus Merchant Discount Rate (MDR) fees, interchange fees, and GST, making 1:1 transaction ID and amount matching fail without batch-settlement breakdown ingestion or reverse fee-schedule simulation.
2. **Multi-Currency & Rolling Reserve Holds**: The engine assumes clean INR-to-INR settlement without foreign exchange fluctuation, risk-based rolling reserves (e.g., 5-10% held back by the processor for 90 days), or partial chargeback withholdings, which in live operations creates perpetual pseudo-unsettled amount variances.
3. **Partial Refunds & Complex Lifecycles**: In live payment processing, a single order often experiences partial refunds (e.g., ₹300 refund on a ₹1,000 order), chargeback disputes, and re-presentment reversals across disparate settlement cycles, which a naive single-key transaction matching engine flags as amount mismatches or duplicate ledger entries rather than lifecycle state transitions.

---

## 9. Assessment Submission Checklist

- [x] **1. Brainstorming Thread**: Full conversation history retained.
- [x] **2. Raw & Distilled Prompt**: Clearly documented in section 10 below.
- [x] **3. Execution Thread**: Complete execution, validation, and test results recorded.
- [x] **4. Test Cases**: 17 automated tests implemented in `tests/test_reconciliation.py`.
- [x] **5. Working Output**:
  - Code Zip: Run `python create_submission_zip.py` to produce `payment_reconciliation_submission.zip`.
  - Deployed Link: Ready for one-click deployment on [Streamlit Community Cloud](https://share.streamlit.io).
  - 3 Sentences on Production Limitations: Included in Section 8 above.

---

## 10. Prompts Used

### Raw Prompt (Mandatory)
```text
The Problem
A payments company's books don't balance at month end. They know every transaction their platform processed. They know what the bank says actually arrived. The two should match. They don't. Find out why. Show them where the gaps are.

Test Data
No files provided. Generate your own — that's part of the assessment. A payments platform records a transaction instantly when a customer pays. The bank batches and settles funds 1–2 days later. At month end every transaction should have a matching settlement.
Plant these gap types: a transaction that settled the following month · a rounding difference that only shows when summed · a duplicate entry in one dataset · a refund with no matching original transaction.
State your assumptions. There are no wrong ones as long as you name them.

What to Submit
1 Brainstorming thread Full LLM convo. Do not clean it up.
2 Distilled prompt and  Raw Prompt (mandatory )  The single prompt you fed into Claude Code or Cursor or any other AI coding tool.
3 Claude Code thread Full execution thread including wrong turns.
4 Test cases What you wrote to verify your solution works.
5 Working output Deployed link + code zip + Demo video + 3 sentences on what it 
would get wrong in production.
```

### Distilled Prompt
```text
Build a complete, working Payment Reconciliation Dashboard using Python, Pandas, and Streamlit.
Generate realistic synthetic datasets in INR: platform_transactions.csv and bank_settlements.csv.
Intentionally plant all four gaps: next-month settlement, aggregate rounding difference, duplicate entry, orphan refund.
Implement the reconciliation engine in reconciliation.py using Decimal arithmetic for financial precision.
Build a modern Streamlit dashboard in app.py with Overview KPIs, Data Upload, Categorized Results tabs, Filterable Exception Report with recommended actions, and CSV report downloads.
Write automated pytest tests in tests/test_reconciliation.py covering all 4 planted gaps and edge cases.
Document all assumptions, methodology, and 3 sentences on what it would get wrong in production in README.md.
```
