"""
Automated Test Suite for Payment Reconciliation System
======================================================
Tests verify each required scenario individually and in combination:
  1. Next-month settlement (Timing difference)
  2. Aggregate rounding difference and row-level paise variance
  3. Duplicate entry detection & double-counting prevention
  4. Orphan refund identification (missing parent transaction)
  5. Successfully matched transactions
  6. Completely missing bank settlements
  7. Empty datasets handling & validation errors
  8. Invalid / corrupted CSV schema handling
  9. Multi-date, multi-amount batch reconciliation
  10. Decimal precision verification (avoiding floating point errors)
"""

import os
import pytest
from decimal import Decimal
import pandas as pd
from reconciliation import ReconciliationEngine, to_decimal, format_inr
from data_generator import generate_synthetic_data, save_datasets


@pytest.fixture
def base_engine():
    return ReconciliationEngine(reconciliation_month="2026-10", rounding_tolerance=Decimal("0.05"))


# ---------------------------------------------------------------------------
# Test 1: Next-Month Settlement (Timing Difference)
# ---------------------------------------------------------------------------
def test_next_month_settlement(base_engine):
    """Verify that a transaction on the last day of the month settled in the next month is classified as timing diff."""
    platform_df = pd.DataFrame([{
        "transaction_id": "TXN_OCT_END_001",
        "transaction_date": "2026-10-31 22:45:00",
        "amount": 5000.00,
        "transaction_type": "PAYMENT",
        "original_transaction_id": "",
    }])
    bank_df = pd.DataFrame([{
        "settlement_id": "SETTL_NOV_001",
        "transaction_id": "TXN_OCT_END_001",
        "settlement_date": "2026-11-02",
        "settlement_amount": 5000.00,
        "bank_reference": "UTR_NOV_001",
    }])

    summary, rec_df, exc_df = base_engine.reconcile(platform_df, bank_df)

    assert summary.timing_difference_count == 1
    assert summary.timing_difference_amount == Decimal("5000.00")
    assert summary.unsettled_count == 0  # Should NOT be counted as missing
    assert summary.matched_count == 0

    assert len(exc_df) == 1
    exc = exc_df.iloc[0]
    assert exc["Exception Type"] == "Next-Month Settlement (Timing)"
    assert "following calendar month" in exc["Reason for Mismatch"]
    assert "Timing Difference" in exc["Recommended Action"]


# ---------------------------------------------------------------------------
# Test 2: Aggregate & Item-level Rounding Difference
# ---------------------------------------------------------------------------
def test_rounding_difference(base_engine):
    """Verify that minor paise variances within tolerance are detected as rounding diffs and aggregate delta is computed."""
    platform_df = pd.DataFrame([
        {"transaction_id": "TXN_RND_001", "transaction_date": "2026-10-10 10:00:00", "amount": 1000.50, "transaction_type": "PAYMENT"},
        {"transaction_id": "TXN_RND_002", "transaction_date": "2026-10-10 11:00:00", "amount": 2000.25, "transaction_type": "PAYMENT"},
    ])
    bank_df = pd.DataFrame([
        {"settlement_id": "SETTL_RND_001", "transaction_id": "TXN_RND_001", "settlement_date": "2026-10-11", "settlement_amount": 1000.48},
        {"settlement_id": "SETTL_RND_002", "transaction_id": "TXN_RND_002", "settlement_date": "2026-10-11", "settlement_amount": 2000.22},
    ])

    summary, rec_df, exc_df = base_engine.reconcile(platform_df, bank_df)

    assert summary.rounding_difference_count == 2
    # Platform total = 3000.75, Bank total = 3000.70 -> Delta = 0.05
    assert summary.aggregate_rounding_delta == Decimal("0.05")
    assert summary.amount_mismatch_count == 0

    rounding_exceptions = exc_df[exc_df["Exception Type"] == "Rounding Difference"]
    assert len(rounding_exceptions) == 2


