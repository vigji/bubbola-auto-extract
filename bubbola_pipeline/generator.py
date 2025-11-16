"""Utilities for synthesizing deterministic ground truth and human-readable PDFs."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Tuple

from fpdf import FPDF

from .models import Invoice, LineItem

DEFAULT_OUTPUT_DIR = Path("tests/generated")


def build_sample_invoice() -> Invoice:
    """Return a deterministic invoice that can be regenerated in tests."""

    return Invoice(
        document_id="demo-invoice-001",
        company_name="Bubbola Research Labs",
        company_address="42 Orbital Terrace, Unit 5, Polaris City",
        customer_name="Axiom Analytics",
        customer_address="177 Market Street, Suite 900, Cascade",
        issue_date=date(2024, 4, 12),
        due_date=date(2024, 5, 12),
        notes="Payment due within 30 days via ACH.",
        line_items=[
            LineItem(description="Data extraction pipeline architecture", quantity=1, unit_price=4200.00),
            LineItem(description="Rust evaluator hardening", quantity=1, unit_price=1850.00),
            LineItem(description="Python PDF prototyping sessions", quantity=3, unit_price=650.00),
        ],
    )


def _write_pdf(invoice: Invoice, pdf_path: Path) -> None:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(15, 15, 15)
    pdf.add_page()
    usable_width = pdf.w - pdf.l_margin - pdf.r_margin
    pdf.set_font("Helvetica", size=14)
    pdf.cell(usable_width, 10, "Bubbola Auto Extract Demo", ln=True)

    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(usable_width, 8, f"Invoice Number: {invoice.document_id}")
    pdf.multi_cell(usable_width, 8, f"Company: {invoice.company_name}")
    pdf.multi_cell(usable_width, 8, f"Company Address: {invoice.company_address}")
    pdf.multi_cell(usable_width, 8, f"Customer: {invoice.customer_name}")
    pdf.multi_cell(usable_width, 8, f"Customer Address: {invoice.customer_address}")
    pdf.multi_cell(usable_width, 8, f"Issue Date: {invoice.issue_date.isoformat()}")
    pdf.multi_cell(usable_width, 8, f"Due Date: {invoice.due_date.isoformat()}")

    pdf.ln(4)
    pdf.set_font("Helvetica", style="B", size=12)
    pdf.cell(usable_width, 8, "Line Items", ln=True)

    pdf.set_font("Helvetica", size=11)
    for idx, item in enumerate(invoice.line_items, start=1):
        pdf.multi_cell(
            usable_width,
            8,
            f"{idx}. {item.description} | Qty: {item.quantity} | Unit Price: ${item.unit_price:.2f}",
        )

    pdf.ln(4)
    pdf.multi_cell(usable_width, 8, f"Notes: {invoice.notes}")
    pdf.multi_cell(usable_width, 8, f"Total: ${invoice.total:.2f}")

    pdf.output(str(pdf_path))


def generate_dataset(output_dir: Path = DEFAULT_OUTPUT_DIR) -> Tuple[Path, Path]:
    """Generate a JSON ground truth file alongside a PDF rendering."""

    invoice = build_sample_invoice()
    output_dir.mkdir(parents=True, exist_ok=True)

    ground_truth_path = output_dir / "ground_truth.json"
    pdf_path = output_dir / "demo_invoice.pdf"

    documents = [invoice.to_ground_truth_document()]
    ground_truth_path.write_text(
        __import__("json").dumps(documents, indent=2),
        encoding="utf-8",
    )

    _write_pdf(invoice, pdf_path)
    return ground_truth_path, pdf_path


def main() -> None:  # pragma: no cover - manual entry point
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory where the JSON and PDF artifacts will be written",
    )
    args = parser.parse_args()
    ground_truth, pdf = generate_dataset(args.output)
    print(f"Wrote {ground_truth}")
    print(f"Wrote {pdf}")


if __name__ == "__main__":
    main()
