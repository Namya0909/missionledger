"""Tax Prep Pack data as a CSV — "a CSV their accountant can open." No AI involved;
pure formatting of tax_prep.py's already-computed numbers, same split-of-concerns as
tax_pdf_builder.py.
"""

import csv
import io

from tax_prep import BusinessTaxData, GroupTaxData, NonprofitTaxData


def _to_csv(header: list[str], rows: list[list]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue()


def build_group_tax_csv(data: GroupTaxData) -> str:
    rows = [
        [bucket.label, item.date.isoformat(), item.merchant, f"{item.amount:.2f}", "Yes" if item.has_receipt else "No"]
        for bucket in data.buckets
        for item in bucket.items
    ]
    return _to_csv(["Category", "Date", "Merchant", "Amount", "Receipt on file"], rows)


def build_nonprofit_tax_csv(data: NonprofitTaxData) -> str:
    rows = [["Gross receipts", "", "", f"{data.gross_receipts:.2f}", ""]]
    rows += [["Spending by category", k, "", f"{v:.2f}", ""] for k, v in data.bucket_totals.items()]
    rows += [["Donor ($250+)", d.donor_name, d.date.isoformat(), f"{d.amount:.2f}", ""] for d in data.donors]
    return _to_csv(["Section", "Name/Category", "Date", "Amount", "Notes"], rows)


def build_business_tax_csv(data: BusinessTaxData) -> str:
    rows = [
        ["Taxable sales", "", f"{data.taxable_sales:.2f}"],
        ["Sales tax rate", "", f"{data.sales_tax_rate * 100:.2f}%"],
        ["Sales tax owed", "", f"{data.tax_owed:.2f}"],
        ["Already saved", "", f"{data.already_saved:.2f}"],
        ["Next estimated tax due date", "", data.next_estimated_due_date.isoformat()],
    ]
    rows += [["Contractor paid $600+", c.merchant, f"{c.total_paid:.2f}"] for c in data.contractors]
    return _to_csv(["Item", "Name", "Value"], rows)