# ---------------------------------------------------------------------------
# Test 3: Duplicate Entry Detection & Double-Counting Prevention
# ---------------------------------------------------------------------------
def test_duplicate_entry(base_engine):
    """Verify that duplicate settlement records are detected and not counted twice in totals."""
    platform_df = pd.DataFrame([{
        "transaction_id": "TXN_DUP_001",
        "transaction_date": "2026-10-05 10:00:00",
        "amount": 750.00,
        "transaction_type": "PAYMENT",
    }])
    bank_df = pd.DataFrame([
        {"settlement_id": "SETTL_DUP_001", "transaction_id": "TXN_DUP_001", "settlement_date": "2026-10-06", "settlement_amount": 750.00},
        {"settlement_id": "SETTL_DUP_002", "transaction_id": "TXN_DUP_001", "settlement_date": "2026-10-07", "settlement_amount": 750.00},
    ])

    summary, rec_df, exc_df = base_engine.reconcile(platform_df, bank_df)

    # 1 matched, 1 duplicate
    assert summary.matched_count == 1
    assert summary.duplicate_count == 1
    assert summary.duplicate_amount == Decimal("750.00")
    # Total bank amount in primary ledger should not be 1500; it should be 750
    assert summary.total_bank_amount == Decimal("750.00")

    dup_exc = exc_df[exc_df["Exception Type"] == "Duplicate Bank Settlement"]
    assert len(dup_exc) == 1
    assert "Duplicate settlement" in dup_exc.iloc[0]["Reason for Mismatch"]


# ---------------------------------------------------------------------------
# Test 4: Orphan Refund Identification
# ---------------------------------------------------------------------------
def test_orphan_refund(base_engine):
    """Verify that refunds without an existing parent sales transaction are flagged as Orphan Refunds."""
    platform_df = pd.DataFrame([
        {
            "transaction_id": "REF_ORPHAN_001",
            "transaction_date": "2026-10-15 14:00:00",
            "amount": 1200.00,
            "transaction_type": "REFUND",
            "original_transaction_id": "TXN_NON_EXISTENT_999",
        },
        {
            "transaction_id": "TXN_SALE_001",
            "transaction_date": "2026-10-14 10:00:00",
            "amount": 800.00,
            "transaction_type": "PAYMENT",
            "original_transaction_id": "",
        },
        {
            "transaction_id": "REF_VALID_001",
            "transaction_date": "2026-10-16 11:00:00",
            "amount": 800.00,
            "transaction_type": "REFUND",
            "original_transaction_id": "TXN_SALE_001",
        },
    ])
    bank_df = pd.DataFrame([
        {"settlement_id": "SETTL_S1", "transaction_id": "TXN_SALE_001", "settlement_date": "2026-10-15", "settlement_amount": 800.00},
        {"settlement_id": "SETTL_R1", "transaction_id": "REF_VALID_001", "settlement_date": "2026-10-17", "settlement_amount": 800.00},
    ])

    summary, rec_df, exc_df = base_engine.reconcile(platform_df, bank_df)

    assert summary.orphan_refund_count == 1
    assert summary.orphan_refund_amount == Decimal("1200.00")

    orphan_exc = exc_df[exc_df["Exception Type"] == "Orphan Refund"]
    assert len(orphan_exc) == 1
    assert orphan_exc.iloc[0]["Transaction ID"] == "REF_ORPHAN_001"
    assert orphan_exc.iloc[0]["Severity"] == "HIGH"


# ---------------------------------------------------------------------------
# Test 5: Successfully Matched Transactions
# ---------------------------------------------------------------------------
def test_successfully_matched_transactions(base_engine):
    """Verify that exact matches with identical amounts and valid dates match with zero discrepancy."""
    platform_df = pd.DataFrame([{
        "transaction_id": "TXN_EXACT_001",
        "transaction_date": "2026-10-04 09:30:00",
        "amount": 3499.00,
        "transaction_type": "PAYMENT",
    }])
    bank_df = pd.DataFrame([{
        "settlement_id": "SETTL_EXACT_001",
        "transaction_id": "TXN_EXACT_001",
        "settlement_date": "2026-10-05",
        "settlement_amount": 3499.00,
    }])

    summary, rec_df, exc_df = base_engine.reconcile(platform_df, bank_df)

    assert summary.matched_count == 1
    assert summary.matched_amount == Decimal("3499.00")
    assert summary.total_discrepancy_amount == Decimal("0.00")
    assert summary.total_exceptions_count == 0
    assert len(exc_df) == 0


