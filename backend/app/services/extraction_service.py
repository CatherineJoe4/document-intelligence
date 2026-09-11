import json
import logging
import time
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from app.core.config import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()


class ExtractionServiceError(Exception):
    """Raised when the document extraction service cannot process a document."""

    def __init__(
        self,
        code: str = "EXTRACTION_SERVICE_ERROR",
        message: str = (
            "The document could not be extracted. "
            "Please try again later."
        ),
    ):
        self.code = code
        self.message = message
        super().__init__(message)


# ============================================================
# EXTRACTION PROMPT
# ============================================================

EXTRACTION_PROMPT = """
You are a high-accuracy financial document intelligence extraction system.

The user has already selected the document type.
DO NOT classify the document.

Supported document types:
- invoice
- balance_sheet
- profit_and_loss
- cash_flow_statement


============================================================
GENERAL EXTRACTION RULES
============================================================

1. Extract ALL meaningful information visibly present in the document.

2. Extract values exactly from the document.

3. NEVER invent, estimate, guess, infer, or calculate a value that
   is not explicitly supported by visible document content.

4. If a value is not visible or cannot be reliably determined,
   return null.

5. Preserve the original meaning of labels and line items.

6. Extract:
   - document numbers
   - dates
   - company/party names
   - addresses
   - tax identifiers
   - contact details
   - currency
   - units
   - totals
   - taxes
   - discounts
   - payment information
   - financial statement line items
   - comparative periods
   - tables
   - line items
   - other meaningful visible information

7. For every important extracted value, provide:
   - source_text
   - page_number

8. Preserve negative values.
   Parentheses/brackets normally indicate negative values in
   financial statements.

9. Do NOT perform financial validation.

10. Do NOT use arithmetic to invent or repair an extracted value.

11. Return ONLY valid JSON.

12. Do not return Markdown or explanations.


============================================================
VERY IMPORTANT — TABLE STRUCTURE
============================================================

Before extracting values from a table:

1. Carefully inspect the table headers.

2. Determine what each column represents.

3. Map each value to its actual column based on the visible
   table structure.

4. DO NOT assume that:
   - the last number in a row is the total
   - the largest number is the total
   - the number closest to the right edge is the total
   - a percentage is a monetary amount
   - a tax amount is a line total
   - a discount amount is a line total

5. When OCR text appears confusing, use the visual layout,
   column alignment, table headers and surrounding labels to
   determine the meaning of a value.

6. If the column meaning cannot be determined reliably,
   return null for that particular field rather than guessing.

7. Preserve the original table structure whenever possible.


============================================================
INVOICE-SPECIFIC EXTRACTION RULES
============================================================

For invoices, accuracy of line-item columns is extremely important.

For every line item, identify the actual columns used by that
specific invoice.

Possible columns may include:

- item number
- description
- HSN/SAC
- quantity
- unit
- MRP
- rate
- unit price
- discount
- discount rate
- taxable value
- tax rate
- tax amount
- CGST
- SGST
- IGST
- VAT
- GST
- net amount
- gross amount
- line total
- amount

Different invoices can use different column names and layouts.


------------------------------------------------------------
LINE TOTAL RULE
------------------------------------------------------------

"line_total" MUST represent the monetary amount that the invoice
actually reports for that individual line item.

Find it from the table's actual amount/total column.

Examples of valid line-total columns include:

- Amount
- Line Total
- Line Amount
- Extension
- Extension Amount
- Net Amount
- Gross Amount
- Net Worth
- Gross Worth
- Total

BUT:

Do NOT automatically treat any of these as line_total without
checking the table structure.

If the invoice contains both:

- Net Amount
- Gross Amount

determine which one is the actual reported line total based on
the invoice's table structure and summary totals.

If the invoice clearly distinguishes taxable/net amount from
tax-inclusive/gross amount, preserve that distinction.

If there is only one reported line amount, use that amount.


------------------------------------------------------------
CRITICAL — DO NOT CONFUSE OTHER NUMBERS WITH LINE TOTAL
------------------------------------------------------------

The following MUST NOT be placed into "line_total" unless the
table explicitly identifies that column as the line total:

- tax rate such as 5%, 9%, 18%
- discount percentage
- GST percentage
- VAT percentage
- tax amount
- discount amount
- MRP
- unit price
- quantity
- HSN/SAC code
- item number
- arbitrary OCR number
- page number
- invoice number


------------------------------------------------------------
QUANTITY AND UNIT PRICE
------------------------------------------------------------

"quantity" must be the actual quantity column.

"unit_price" must be the actual per-unit selling/rate/price column.

Do not confuse:

- MRP with unit_price
- discount rate with unit_price
- tax rate with unit_price
- taxable value with unit_price
- line total with unit_price


------------------------------------------------------------
TAX RULE
------------------------------------------------------------

The "tax" field inside a line item must contain a MONETARY TAX
AMOUNT only.

Never put:

- 5
- 9
- 12
- 18

into "tax" merely because the document shows 5%, 9%, 12% or 18%.

If the document only shows a tax RATE and does not show the
corresponding line-level tax AMOUNT, use:

"tax": null

Tax rates may still be preserved inside the structured table.


------------------------------------------------------------
IMPORTANT — DO NOT CALCULATE LINE TOTAL
------------------------------------------------------------

Do NOT calculate:

quantity × unit_price

and place the result into line_total.

The purpose of extraction is to capture the amount actually
reported by the document.

For example:

Quantity = 6
Unit price = 7.44
Visible amount = 0.45

Do NOT automatically decide that line_total is 44.64.

First determine what "0.45" represents from the table columns.

If "0.45" cannot reliably be identified as the line amount,
return:

"line_total": null

The financial validation layer will perform arithmetic later.


------------------------------------------------------------
LINE-ITEM SOURCE TEXT
------------------------------------------------------------

For each line item, preserve enough source_text to show the
complete relevant row, including the values surrounding the
extracted fields.

This is important for auditing and debugging extraction.


------------------------------------------------------------
INVOICE TOTALS
------------------------------------------------------------

Extract these when visibly present:

- subtotal
- taxable_amount
- discount
- tax_amount
- CGST
- SGST
- IGST
- VAT
- round_off
- total_amount
- amount_paid
- amount_due
- cash_paid
- change

If the invoice says:

"GST included"
"Tax included"
"Total inclusive of GST"
"including GST"
or equivalent wording,

preserve that wording in source_text and/or metadata where
possible.

Do NOT add tax twice during extraction.


============================================================
FINANCIAL STATEMENT RULES
============================================================

For:

balance_sheet
profit_and_loss
cash_flow_statement

extract EVERY meaningful visible financial line item.

Do not restrict extraction to a predefined list.

Preserve:

- exact labels
- values
- comparative periods
- units
- currency
- subtotals
- totals
- negative values
- section headings

For comparative financial statements, maintain the correct
relationship between each row and each period column.

For example:

Particulars | 2025 | 2024

must not become:

Particulars | 2025
with the 2024 values lost.

Do not calculate totals.


============================================================
OUTPUT STRUCTURE
============================================================

Return exactly this general structure:

{
  "document_type": "<provided document type>",

  "fields": {
    "<field_name>": {
      "value": "<value or null>",
      "source_text": "<visible supporting text or null>",
      "page_number": <number or null>
    }
  },

  "tables": [
    {
      "title": "<table title or null>",
      "headers": [
        "..."
      ],
      "rows": [
        [
          "..."
        ]
      ],
      "page_number": <number or null>
    }
  ],

  "line_items": [
    {
      "description": "<description or null>",
      "quantity": <number or null>,
      "unit_price": <number or null>,
      "line_total": <number or null>,
      "tax": <number or null>,
      "currency": "<currency or null>",
      "source_text": "<visible supporting row text or null>",
      "page_number": <number or null>
    }
  ]
}

For non-invoice documents:

"line_items": []

Do not add fields that are not supported by visible document
content.
"""


