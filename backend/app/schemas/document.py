from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict


class DocumentType(str, Enum):
    INVOICE = "invoice"
    BALANCE_SHEET = "balance_sheet"
    PROFIT_AND_LOSS = "profit_and_loss"
    CASH_FLOW_STATEMENT = "cash_flow_statement"


class ProcessingStatus(str, Enum):
    PASS = "PASS"
    FAILED = "FAILED"


class ValidationStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ValidationResult(BaseModel):
    check: str
    input_values: dict[str, Any]
    calculated_value: float | None = None
    reported_value: float | None = None
    variance: float | None = None
    status: ValidationStatus


class DocumentResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_name: str
    document_type: DocumentType
    status: ProcessingStatus

    file_validation: dict[str, Any]

    extracted_data: dict[str, Any]

    financial_validations: list[ValidationResult]

    metadata: dict[str, Any]

    created_at: datetime | None = None
    updated_at: datetime | None = None