# ---------------------------------------------------------------------------
# Test 6: Completely Missing Settlements
# ---------------------------------------------------------------------------
def test_unsettled_missing_settlement(base_engine):
    """Verify that platform transactions without any bank settlement are flagged as missing."""
    platform_df = pd.DataFrame([{
        "transaction_id": "TXN_LOST_001",
        "transaction_date": "2026-10-08 12:00:00",
        "amount": 9999.00,
        "transaction_type": "PAYMENT",
    }])
    bank_df = pd.DataFrame(columns=["settlement_id", "transaction_id", "settlement_date", "settlement_amount"])

    summary, rec_df, exc_df = base_engine.reconcile(platform_df, bank_df)

    assert summary.unsettled_count == 1
    assert summary.unsettled_amount == Decimal("9999.00")
    assert summary.matched_count == 0
    assert len(exc_df) == 1
    assert exc_df.iloc[0]["Exception Type"] == "Unsettled / Missing Settlement"


# ---------------------------------------------------------------------------
# Test 7: Empty Datasets Handling
# ---------------------------------------------------------------------------
def test_empty_datasets(base_engine):
    """Verify graceful handling and descriptive error when an empty dataset is provided."""
    empty_df = pd.DataFrame()
    valid_df = pd.DataFrame([{
        "transaction_id": "TXN_1",
        "transaction_date": "2026-10-01",
        "amount": 100,
        "transaction_type": "PAYMENT"
    }])

    with pytest.raises(ValueError, match="empty"):
        base_engine.reconcile(empty_df, valid_df)


# ---------------------------------------------------------------------------
# Test 8: Invalid CSV Schema Handling
# ---------------------------------------------------------------------------
def test_invalid_csv_schema(base_engine):
    """Verify that missing required columns raises a descriptive ValueError."""
    corrupt_platform = pd.DataFrame([{"wrong_col_1": "123", "wrong_col_2": 456}])
    valid_bank = pd.DataFrame([{
        "settlement_id": "S1",
        "transaction_id": "T1",
        "settlement_date": "2026-10-02",
        "settlement_amount": 100
    }])

    with pytest.raises(ValueError, match="Missing required columns in platform"):
        base_engine.reconcile(corrupt_platform, valid_bank)


# ---------------------------------------------------------------------------
# Test 9: Comprehensive Generated Dataset Test (All 4 Planted Gaps)
# ---------------------------------------------------------------------------
def test_full_generated_dataset(base_engine):
    """Verify that all 4 planted gaps and standard transactions in synthetic data are properly identified."""
    platform_df, bank_df = generate_synthetic_data(num_records=50, month="2026-10", seed=42)
    summary, rec_df, exc_df = base_engine.reconcile(platform_df, bank_df)

    # 1. Next month settlement exists
    assert summary.timing_difference_count == 1
    assert summary.timing_difference_amount == Decimal("4500.00")

    # 2. Rounding difference exists
    assert summary.rounding_difference_count >= 1
    assert summary.aggregate_rounding_delta != Decimal("0.00")

    # 3. Duplicate entry exists
    assert summary.duplicate_count >= 1

    # 4. Orphan refund exists
    assert summary.orphan_refund_count >= 1

    # 5. Normal matches exist
    assert summary.matched_count >= 40

    # Ensure all exception types are present in the report
    types = set(exc_df["Exception Type"])
    assert "Next-Month Settlement (Timing)" in types
    assert "Rounding Difference" in types
    assert "Duplicate Bank Settlement" in types or "Duplicate Platform Entry" in types
    assert "Orphan Refund" in types


# ---------------------------------------------------------------------------
# Test 10: Decimal Precision vs Floating Point Drift
# ---------------------------------------------------------------------------
def test_decimal_precision():
    """Verify that to_decimal converts floats and strings cleanly without float representation errors."""
    val1 = to_decimal(0.1 + 0.2)  # In float, 0.1 + 0.2 is 0.30000000000000004
    assert val1 == Decimal("0.30")

    val2 = to_decimal("₹ 14,999.50 ")
    assert val2 == Decimal("14999.50")

    val3 = to_decimal(None)
    assert val3 == Decimal("0.00")