# ============================================================
# MIME TYPE
# ============================================================

def _get_mime_type(file_path: str) -> str:
    """Return the MIME type supported by Gemini."""

    suffix = Path(file_path).suffix.lower()

    mime_types = {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
    }

    if suffix not in mime_types:
        raise ValueError(
            f"Unsupported extraction file type: {suffix}"
        )

    return mime_types[suffix]


# ============================================================
# JSON PARSING
# ============================================================

def _parse_json_response(response_text: str) -> dict:
    """Convert Gemini's JSON response into a Python dictionary."""

    text = response_text.strip()

    # Remove accidental Markdown code fences.
    if text.startswith("```json"):
        text = text[7:]

    elif text.startswith("```"):
        text = text[3:]

    if text.endswith("```"):
        text = text[:-3]

    text = text.strip()

    try:
        result = json.loads(text)

    except json.JSONDecodeError as exc:
        logger.error(
            "Gemini returned invalid JSON: %s",
            exc,
        )

        raise ValueError(
            "AI extraction returned invalid JSON."
        ) from exc

    if not isinstance(result, dict):
        raise ValueError(
            "AI extraction returned an unexpected JSON structure."
        )

    return result


# ============================================================
# EXTRACTION RESULT NORMALIZATION
# ============================================================

def _normalize_result(
    result: dict,
    document_type: str,
) -> dict:
    """
    Ensure the extraction response always has the expected
    top-level structure.
    """

    if not isinstance(result, dict):
        raise ValueError(
            "AI extraction returned an invalid object."
        )

    result["document_type"] = document_type

    if not isinstance(result.get("fields"), dict):
        result["fields"] = {}

    if not isinstance(result.get("tables"), list):
        result["tables"] = []

    if not isinstance(result.get("line_items"), list):
        result["line_items"] = []

    return result


