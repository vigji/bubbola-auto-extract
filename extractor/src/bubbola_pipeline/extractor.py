"""Parse the synthetic PDF and emit structured predictions."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable, List

from PyPDF2 import PdfReader

from .models import Invoice, LineItem


def _read_pdf_lines(pdf_path: Path) -> List[str]:
    reader = PdfReader(str(pdf_path))
    chunks: List[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        chunks.extend(line.strip() for line in text.splitlines())
    return [line for line in chunks if line]


def _parse_line_item(line: str) -> LineItem:
    match = re.match(
        r"^\d+\. (?P<desc>.+) \| Qty: (?P<qty>\d+) \| Unit Price: \$(?P<price>[0-9.]+)$",
        line,
    )
    if not match:
        raise ValueError(f"Unexpected line item format: {line}")
    return LineItem(
        description=match.group("desc"),
        quantity=int(match.group("qty")),
        unit_price=float(match.group("price")),
    )


def extract_invoice(pdf_path: Path) -> Invoice:
    lines = _read_pdf_lines(pdf_path)

    field_aliases = {
        "Invoice Number": "document_id",
        "Company": "company_name",
        "Company Address": "company_address",
        "Customer": "customer_name",
        "Customer Address": "customer_address",
        "Issue Date": "issue_date",
        "Due Date": "due_date",
    }

    payload = {}
    line_items: List[LineItem] = []
    in_items = False
    for line in lines:
        if line.lower().startswith("line items"):
            in_items = True
            continue
        if line.lower().startswith("notes:"):
            payload["notes"] = line.split(":", 1)[1].strip()
            in_items = False
            continue
        if line.lower().startswith("total:"):
            # trust the structured model to recompute the total
            continue

        if in_items and re.match(r"^\d+\. ", line):
            line_items.append(_parse_line_item(line))
            continue

        if ":" in line and not in_items:
            key, value = [part.strip() for part in line.split(":", 1)]
            alias = field_aliases.get(key)
            if alias:
                payload[alias] = value

    invoice = Invoice(line_items=line_items, **payload)  # type: ignore[arg-type]
    return invoice


def save_predictions(invoice: Invoice, output_path: Path) -> Path:
    document = invoice.to_ground_truth_document()
    output_path.write_text(json.dumps([document], indent=2), encoding="utf-8")
    return output_path


def main() -> None:  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="Path to the PDF produced by the generator")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("tests/generated/predictions.json"),
        help="Where the JSON predictions should be stored",
    )
    args = parser.parse_args()

    invoice = extract_invoice(args.pdf)
    save_predictions(invoice, args.output)
    print(f"Extracted predictions to {args.output}")


if __name__ == "__main__":
    main()