# ---------------------------------------------------------------------------
# Test 11: Multi-date, Multi-amount Batch Reconciliation
# ---------------------------------------------------------------------------
def test_multi_date_multi_amount_batch(base_engine):
    """Verify realistic multi-day batch with mixed amounts, successful matches, and differences."""
    platform_df = pd.DataFrame([
        {"transaction_id": "TXN_M1", "transaction_date": "2026-10-01 10:00:00", "amount": 150.00, "transaction_type": "PAYMENT"},
        {"transaction_id": "TXN_M2", "transaction_date": "2026-10-05 14:30:00", "amount": 2500.00, "transaction_type": "PAYMENT"},
        {"transaction_id": "TXN_M3", "transaction_date": "2026-10-12 18:00:00", "amount": 99.99, "transaction_type": "PAYMENT"},
        {"transaction_id": "TXN_M4", "transaction_date": "2026-10-25 21:15:00", "amount": 18450.50, "transaction_type": "PAYMENT"},
    ])
    bank_df = pd.DataFrame([
        {"settlement_id": "SETTL_M1", "transaction_id": "TXN_M1", "settlement_date": "2026-10-02", "settlement_amount": 150.00},
        {"settlement_id": "SETTL_M2", "transaction_id": "TXN_M2", "settlement_date": "2026-10-07", "settlement_amount": 2500.00},
        {"settlement_id": "SETTL_M3", "transaction_id": "TXN_M3", "settlement_date": "2026-10-14", "settlement_amount": 99.99},
        {"settlement_id": "SETTL_M4", "transaction_id": "TXN_M4", "settlement_date": "2026-10-27", "settlement_amount": 18450.50},
    ])

    summary, rec_df, exc_df = base_engine.reconcile(platform_df, bank_df)

    assert summary.matched_count == 4
    assert summary.total_discrepancy_amount == Decimal("0.00")
    assert summary.matched_amount == Decimal("21200.49")
    assert len(exc_df) == 0


# ---------------------------------------------------------------------------
# Test 12: Amount Mismatch Exceeding Tolerance
# ---------------------------------------------------------------------------
def test_amount_mismatch_exceeding_tolerance(base_engine):
    """Verify that a discrepancy exceeding rounding tolerance is marked as AMOUNT_MISMATCH."""
    platform_df = pd.DataFrame([{
        "transaction_id": "TXN_MISMATCH_001",
        "transaction_date": "2026-10-10 10:00:00",
        "amount": 5000.00,
        "transaction_type": "PAYMENT",
    }])
    bank_df = pd.DataFrame([{
        "settlement_id": "SETTL_MISMATCH_001",
        "transaction_id": "TXN_MISMATCH_001",
        "settlement_date": "2026-10-11",
        "settlement_amount": 4500.00,  # 500 INR difference
    }])

    summary, rec_df, exc_df = base_engine.reconcile(platform_df, bank_df)

    assert summary.amount_mismatch_count == 1
    assert summary.amount_mismatch_amount == Decimal("500.00")
    assert len(exc_df) == 1
    assert exc_df.iloc[0]["Exception Type"] == "Amount Mismatch"
    assert exc_df.iloc[0]["Severity"] == "HIGH"


# ---------------------------------------------------------------------------
# Test 13: Unmatched Bank Credit (Ghost Deposit)
# ---------------------------------------------------------------------------
def test_unmatched_bank_credit(base_engine):
    """Verify that a bank settlement with an unknown transaction ID is flagged as UNMATCHED_BANK_CREDIT."""
    platform_df = pd.DataFrame([{
        "transaction_id": "TXN_P_001",
        "transaction_date": "2026-10-10 10:00:00",
        "amount": 1000.00,
        "transaction_type": "PAYMENT",
    }])
    bank_df = pd.DataFrame([
        {"settlement_id": "SETTL_P_001", "transaction_id": "TXN_P_001", "settlement_date": "2026-10-11", "settlement_amount": 1000.00},
        {"settlement_id": "SETTL_GHOST", "transaction_id": "TXN_UNKNOWN_999", "settlement_date": "2026-10-12", "settlement_amount": 7500.00},
    ])

    summary, rec_df, exc_df = base_engine.reconcile(platform_df, bank_df)

    assert summary.matched_count == 1
    assert summary.unmatched_bank_count == 1
    assert summary.unmatched_bank_amount == Decimal("7500.00")
    ghost_exc = exc_df[exc_df["Exception Type"] == "Unmatched Bank Credit"]
    assert len(ghost_exc) == 1
    assert ghost_exc.iloc[0]["Transaction ID"] == "TXN_UNKNOWN_999"


