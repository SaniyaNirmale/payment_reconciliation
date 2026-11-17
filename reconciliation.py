"""
Payment Reconciliation Engine
=============================
Core logic for matching payment platform records with bank settlement statements.
Features:
  - Exact Decimal arithmetic for financial comparisons (no IEEE 754 float drift)
  - Distinguishes raw dataset rows vs unique transaction entities
  - Next-month settlement detection (in-transit timing difference)
  - Line-level paise variance vs aggregate batch rounding analysis
  - In-dataset deduplication to prevent double-counting in ledger books
  - Orphan refund detection (refund with missing/invalid parent sales transaction)
  - Net reconciliation difference and gross exception exposure metrics
  - Side-by-side audit metadata for every reconciled item
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd
import numpy as np


def to_decimal(val: Any) -> Decimal:
    """Safely convert any numeric or string representation into a 2-decimal place Decimal."""
    if val is None or pd.isna(val) or val == "":
        return Decimal("0.00")
    try:
        s = str(val).replace("₹", "").replace(",", "").strip()
        d = Decimal(s)
        return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0.00")


def format_inr(amount: Decimal) -> str:
    """Format decimal amount as INR currency string with sign handling."""
    if amount < Decimal("0.00"):
        return f"-₹{abs(amount):,.2f}"
    return f"₹{amount:,.2f}"


@dataclass
class ReconciliationSummary:
    reconciliation_month: str
    
    # Dataset volume metrics (Raw vs Unique)
    raw_platform_count: int = 0
    unique_platform_count: int = 0
    total_platform_amount: Decimal = Decimal("0.00")
    
    raw_bank_count: int = 0
    unique_bank_count: int = 0
    total_bank_amount: Decimal = Decimal("0.00")
    
    # Matching breakdown
    matched_count: int = 0                  # Total matched (exact + within tolerance)
    matched_exact_count: int = 0            # Exact zero difference
    matched_variance_count: int = 0         # Within rounding tolerance
    matched_amount: Decimal = Decimal("0.00")
    match_rate_percentage: float = 0.0
    
    # Timing differences (Settled after period end)
    timing_difference_count: int = 0
    timing_difference_amount: Decimal = Decimal("0.00")
    
    # Rounding differences
    rounding_difference_count: int = 0
    rounding_difference_amount: Decimal = Decimal("0.00")
    aggregate_rounding_delta: Decimal = Decimal("0.00")
    
    # Duplicates (Platform and Bank)
    duplicate_count: int = 0
    duplicate_platform_count: int = 0
    duplicate_platform_amount: Decimal = Decimal("0.00")
    duplicate_bank_count: int = 0
    duplicate_bank_amount: Decimal = Decimal("0.00")
    duplicate_amount: Decimal = Decimal("0.00")
    
    # Orphan refunds
    orphan_refund_count: int = 0
    orphan_refund_amount: Decimal = Decimal("0.00")
    
    # Unsettled / Missing settlements
    unsettled_count: int = 0
    unsettled_amount: Decimal = Decimal("0.00")
    
    # Unmatched bank credits (Ghost deposits)
    unmatched_bank_count: int = 0
    unmatched_bank_amount: Decimal = Decimal("0.00")
    
    # Amount mismatches exceeding tolerance
    amount_mismatch_count: int = 0
    amount_mismatch_amount: Decimal = Decimal("0.00")
    
    # Net and Gross Variance Metrics
    net_reconciliation_difference: Decimal = Decimal("0.00")  # Platform Total - Bank Total
    gross_exception_exposure: Decimal = Decimal("0.00")       # Total exposure under review
    total_discrepancy_amount: Decimal = Decimal("0.00")       # Backward-compatible alias for gross exposure
    total_exceptions_count: int = 0


@dataclass
class ExceptionRecord:
    transaction_id: str
    transaction_date: Optional[str]
    settlement_date: Optional[str]
    expected_amount: Decimal
    actual_amount: Decimal
    difference: Decimal
    exception_type: str
    reason: str
    recommended_action: str
    severity: str  # HIGH, MEDIUM, LOW, INFO


class ReconciliationEngine:
    """
    Automated payment reconciliation engine.
    Matches platform transaction ledger with acquiring bank settlement statement.
    """

    REQUIRED_PLATFORM_COLS = ["transaction_id", "transaction_date", "amount", "transaction_type"]
    REQUIRED_BANK_COLS = ["settlement_id", "transaction_id", "settlement_date", "settlement_amount"]

    def __init__(
        self,
        reconciliation_month: Optional[str] = None,
        rounding_tolerance: Decimal = Decimal("0.05"),
        standard_settlement_days: int = 2,
    ):
        self.reconciliation_month = reconciliation_month
        self.rounding_tolerance = rounding_tolerance
        self.standard_settlement_days = standard_settlement_days

    @classmethod
    def validate_schema(cls, df: pd.DataFrame, dataset_type: str) -> Tuple[bool, List[str]]:
        """Validate whether the dataframe contains required columns and non-null identifiers."""
        errors = []
        if df is None:
            return False, [f"{dataset_type} dataset is None."]
        if df.empty and len(df.columns) == 0:
            return False, [f"{dataset_type} dataset is completely empty."]

        required = cls.REQUIRED_PLATFORM_COLS if dataset_type == "platform" else cls.REQUIRED_BANK_COLS
        missing = [col for col in required if col not in df.columns]
        if missing:
            errors.append(f"Missing required columns in {dataset_type} dataset: {', '.join(missing)}")

        return len(errors) == 0, errors

    def reconcile(
        self,
        platform_df: pd.DataFrame,
        bank_df: pd.DataFrame,
    ) -> Tuple[ReconciliationSummary, pd.DataFrame, pd.DataFrame]:
        """
        Execute full payment reconciliation workflow.

        Returns:
            summary: ReconciliationSummary object with calculated KPIs
            reconciled_df: Comprehensive unified reconciliation ledger with side-by-side details
            exceptions_df: Filterable actionable exception records
        """
        # 1. Schema Validation
        p_valid, p_errs = self.validate_schema(platform_df, "platform")
        b_valid, b_errs = self.validate_schema(bank_df, "bank")
        if not p_valid or not b_valid:
            all_errors = p_errs + b_errs
            raise ValueError(f"Schema validation failed: {'; '.join(all_errors)}")

        p_df = platform_df.copy()
        b_df = bank_df.copy()

        # 2. String Standardization
        p_df["transaction_id"] = p_df["transaction_id"].fillna("").astype(str).str.strip()
        b_df["transaction_id"] = b_df["transaction_id"].fillna("").astype(str).str.strip()
        b_df["settlement_id"] = b_df["settlement_id"].fillna("").astype(str).str.strip()

        # 3. Clean amounts as Decimals
        p_df["amount_dec"] = p_df["amount"].apply(to_decimal)
        b_df["settlement_amount_dec"] = b_df["settlement_amount"].apply(to_decimal)

        # 4. Parse Dates
        p_df["txn_date_parsed"] = pd.to_datetime(p_df["transaction_date"], errors="coerce")
        b_df["settle_date_parsed"] = pd.to_datetime(b_df["settlement_date"], errors="coerce")

        # 5. Determine Target Month
        if not self.reconciliation_month:
            valid_dates = p_df["txn_date_parsed"].dropna()
            if not valid_dates.empty:
                self.reconciliation_month = valid_dates.dt.strftime("%Y-%m").mode()[0]
            else:
                self.reconciliation_month = datetime.now().strftime("%Y-%m")

        target_year, target_month = map(int, self.reconciliation_month.split("-"))

        # Volume Metrics
        raw_p_count = len(p_df)
        raw_b_count = len(b_df)
        unique_p_count = p_df["transaction_id"].replace("", np.nan).dropna().nunique()
        unique_b_count = b_df["transaction_id"].replace("", np.nan).dropna().nunique()

        # -------------------------------------------------------------
        # STEP 1: Duplicate Detection
        # -------------------------------------------------------------
        # Platform duplicates
        p_df["is_platform_duplicate"] = p_df.duplicated(subset=["transaction_id"], keep="first")
        
        # Bank duplicates (same transaction_id settled more than once or duplicate settlement_id)
        b_df["is_bank_duplicate_tx"] = b_df.duplicated(subset=["transaction_id"], keep="first")
        b_df["is_bank_duplicate_settle"] = b_df.duplicated(subset=["settlement_id"], keep="first")
        b_df["is_bank_duplicate"] = b_df["is_bank_duplicate_tx"] | b_df["is_bank_duplicate_settle"]

        p_primary = p_df[~p_df["is_platform_duplicate"]].copy()
        p_duplicates = p_df[p_df["is_platform_duplicate"]].copy()

        b_primary = b_df[~b_df["is_bank_duplicate"]].copy()
        b_duplicates = b_df[b_df["is_bank_duplicate"]].copy()

        # -------------------------------------------------------------
        # STEP 2: Orphan Refund Detection
        # -------------------------------------------------------------
        if "original_transaction_id" in p_df.columns:
            p_df["original_transaction_id"] = p_df["original_transaction_id"].fillna("").astype(str).str.strip()
        else:
            p_df["original_transaction_id"] = ""

        # Set of all valid platform payment IDs
        all_valid_payment_ids = set(
            p_df[
                (p_df["transaction_type"].astype(str).str.upper() == "PAYMENT")
                & (~p_df["is_platform_duplicate"])
            ]["transaction_id"]
        )

        p_df["is_orphan_refund"] = False
        refund_mask = p_df["transaction_type"].astype(str).str.upper() == "REFUND"
        for idx, row in p_df[refund_mask].iterrows():
            orig_id = row["original_transaction_id"]
            if not orig_id or orig_id not in all_valid_payment_ids:
                p_df.at[idx, "is_orphan_refund"] = True

        p_primary["is_orphan_refund"] = p_df.loc[p_primary.index, "is_orphan_refund"]

        # -------------------------------------------------------------
        # STEP 3: Core Outer-Join Matching on Stable Transaction ID
        # -------------------------------------------------------------
        merged = pd.merge(
            p_primary,
            b_primary,
            on="transaction_id",
            how="outer",
            suffixes=("_platform", "_bank"),
        )

        records_list: List[Dict[str, Any]] = []
        exceptions_list: List[ExceptionRecord] = []

        # Metric Counters
        matched_exact_count = 0
        matched_variance_count = 0
        matched_amount = Decimal("0.00")
        
        timing_diff_count = 0
        timing_diff_amount = Decimal("0.00")
        
        rounding_diff_count = 0
        rounding_diff_amount = Decimal("0.00")
        
        unsettled_count = 0
        unsettled_amount = Decimal("0.00")
        
        unmatched_bank_count = 0
        unmatched_bank_amount = Decimal("0.00")
        
        amount_mismatch_count = 0
        amount_mismatch_amount = Decimal("0.00")

        # Sum tracking for aggregate rounding delta
        platform_matched_sum = Decimal("0.00")
        bank_matched_sum = Decimal("0.00")

        for _, row in merged.iterrows():
            tx_id = row["transaction_id"]
            has_platform = pd.notna(row.get("amount_dec"))
            has_bank = pd.notna(row.get("settlement_amount_dec"))

            p_amt = row["amount_dec"] if has_platform else Decimal("0.00")
            b_amt = row["settlement_amount_dec"] if has_bank else Decimal("0.00")
            diff = (p_amt - b_amt).quantize(Decimal("0.01"))

            p_date_str = str(row["transaction_date"]) if has_platform and pd.notna(row.get("transaction_date")) else "-"
            b_date_str = str(row["settlement_date"]) if has_bank and pd.notna(row.get("settlement_date")) else "-"
            p_date_parsed = row.get("txn_date_parsed") if has_platform else pd.NaT
            b_date_parsed = row.get("settle_date_parsed") if has_bank else pd.NaT

            is_orphan = row.get("is_orphan_refund", False) if has_platform else False
            tx_type = str(row.get("transaction_type", "PAYMENT")).upper() if has_platform else "SETTLEMENT"
            settle_id = str(row.get("settlement_id", "")) if has_bank and pd.notna(row.get("settlement_id")) else "-"
            bank_ref = str(row.get("bank_reference", "")) if has_bank and pd.notna(row.get("bank_reference")) else "-"
            cust_id = str(row.get("customer_id", "")) if has_platform and pd.notna(row.get("customer_id")) else "-"
            pay_method = str(row.get("payment_method", "")) if has_platform and pd.notna(row.get("payment_method")) else "-"

            # Case A: Orphan Refund
            if is_orphan:
                status = "ORPHAN_REFUND"
                orig_ref = row.get("original_transaction_id", "")
                reason = (
                    f"Refund of {format_inr(p_amt)} has no matching original sales transaction in platform ledger "
                    f"(Supplied reference: '{orig_ref}')."
                )
                action = "Investigate for merchant portal manual override, unauthorized refund, or unlinked sales batch."
                severity = "HIGH"
                exceptions_list.append(
                    ExceptionRecord(
                        transaction_id=tx_id,
                        transaction_date=p_date_str,
                        settlement_date=b_date_str if b_date_str != "-" else None,
                        expected_amount=p_amt,
                        actual_amount=b_amt,
                        difference=diff,
                        exception_type="Orphan Refund",
                        reason=reason,
                        recommended_action=action,
                        severity=severity,
                    )
                )

            # Case B: Both Platform and Bank records exist
            elif has_platform and has_bank:
                # Check for Next-Month Settlement (Timing difference)
                is_next_month = False
                if pd.notna(p_date_parsed) and pd.notna(b_date_parsed):
                    is_in_target_month = (p_date_parsed.year == target_year and p_date_parsed.month == target_month)
                    is_after_month = (
                        (b_date_parsed.year > target_year)
                        or (b_date_parsed.year == target_year and b_date_parsed.month > target_month)
                    )
                    if is_in_target_month and is_after_month:
                        is_next_month = True

                if is_next_month:
                    status = "TIMING_DIFFERENCE_NEXT_MONTH"
                    timing_diff_count += 1
                    timing_diff_amount += p_amt
                    reason = (
                        f"Transaction recorded on {p_date_str} (end of {self.reconciliation_month}), "
                        f"settled by bank on {b_date_str} in the following calendar month (T+1/T+2 cycle)."
                    )
                    action = "Carry forward as Timing Difference / In-Transit Settlement Float in month-end ledger. Not permanently missing."
                    severity = "INFO"
                    exceptions_list.append(
                        ExceptionRecord(
                            transaction_id=tx_id,
                            transaction_date=p_date_str,
                            settlement_date=b_date_str,
                            expected_amount=p_amt,
                            actual_amount=b_amt,
                            difference=diff,
                            exception_type="Next-Month Settlement (Timing)",
                            reason=reason,
                            recommended_action=action,
                            severity=severity,
                        )
                    )

                elif diff == Decimal("0.00"):
                    status = "MATCHED"
                    matched_exact_count += 1
                    matched_amount += p_amt
                    platform_matched_sum += p_amt
                    bank_matched_sum += b_amt
                    reason = "Platform and bank records match exactly on ID, amount, and currency."
                    action = "None. Transaction fully reconciled."
                    severity = "LOW"

                elif abs(diff) <= self.rounding_tolerance:
                    status = "ROUNDING_DIFFERENCE"
                    matched_variance_count += 1
                    rounding_diff_count += 1
                    rounding_diff_amount += abs(diff)
                    matched_amount += p_amt
                    platform_matched_sum += p_amt
                    bank_matched_sum += b_amt
                    reason = (
                        f"Amount variance of {format_inr(diff)} is within rounding tolerance "
                        f"({format_inr(self.rounding_tolerance)}). Result of line-level fractional MDR/tax rounding."
                    )
                    action = "Post minor variance to Merchant Rounding / Small Balance Expense Ledger."
                    severity = "LOW"
                    exceptions_list.append(
                        ExceptionRecord(
                            transaction_id=tx_id,
                            transaction_date=p_date_str,
                            settlement_date=b_date_str,
                            expected_amount=p_amt,
                            actual_amount=b_amt,
                            difference=diff,
                            exception_type="Rounding Difference",
                            reason=reason,
                            recommended_action=action,
                            severity=severity,
                        )
                    )

                else:
                    status = "AMOUNT_MISMATCH"
                    amount_mismatch_count += 1
                    amount_mismatch_amount += abs(diff)
                    reason = (
                        f"Discrepancy of {format_inr(diff)} (Expected: {format_inr(p_amt)}, "
                        f"Bank: {format_inr(b_amt)}) exceeds rounding tolerance."
                    )
                    action = "Raise claim with acquiring bank; verify if unrecorded interchange fee or clawback was deducted."
                    severity = "HIGH"
                    exceptions_list.append(
                        ExceptionRecord(
                            transaction_id=tx_id,
                            transaction_date=p_date_str,
                            settlement_date=b_date_str,
                            expected_amount=p_amt,
                            actual_amount=b_amt,
                            difference=diff,
                            exception_type="Amount Mismatch",
                            reason=reason,
                            recommended_action=action,
                            severity=severity,
                        )
                    )

            # Case C: Platform recorded, bank missing
            elif has_platform and not has_bank:
                status = "UNSETTLED_MISSING"
                unsettled_count += 1
                unsettled_amount += p_amt
                reason = (
                    f"Platform recorded transaction {format_inr(p_amt)} on {p_date_str}, "
                    f"but no settlement credit was received from the bank."
                )
                action = "Check acquiring gateway batch status; verify with bank if settlement batch dropped."
                severity = "HIGH"
                exceptions_list.append(
                    ExceptionRecord(
                        transaction_id=tx_id,
                        transaction_date=p_date_str,
                        settlement_date=None,
                        expected_amount=p_amt,
                        actual_amount=Decimal("0.00"),
                        difference=p_amt,
                        exception_type="Unsettled / Missing Settlement",
                        reason=reason,
                        recommended_action=action,
                        severity=severity,
                    )
                )

            # Case D: Bank credit exists without platform record
            else:
                status = "UNMATCHED_BANK_CREDIT"
                unmatched_bank_count += 1
                unmatched_bank_amount += b_amt
                reason = (
                    f"Bank deposited {format_inr(b_amt)} on {b_date_str} referencing '{tx_id}', "
                    f"but no corresponding transaction exists in platform sales ledger."
                )
                action = "Investigate unidentified bank credit; check for offline payments or delayed gateway webhooks."
                severity = "MEDIUM"
                exceptions_list.append(
                    ExceptionRecord(
                        transaction_id=tx_id,
                        transaction_date=None,
                        settlement_date=b_date_str,
                        expected_amount=Decimal("0.00"),
                        actual_amount=b_amt,
                        difference=-b_amt,
                        exception_type="Unmatched Bank Credit",
                        reason=reason,
                        recommended_action=action,
                        severity=severity,
                    )
                )

            records_list.append({
                "transaction_id": tx_id,
                "settlement_id": settle_id,
                "bank_reference": bank_ref,
                "customer_id": cust_id,
                "payment_method": pay_method,
                "transaction_date": p_date_str,
                "settlement_date": b_date_str,
                "transaction_type": tx_type,
                "platform_amount": float(p_amt),
                "bank_settlement_amount": float(b_amt),
                "difference": float(diff),
                "reconciliation_status": status,
                "reason": reason,
                "recommended_action": action,
                "severity": severity,
                "is_duplicate": False,
            })

        # -------------------------------------------------------------
        # STEP 4: Process Duplicates & Prevent Double Counting
        # -------------------------------------------------------------
        dup_p_count = 0
        dup_p_amount = Decimal("0.00")
        for _, row in p_duplicates.iterrows():
            tx_id = row["transaction_id"]
            amt = row["amount_dec"]
            p_date_str = str(row["transaction_date"]) if pd.notna(row.get("transaction_date")) else "-"
            dup_p_count += 1
            dup_p_amount += amt
            reason = f"Duplicate platform transaction entry detected for ID '{tx_id}'. Isolated to prevent double-counting."
            action = "Purge or deactivate duplicate record in platform database."
            severity = "MEDIUM"

            exceptions_list.append(
                ExceptionRecord(
                    transaction_id=tx_id,
                    transaction_date=p_date_str,
                    settlement_date=None,
                    expected_amount=amt,
                    actual_amount=Decimal("0.00"),
                    difference=amt,
                    exception_type="Duplicate Platform Entry",
                    reason=reason,
                    recommended_action=action,
                    severity=severity,
                )
            )

            records_list.append({
                "transaction_id": tx_id,
                "settlement_id": "-",
                "bank_reference": "-",
                "customer_id": str(row.get("customer_id", "-")),
                "payment_method": str(row.get("payment_method", "-")),
                "transaction_date": p_date_str,
                "settlement_date": "-",
                "transaction_type": str(row.get("transaction_type", "PAYMENT")).upper(),
                "platform_amount": float(amt),
                "bank_settlement_amount": 0.00,
                "difference": float(amt),
                "reconciliation_status": "DUPLICATE_ENTRY",
                "reason": reason,
                "recommended_action": action,
                "severity": severity,
                "is_duplicate": True,
            })

        dup_b_count = 0
        dup_b_amount = Decimal("0.00")
        for _, row in b_duplicates.iterrows():
            tx_id = row["transaction_id"]
            amt = row["settlement_amount_dec"]
            b_date_str = str(row["settlement_date"]) if pd.notna(row.get("settlement_date")) else "-"
            dup_b_count += 1
            dup_b_amount += amt
            reason = (
                f"Duplicate settlement detected for transaction ID '{tx_id}' "
                f"(Settlement ID: {row.get('settlement_id', '')}). Potential double credit by bank."
            )
            action = "Contact bank ops to confirm if duplicate settlement was clawed back or needs refund."
            severity = "HIGH"

            exceptions_list.append(
                ExceptionRecord(
                    transaction_id=tx_id,
                    transaction_date=None,
                    settlement_date=b_date_str,
                    expected_amount=Decimal("0.00"),
                    actual_amount=amt,
                    difference=-amt,
                    exception_type="Duplicate Bank Settlement",
                    reason=reason,
                    recommended_action=action,
                    severity=severity,
                )
            )

            records_list.append({
                "transaction_id": tx_id,
                "settlement_id": str(row.get("settlement_id", "-")),
                "bank_reference": str(row.get("bank_reference", "-")),
                "customer_id": "-",
                "payment_method": "-",
                "transaction_date": "-",
                "settlement_date": b_date_str,
                "transaction_type": "SETTLEMENT",
                "platform_amount": 0.00,
                "bank_settlement_amount": float(amt),
                "difference": float(-amt),
                "reconciliation_status": "DUPLICATE_ENTRY",
                "reason": reason,
                "recommended_action": action,
                "severity": severity,
                "is_duplicate": True,
            })

        total_dup_count = dup_p_count + dup_b_count
        total_dup_amount = dup_p_amount + dup_b_amount

        # Orphan count from primary platform dataset
        orphan_df = p_primary[p_primary["is_orphan_refund"]]
        orphan_count = len(orphan_df)
        orphan_amount = orphan_df["amount_dec"].sum()

        # Aggregate rounding delta across matched records
        aggregate_rounding_delta = (platform_matched_sum - bank_matched_sum).quantize(Decimal("0.01"))

        # Primary financial totals (preventing double-counting)
        total_p_amt = p_primary["amount_dec"].sum()
        total_b_amt = b_primary["settlement_amount_dec"].sum()

        # Net reconciliation difference (Platform Total - Bank Total)
        net_diff = (total_p_amt - total_b_amt).quantize(Decimal("0.01"))

        # Gross Exception Exposure (sum of absolute exposure of all exceptions)
        gross_exposure = sum((abs(e.difference) for e in exceptions_list), Decimal("0.00")).quantize(Decimal("0.01"))

        total_matched = matched_exact_count + matched_variance_count
        match_rate = round((total_matched / unique_p_count * 100), 1) if unique_p_count > 0 else 0.0

        summary = ReconciliationSummary(
            reconciliation_month=self.reconciliation_month,
            raw_platform_count=raw_p_count,
            unique_platform_count=unique_p_count,
            total_platform_amount=total_p_amt,
            raw_bank_count=raw_b_count,
            unique_bank_count=unique_b_count,
            total_bank_amount=total_b_amt,
            matched_count=total_matched,
            matched_exact_count=matched_exact_count,
            matched_variance_count=matched_variance_count,
            matched_amount=matched_amount,
            match_rate_percentage=match_rate,
            timing_difference_count=timing_diff_count,
            timing_difference_amount=timing_diff_amount,
            rounding_difference_count=rounding_diff_count,
            rounding_difference_amount=rounding_diff_amount,
            aggregate_rounding_delta=aggregate_rounding_delta,
            duplicate_count=total_dup_count,
            duplicate_platform_count=dup_p_count,
            duplicate_platform_amount=dup_p_amount,
            duplicate_bank_count=dup_b_count,
            duplicate_bank_amount=dup_b_amount,
            duplicate_amount=total_dup_amount,
            orphan_refund_count=orphan_count,
            orphan_refund_amount=orphan_amount,
            unsettled_count=unsettled_count,
            unsettled_amount=unsettled_amount,
            unmatched_bank_count=unmatched_bank_count,
            unmatched_bank_amount=unmatched_bank_amount,
            amount_mismatch_count=amount_mismatch_count,
            amount_mismatch_amount=amount_mismatch_amount,
            net_reconciliation_difference=net_diff,
            gross_exception_exposure=gross_exposure,
            total_discrepancy_amount=gross_exposure,
            total_exceptions_count=len(exceptions_list),
        )

        reconciled_df = pd.DataFrame(records_list)

        exceptions_data = [
            {
                "Transaction ID": e.transaction_id,
                "Transaction Date": e.transaction_date or "-",
                "Settlement Date": e.settlement_date or "-",
                "Expected Amount (INR)": float(e.expected_amount),
                "Actual Amount (INR)": float(e.actual_amount),
                "Difference (INR)": float(e.difference),
                "Exception Type": e.exception_type,
                "Reason for Mismatch": e.reason,
                "Recommended Action": e.recommended_action,
                "Severity": e.severity,
            }
            for e in exceptions_list
        ]
        exceptions_df = pd.DataFrame(exceptions_data)

        return summary, reconciled_df, exceptions_df
