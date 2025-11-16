"""Pydantic data models shared across generators and extractors."""

from __future__ import annotations

from datetime import date
from typing import List

from pydantic import BaseModel, Field, validator


class LineItem(BaseModel):
    description: str = Field(..., description="Short explanation of the service")
    quantity: int = Field(..., ge=1, description="Units billed")
    unit_price: float = Field(..., ge=0.0, description="Price per unit")

    @property
    def total(self) -> float:
        return round(self.quantity * self.unit_price, 2)


class Invoice(BaseModel):
    """Small invoice-like payload used as structured ground truth."""

    document_id: str = Field(..., description="Stable identifier for the PDF")
    company_name: str
    company_address: str
    customer_name: str
    customer_address: str
    issue_date: date
    due_date: date
    line_items: List[LineItem]
    notes: str = ""

    @validator("line_items")
    def ensure_line_items(cls, value: List[LineItem]) -> List[LineItem]:
        if not value:
            raise ValueError("At least one line item is required")
        return value

    @property
    def subtotal(self) -> float:
        return round(sum(item.total for item in self.line_items), 2)

    @property
    def total(self) -> float:
        # Tax-free dataset, but left here for parity with typical invoices.
        return self.subtotal

    def to_ground_truth_document(self) -> dict:
        """Adapter to match the evaluator's JSON schema."""

        return {
            "document_id": self.document_id,
            "fields": {
                "company_name": self.company_name,
                "company_address": self.company_address,
                "customer_name": self.customer_name,
                "customer_address": self.customer_address,
                "issue_date": self.issue_date.isoformat(),
                "due_date": self.due_date.isoformat(),
                "notes": self.notes,
                "line_items": [
                    {
                        "description": item.description,
                        "quantity": item.quantity,
                        "unit_price": item.unit_price,
                        "total": item.total,
                    }
                    for item in self.line_items
                ],
                "total": self.total,
            },
        }