# ---------------------------------------------------------------------------
# Test 14: Duplicate Platform Record Detection
# ---------------------------------------------------------------------------
def test_duplicate_platform_record(base_engine):
    """Verify that duplicated platform records are detected and excluded from double-counting."""
    platform_df = pd.DataFrame([
        {"transaction_id": "TXN_P_DUP_1", "transaction_date": "2026-10-02 10:00:00", "amount": 1200.00, "transaction_type": "PAYMENT"},
        {"transaction_id": "TXN_P_DUP_1", "transaction_date": "2026-10-02 10:00:05", "amount": 1200.00, "transaction_type": "PAYMENT"},
    ])
    bank_df = pd.DataFrame([
        {"settlement_id": "SETTL_P1", "transaction_id": "TXN_P_DUP_1", "settlement_date": "2026-10-03", "settlement_amount": 1200.00},
    ])

    summary, rec_df, exc_df = base_engine.reconcile(platform_df, bank_df)

    assert summary.raw_platform_count == 2
    assert summary.unique_platform_count == 1
    assert summary.duplicate_platform_count == 1
    assert summary.duplicate_platform_amount == Decimal("1200.00")
    assert summary.total_platform_amount == Decimal("1200.00")  # Duplicates excluded from primary ledger total
    assert summary.matched_count == 1


# ---------------------------------------------------------------------------
# Test 15: Matching by Stable Reference, Not Amount Alone
# ---------------------------------------------------------------------------
def test_multiple_records_with_same_amount(base_engine):
    """Verify that multiple records with the exact same amount are matched only by their ID."""
    platform_df = pd.DataFrame([
        {"transaction_id": "TXN_SAME_A", "transaction_date": "2026-10-04 10:00:00", "amount": 500.00, "transaction_type": "PAYMENT"},
        {"transaction_id": "TXN_SAME_B", "transaction_date": "2026-10-04 11:00:00", "amount": 500.00, "transaction_type": "PAYMENT"},
    ])
    bank_df = pd.DataFrame([
        # Only settlement for TXN_SAME_B is present; TXN_SAME_A was never settled
        {"settlement_id": "SETTL_B", "transaction_id": "TXN_SAME_B", "settlement_date": "2026-10-05", "settlement_amount": 500.00},
    ])

    summary, rec_df, exc_df = base_engine.reconcile(platform_df, bank_df)

    # Must match B, but NOT match A (no false match on amount 500 alone)
    assert summary.matched_count == 1
    assert summary.unsettled_count == 1
    assert summary.unsettled_amount == Decimal("500.00")
    assert len(exc_df) == 1
    assert exc_df.iloc[0]["Transaction ID"] == "TXN_SAME_A"


# ---------------------------------------------------------------------------
# Test 16: Corrupt Values, Strings, and NaNs Handling
# ---------------------------------------------------------------------------
def test_incorrect_dates_and_invalid_financial_values(base_engine):
    """Verify engine handles NaNs, spaces, invalid date strings without unhandled exceptions."""
    platform_df = pd.DataFrame([{
        "transaction_id": "TXN_CORRUPT_01",
        "transaction_date": "INVALID_DATE_STRING",
        "amount": "₹ 1,500.50 ",
        "transaction_type": "PAYMENT",
    }])
    bank_df = pd.DataFrame([{
        "settlement_id": "SETTL_C1",
        "transaction_id": "TXN_CORRUPT_01",
        "settlement_date": None,
        "settlement_amount": 1500.50,
    }])

    summary, rec_df, exc_df = base_engine.reconcile(platform_df, bank_df)
    assert summary.matched_count == 1
    assert summary.matched_amount == Decimal("1500.50")


# ---------------------------------------------------------------------------
# Test 17: Planted Data Issue Manifest Verification
# ---------------------------------------------------------------------------
def test_data_issue_manifest_verification():
    """Verify that the data generator manifest lists all planted scenarios and matches output."""
    from data_generator import get_data_issue_manifest
    manifest = get_data_issue_manifest("2026-10")
    assert len(manifest) >= 8

    # All 4 mandatory problem types must be present in the manifest
    issue_types = set(manifest["Planted Issue Type"])
    assert "Next-Month Settlement (Timing)" in issue_types
    assert "Rounding Difference" in issue_types
    assert "Duplicate Bank Settlement" in issue_types
    assert "Orphan Refund" in issue_types