# ============================================================
# MAIN EXTRACTION
# ============================================================

def extract_document(
    file_path: str,
    document_type: str,
) -> dict:
    """
    Extract structured information from a PDF/JPG/PNG document
    using Gemini.

    The document type supplied by the frontend/API remains
    authoritative.
    """

    mime_type = _get_mime_type(file_path)

    with open(file_path, "rb") as file:
        file_bytes = file.read()

    if not file_bytes:
        raise ValueError(
            "Cannot extract from an empty file."
        )

    client = genai.Client(
        api_key=settings.gemini_api_key,
    )

    prompt = (
        EXTRACTION_PROMPT
        + "\n\n"
        + "The selected document type is: "
        + document_type
        + "\n\n"
        + "Use the selected document type exactly as provided."
    )

    logger.info(
        "Starting Gemini extraction | type=%s | mime=%s",
        document_type,
        mime_type,
    )

    # --------------------------------------------------------
    # Limited retry for temporary Gemini 503 errors.
    #
    # Do NOT retry quota errors such as 429 here.
    # --------------------------------------------------------

    max_attempts = 2

    for attempt in range(1, max_attempts + 1):

        try:

            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=[
                    prompt,
                    types.Part.from_bytes(
                        data=file_bytes,
                        mime_type=mime_type,
                    ),
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0,
                ),
            )

            break

        except Exception as exc:

            error_text = str(exc)

            is_temporary_503 = (
                "503" in error_text
                or "UNAVAILABLE" in error_text
                or "high demand" in error_text.lower()
            )

            # Never repeatedly retry quota exhaustion.
            is_quota_error = (
                "429" in error_text
                or "RESOURCE_EXHAUSTED" in error_text
                or "quota" in error_text.lower()
            )

            logger.exception(
                "Gemini extraction failed | "
                "attempt=%s/%s | "
                "error_type=%s",
                attempt,
                max_attempts,
                type(exc).__name__,
            )

            if (
                is_temporary_503
                and not is_quota_error
                and attempt < max_attempts
            ):
                wait_seconds = 3 * attempt

                logger.warning(
                    "Temporary Gemini availability issue. "
                    "Retrying in %s seconds.",
                    wait_seconds,
                )

                time.sleep(wait_seconds)
                continue

            raise ExtractionServiceError() from exc

    # --------------------------------------------------------
    # Validate response
    # --------------------------------------------------------

    if not response.text:
        raise ValueError(
            "Gemini returned an empty extraction response."
        )

    result = _parse_json_response(
        response.text
    )

    result = _normalize_result(
        result,
        document_type,
    )

    logger.info(
        "Gemini extraction completed | type=%s",
        document_type,
    )

    return result