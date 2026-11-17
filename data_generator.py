"""
Synthetic Data Generator for Payment Reconciliation
===================================================
Generates realistic platform transaction and bank settlement datasets (in INR)
with intentionally planted edge cases:
  1. Next-month settlement (Timing difference)
  2. Rounding difference (Individual paise variance + Aggregate summation variance)
  3. Duplicate entry (Duplicate bank settlement / platform entry)
  4. Orphan refund (Refund referencing non-existent transaction)
"""

import os
import random
import calendar
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Tuple
import pandas as pd


def generate_synthetic_data(
    num_records: int = 50,
    month: str = "2026-10",
    seed: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generate platform transactions and bank settlements.
    
    :param num_records: Base number of normal transactions.
    :param month: Target reconciliation month in 'YYYY-MM' format.
    :param seed: Random seed for reproducible generation.
    :return: (platform_df, bank_df)
    """
    random.seed(seed)
    year, month_num = map(int, month.split("-"))
    
    # Days in month: October has 31 days
    start_date = datetime(year, month_num, 1, 9, 0, 0)
    
    platform_rows = []
    bank_rows = []
    
    settle_counter = 1000

    # -------------------------------------------------------------
    # 1. Generate Standard Matching Transactions (T+1 to T+2 days)
    # -------------------------------------------------------------
    customer_ids = [f"CUST_{i:04d}" for i in range(1, 25)]
    payment_methods = ["UPI", "CREDIT_CARD", "DEBIT_CARD", "NET_BANKING"]
    common_amounts = [
        199.00, 249.50, 499.00, 799.00, 999.00, 1299.50,
        1499.00, 2499.00, 4999.00, 9999.00, 15000.00
    ]

    for i in range(1, num_records + 1):
        tx_id = f"TXN_{year}{month_num:02d}_{i:04d}"
        day = min(28, 1 + (i % 27))
        hour = random.randint(8, 22)
        minute = random.randint(0, 59)
        second = random.randint(0, 59)
        tx_date = datetime(year, month_num, day, hour, minute, second)
        
        amt = Decimal(str(random.choice(common_amounts)))
        method = random.choice(payment_methods)
        cust = random.choice(customer_ids)

        platform_rows.append({
            "transaction_id": tx_id,
            "transaction_date": tx_date.strftime("%Y-%m-%d %H:%M:%S"),
            "customer_id": cust,
            "payment_method": method,
            "transaction_type": "PAYMENT",
            "amount": float(amt),
            "currency": "INR",
            "status": "SUCCESS",
            "original_transaction_id": "",
            "notes": "Standard customer payment",
        })

        # Bank settles 1 to 2 business days later
        settle_lag_days = random.choice([1, 2])
        settle_date = (tx_date + timedelta(days=settle_lag_days)).strftime("%Y-%m-%d")
        settle_counter += 1
        settle_id = f"SETTL_{year}{month_num:02d}_{settle_counter}"
        bank_ref = f"UTR{year}{month_num:02d}{random.randint(100000, 999999)}"

        bank_rows.append({
            "settlement_id": settle_id,
            "transaction_id": tx_id,
            "settlement_date": settle_date,
            "settlement_amount": float(amt),
            "currency": "INR",
            "bank_reference": bank_ref,
            "settlement_status": "SETTLED",
            "notes": "Direct bank clearance",
        })

    # -------------------------------------------------------------
    # 2. Plant Problem #1: Next-Month Settlement (Timing Difference)
    # Transaction on the last day of the month (e.g., Oct 31 or Sep 30)
    # Bank settles on day 2 of following month
    # -------------------------------------------------------------
    last_day = calendar.monthrange(year, month_num)[1]
    timing_tx_id = f"TXN_{year}{month_num:02d}_9001"
    timing_tx_date = datetime(year, month_num, last_day, 21, 45, 10)
    timing_amt = 4500.00
    platform_rows.append({
        "transaction_id": timing_tx_id,
        "transaction_date": timing_tx_date.strftime("%Y-%m-%d %H:%M:%S"),
        "customer_id": "CUST_0088",
        "payment_method": "UPI",
        "transaction_type": "PAYMENT",
        "amount": timing_amt,
        "currency": "INR",
        "status": "SUCCESS",
        "original_transaction_id": "",
        "notes": "Month-end evening transaction",
    })
    
    # Settles in following month (Month + 1)
    settle_counter += 1
    next_month_num = 1 if month_num == 12 else month_num + 1
    next_year = year + 1 if month_num == 12 else year
    settle_nov_date = datetime(next_year, next_month_num, 2).strftime("%Y-%m-%d")
    bank_rows.append({
        "settlement_id": f"SETTL_{next_year}{next_month_num:02d}_{settle_counter}",
        "transaction_id": timing_tx_id,
        "settlement_date": settle_nov_date,
        "settlement_amount": timing_amt,
        "currency": "INR",
        "bank_reference": f"UTR{next_year}{next_month_num:02d}778899",
        "settlement_status": "SETTLED",
        "notes": "Settled on T+2 into subsequent month",
    })

    # -------------------------------------------------------------
    # 3. Plant Problem #2: Rounding Difference
    # Individual amounts look very close (e.g. ₹1,499.50 vs ₹1,499.48 and ₹2,350.25 vs ₹2,350.22)
    # Summing creates visible aggregate rounding divergence
    # -------------------------------------------------------------
    rounding_cases = [
        (f"TXN_{year}{month_num:02d}_8001", 1499.50, 1499.48, "2 paise MDR rounding difference"),
        (f"TXN_{year}{month_num:02d}_8002", 2350.25, 2350.22, "3 paise interchange fraction truncation"),
        (f"TXN_{year}{month_num:02d}_8003", 850.75, 850.73, "2 paise fractional GST calculation diff"),
    ]
    for r_idx, (r_tx_id, p_val, b_val, r_note) in enumerate(rounding_cases, start=1):
        r_date = datetime(year, month_num, 15 + r_idx, 14, 20, 0)
        platform_rows.append({
            "transaction_id": r_tx_id,
            "transaction_date": r_date.strftime("%Y-%m-%d %H:%M:%S"),
            "customer_id": f"CUST_00{r_idx:02d}",
            "payment_method": "CREDIT_CARD",
            "transaction_type": "PAYMENT",
            "amount": p_val,
            "currency": "INR",
            "status": "SUCCESS",
            "original_transaction_id": "",
            "notes": f"Item subject to fractional MDR: {r_note}",
        })
        settle_counter += 1
        bank_rows.append({
            "settlement_id": f"SETTL_{year}{month_num:02d}_{settle_counter}",
            "transaction_id": r_tx_id,
            "settlement_date": (r_date + timedelta(days=1)).strftime("%Y-%m-%d"),
            "settlement_amount": b_val,
            "currency": "INR",
            "bank_reference": f"UTR{year}{month_num:02d}8811{r_idx}",
            "settlement_status": "SETTLED",
            "notes": f"Bank settlement with {r_note}",
        })

    # -------------------------------------------------------------
    # 4. Plant Problem #3: Duplicate Entry
    # Include duplicate settlement entry in the bank dataset (same transaction settled twice)
    # -------------------------------------------------------------
    dup_tx_id = f"TXN_{year}{month_num:02d}_0010"
    dup_date = datetime(year, month_num, 10, 11, 0, 0)
    # The transaction exists in platform_rows (already generated at index 10)
    # Now create duplicate settlement in bank_settlements!
    settle_counter += 1
    bank_rows.append({
        "settlement_id": f"SETTL_{year}{month_num:02d}_{settle_counter}_DUP",
        "transaction_id": dup_tx_id,
        "settlement_date": (dup_date + timedelta(days=2)).strftime("%Y-%m-%d"),
        "settlement_amount": 499.00,
        "currency": "INR",
        "bank_reference": f"UTR{year}{month_num:02d}DUP999",
        "settlement_status": "SETTLED",
        "notes": "DUPLICATE: Erroneous duplicate batch upload by bank partner",
    })

    # -------------------------------------------------------------
    # 5. Plant Problem #4: Orphan Refund
    # Platform refund with NO original transaction record
    # -------------------------------------------------------------
    orphan_refund_id = f"TXN_{year}{month_num:02d}_7001"
    orphan_date = datetime(year, month_num, 20, 16, 30, 0)
    platform_rows.append({
        "transaction_id": orphan_refund_id,
        "transaction_date": orphan_date.strftime("%Y-%m-%d %H:%M:%S"),
        "customer_id": "CUST_0099",
        "payment_method": "UPI",
        "transaction_type": "REFUND",
        "amount": 750.00,
        "currency": "INR",
        "status": "SUCCESS",
        "original_transaction_id": "TXN_202512_9999_NONEXISTENT",
        "notes": "ORPHAN REFUND: Initiated without valid parent sales transaction",
    })

    # -------------------------------------------------------------
    # 6. Additional Realistic Edge Cases
    # a) Legitimate Refund with existing parent transaction
    # -------------------------------------------------------------
    parent_tx_id = f"TXN_{year}{month_num:02d}_0003"
    valid_refund_id = f"TXN_{year}{month_num:02d}_7002"
    valid_refund_date = datetime(year, month_num, 18, 12, 10, 0)
    platform_rows.append({
        "transaction_id": valid_refund_id,
        "transaction_date": valid_refund_date.strftime("%Y-%m-%d %H:%M:%S"),
        "customer_id": "CUST_0003",
        "payment_method": "UPI",
        "transaction_type": "REFUND",
        "amount": 499.00,
        "currency": "INR",
        "status": "SUCCESS",
        "original_transaction_id": parent_tx_id,
        "notes": f"Valid refund referencing original payment {parent_tx_id}",
    })
    settle_counter += 1
    bank_rows.append({
        "settlement_id": f"SETTL_{year}{month_num:02d}_{settle_counter}",
        "transaction_id": valid_refund_id,
        "settlement_date": (valid_refund_date + timedelta(days=1)).strftime("%Y-%m-%d"),
        "settlement_amount": 499.00,
        "currency": "INR",
        "bank_reference": f"UTR{year}{month_num:02d}REF499",
        "settlement_status": "SETTLED",
        "notes": "Refund settlement debited by bank",
    })

    # b) Unsettled / Missing Bank Settlement (Platform recorded payment, bank dropped it)
    unsettled_tx_id = f"TXN_{year}{month_num:02d}_6001"
    unsettled_date = datetime(year, month_num, 12, 15, 0, 0)
    platform_rows.append({
        "transaction_id": unsettled_tx_id,
        "transaction_date": unsettled_date.strftime("%Y-%m-%d %H:%M:%S"),
        "customer_id": "CUST_0015",
        "payment_method": "NET_BANKING",
        "transaction_type": "PAYMENT",
        "amount": 3200.00,
        "currency": "INR",
        "status": "SUCCESS",
        "original_transaction_id": "",
        "notes": "Payment processed on gateway but no settlement received from acquiring bank",
    })

    # c) Unmatched Bank Settlement (Bank received credit, platform has no record)
    settle_counter += 1
    bank_rows.append({
        "settlement_id": f"SETTL_{year}{month_num:02d}_{settle_counter}",
        "transaction_id": f"TXN_{year}{month_num:02d}_UNKNOWN_99",
        "settlement_date": f"{year}-{month_num:02d}-22",
        "settlement_amount": 1850.00,
        "currency": "INR",
        "bank_reference": f"UTR{year}{month_num:02d}GHOST",
        "settlement_status": "SETTLED",
        "notes": "Direct bank credit without matching platform transaction ID",
    })

    platform_df = pd.DataFrame(platform_rows)
    bank_df = pd.DataFrame(bank_rows)

    return platform_df, bank_df


def save_datasets(
    output_dir: str = "data",
    num_records: int = 50,
    month: str = "2026-10",
) -> Tuple[str, str]:
    """Generate datasets and save them to CSV files."""
    os.makedirs(output_dir, exist_ok=True)
    platform_df, bank_df = generate_synthetic_data(num_records=num_records, month=month)
    
    platform_path = os.path.join(output_dir, "platform_transactions.csv")
    bank_path = os.path.join(output_dir, "bank_settlements.csv")
    
    platform_df.to_csv(platform_path, index=False)
    bank_df.to_csv(bank_path, index=False)
    
    return platform_path, bank_path


def get_data_issue_manifest(month: str = "2026-10") -> pd.DataFrame:
    """Return an audit manifest of all planted discrepancy scenarios in the test dataset."""
    year, month_num = map(int, month.split("-"))
    manifest = [
        {
            "Transaction ID": f"TXN_{year}{month_num:02d}_9001",
            "Planted Issue Type": "Next-Month Settlement (Timing)",
            "Expected Classification": "TIMING_DIFFERENCE_NEXT_MONTH",
            "Platform Amount (INR)": 4500.00,
            "Bank Amount (INR)": 4500.00,
            "Difference (INR)": 0.00,
            "Planted Scenario": "Month-end evening payment settled T+2 into subsequent month.",
            "Expected Action": "Carry forward into month-end in-transit float ledger.",
        },
        {
            "Transaction ID": f"TXN_{year}{month_num:02d}_8001",
            "Planted Issue Type": "Rounding Difference",
            "Expected Classification": "ROUNDING_DIFFERENCE",
            "Platform Amount (INR)": 1499.50,
            "Bank Amount (INR)": 1499.48,
            "Difference (INR)": 0.02,
            "Planted Scenario": "2 paise fractional interchange / MDR rounding difference.",
            "Expected Action": "Post to rounding / FX / small balance expense ledger.",
        },
        {
            "Transaction ID": f"TXN_{year}{month_num:02d}_8002",
            "Planted Issue Type": "Rounding Difference",
            "Expected Classification": "ROUNDING_DIFFERENCE",
            "Platform Amount (INR)": 2350.25,
            "Bank Amount (INR)": 2350.22,
            "Difference (INR)": 0.03,
            "Planted Scenario": "3 paise interchange fractional deduction difference.",
            "Expected Action": "Post to rounding / FX / small balance expense ledger.",
        },
        {
            "Transaction ID": f"TXN_{year}{month_num:02d}_8003",
            "Planted Issue Type": "Rounding Difference",
            "Expected Classification": "ROUNDING_DIFFERENCE",
            "Platform Amount (INR)": 850.75,
            "Bank Amount (INR)": 850.73,
            "Difference (INR)": 0.02,
            "Planted Scenario": "2 paise fractional GST calculation variance.",
            "Expected Action": "Post to rounding / FX / small balance expense ledger.",
        },
        {
            "Transaction ID": f"TXN_{year}{month_num:02d}_0010",
            "Planted Issue Type": "Duplicate Bank Settlement",
            "Expected Classification": "DUPLICATE_ENTRY",
            "Platform Amount (INR)": 499.00,
            "Bank Amount (INR)": 499.00,
            "Difference (INR)": -499.00,
            "Planted Scenario": "Bank uploaded duplicate settlement entry for the same payment.",
            "Expected Action": "Quarantine duplicate and verify with bank partner.",
        },
        {
            "Transaction ID": f"TXN_{year}{month_num:02d}_7001",
            "Planted Issue Type": "Orphan Refund",
            "Expected Classification": "ORPHAN_REFUND",
            "Platform Amount (INR)": 750.00,
            "Bank Amount (INR)": 0.00,
            "Difference (INR)": 750.00,
            "Planted Scenario": "Refund initiated without matching original sales transaction in platform.",
            "Expected Action": "Flag HIGH severity; investigate potential fraud or missing sales batch.",
        },
        {
            "Transaction ID": f"TXN_{year}{month_num:02d}_6001",
            "Planted Issue Type": "Unsettled / Missing Settlement",
            "Expected Classification": "UNSETTLED_MISSING",
            "Platform Amount (INR)": 3200.00,
            "Bank Amount (INR)": 0.00,
            "Difference (INR)": 3200.00,
            "Planted Scenario": "Payment processed on gateway, but bank settlement batch was dropped.",
            "Expected Action": "Escalate to acquiring bank ops to re-initiate settlement payout.",
        },
        {
            "Transaction ID": f"TXN_{year}{month_num:02d}_UNKNOWN_99",
            "Planted Issue Type": "Unmatched Bank Credit",
            "Expected Classification": "UNMATCHED_BANK_CREDIT",
            "Platform Amount (INR)": 0.00,
            "Bank Amount (INR)": 1850.00,
            "Difference (INR)": -1850.00,
            "Planted Scenario": "Bank deposited funds without any corresponding platform transaction ID.",
            "Expected Action": "Audit bank statement for unidentified direct wire or missed webhook.",
        },
    ]
    return pd.DataFrame(manifest)


def get_sample_platform_template_csv() -> str:
    """Return clean CSV string template for platform transaction uploads."""
    rows = [
        "transaction_id,transaction_date,customer_id,payment_method,transaction_type,amount,currency,status,original_transaction_id,notes",
        "TXN_SAMPLE_001,2026-10-01 10:15:30,CUST_0001,UPI,PAYMENT,1499.00,INR,SUCCESS,,Sample customer order",
        "TXN_SAMPLE_002,2026-10-02 11:45:00,CUST_0002,CREDIT_CARD,PAYMENT,2499.50,INR,SUCCESS,,Sample retail purchase",
        "TXN_SAMPLE_003,2026-10-05 14:20:10,CUST_0003,UPI,REFUND,499.00,INR,SUCCESS,TXN_SAMPLE_001,Sample refund",
    ]
    return "\n".join(rows)


def get_sample_bank_template_csv() -> str:
    """Return clean CSV string template for bank settlement uploads."""
    rows = [
        "settlement_id,transaction_id,settlement_date,settlement_amount,currency,bank_reference,settlement_status,notes",
        "SETTL_SAMPLE_1001,TXN_SAMPLE_001,2026-10-02,1499.00,INR,UTR202610998811,SETTLED,Acquiring bank clearance",
        "SETTL_SAMPLE_1002,TXN_SAMPLE_002,2026-10-03,2499.50,INR,UTR202610998812,SETTLED,Card network payout",
        "SETTL_SAMPLE_1003,TXN_SAMPLE_003,2026-10-06,499.00,INR,UTR202610998813,SETTLED,Refund debit clearance",
    ]
    return "\n".join(rows)


if __name__ == "__main__":
    p_path, b_path = save_datasets()
    print(f"Platform transactions saved to: {p_path}")
    print(f"Bank settlements saved to: {b_path}")
