

from __future__ import annotations

import re
from typing import Any


# ============================================================
# GENERAL HELPERS
# ============================================================

NUMBER_PATTERN = re.compile(
    r"""
    (?P<number>
        [(\[]?\s*
        [-+]?
        (?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)
        \s*[)\]]?
    )
    """,
    re.VERBOSE,
)


def _to_number(value: Any) -> float | None:
    """
    Convert an extracted value into a number.

    Supports:
    - 1234
    - 1,234.50
    - (1,234.50)
    - [1,234.50]
    - -1234.50

    Does not try to 'repair' ambiguous OCR numbers.
    """

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()

    if not text:
        return None

    # Common representations of missing values.
    if text.lower() in {
        "-",
        "—",
        "–",
        "na",
        "n/a",
        "nil",
        "none",
        "null",
        "",
    }:
        return None

    # Remove currency symbols and spaces.
    cleaned = (
        text.replace(",", "")
        .replace("₹", "")
        .replace("$", "")
        .replace("€", "")
        .replace("£", "")
        .replace("RM", "")
        .replace("CAD", "")
        .replace("USD", "")
        .replace("INR", "")
        .strip()
    )

    # Parentheses/brackets indicate negative values.
    negative = False

    if (
        (cleaned.startswith("(") and cleaned.endswith(")"))
        or (cleaned.startswith("[") and cleaned.endswith("]"))
    ):
        negative = True
        cleaned = cleaned[1:-1].strip()

    try:
        number = float(cleaned)

        if negative:
            number = -abs(number)

        return number

    except (ValueError, TypeError):
        return None


def _normalize_label(label: Any) -> str:
    """
    Normalize a financial statement label for semantic matching.

    Examples:

    'Provisions and contingencies [Refer Schedule 18 (12)]'
        ->
    'provisions and contingencies'

    'Net cash flow (used in) / from operating activities'
        ->
    'net cash flow used in from operating activities'
    """

    if label is None:
        return ""

    text = str(label).lower()

    # Remove references such as:
    # [Refer Schedule 18 (12)]
    # (Refer Note 4)
    text = re.sub(r"\[[^\]]*\]", " ", text)
    text = re.sub(r"\([^)]*refer[^)]*\)", " ", text)

    # Standardize symbols.
    text = text.replace("&", " and ")
    text = text.replace("/", " ")
    text = text.replace("-", " ")
    text = text.replace("_", " ")

    # Remove punctuation.
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    # Normalize common plural forms.
    text = re.sub(r"\bexpenses\b", "expense", text)
    text = re.sub(r"\bprovisions\b", "provision", text)
    text = re.sub(r"\bminorities\b", "minority", text)
    text = re.sub(r"\bprofits\b", "profit", text)

    # Collapse whitespace.
    text = re.sub(r"\s+", " ", text).strip()

    return text


def _tokens(label: Any) -> set[str]:
    return set(_normalize_label(label).split())


def _contains_all(label: Any, *words: str) -> bool:
    normalized = _normalize_label(label)

    return all(word.lower() in normalized for word in words)


def _contains_any(label: Any, *words: str) -> bool:
    normalized = _normalize_label(label)

    return any(word.lower() in normalized for word in words)


def _is_header_row(row: list[Any]) -> bool:
    """
    Detect rows that are section/header rows rather than financial values.
    """

    if not row:
        return True

    label = _normalize_label(row[0])

    if not label:
        return True

    # A row containing only text and no useful numbers is often a section.
    numeric_values = [_to_number(value) for value in row[1:]]

    return all(value is None for value in numeric_values)


def _row_label(row: list[Any]) -> str:
    if not row:
        return ""

    return str(row[0] or "").strip()


def _row_value(
    row: list[Any],
    column_index: int,
) -> float | None:

    if column_index >= len(row):
        return None

    return _to_number(row[column_index])


def _validation(
    check: str,
    input_values: dict[str, Any],
    calculated_value: float | None,
    reported_value: float | None,
    tolerance: float = 0.01,
) -> dict[str, Any]:
    """
    Create a standard validation result.
    """

    if calculated_value is None or reported_value is None:

        return {
            "check": check,
            "input_values": input_values,
            "calculated_value": calculated_value,
            "reported_value": reported_value,
            "variance": None,
            "status": "NOT_APPLICABLE",
        }

    variance = calculated_value - reported_value

    status = (
        "PASS"
        if abs(variance) <= tolerance
        else "FAIL"
    )

    return {
        "check": check,
        "input_values": input_values,
        "calculated_value": calculated_value,
        "reported_value": reported_value,
        "variance": variance,
        "status": status,
    }


# ============================================================
# FIELD HELPERS
# ============================================================

def _field_value(
    fields: dict[str, Any],
    *possible_names: str,
) -> float | None:
    """
    Find a numeric field using normalized key matching.

    Supports both:
        {"total_amount": 108.50}

    and:
        {
            "total_amount": {
                "value": 108.50,
                "source_text": "Total Sales RM 108.50"
            }
        }
    """

    if not fields:
        return None

    normalized_fields = {
        _normalize_label(key): value
        for key, value in fields.items()
    }

    for name in possible_names:
        normalized_name = _normalize_label(name)

        if normalized_name not in normalized_fields:
            continue

        value = normalized_fields[normalized_name]

        # Gemini structured field
        if isinstance(value, dict):
            value = value.get("value")

        return _to_number(value)

    return None
def _field_raw_value(
    fields: dict[str, Any],
    *possible_names: str,
) -> Any:
    """
    Return the raw value of a field.
    """

    if not fields:
        return None

    normalized_fields = {
        _normalize_label(key): value
        for key, value in fields.items()
    }

    for name in possible_names:

        normalized_name = _normalize_label(name)

        if normalized_name in normalized_fields:

            value = normalized_fields[normalized_name]

            if isinstance(value, dict):
                return value.get("value")

            return value

    return None


# ============================================================
# TABLE HELPERS
# ============================================================

def _get_tables(extracted_data: dict[str, Any]) -> list[dict[str, Any]]:
    tables = extracted_data.get("tables", [])

    if not isinstance(tables, list):
        return []

    return [
        table
        for table in tables
        if isinstance(table, dict)
    ]


def _get_rows(table: dict[str, Any]) -> list[list[Any]]:
    rows = table.get("rows", [])

    if not isinstance(rows, list):
        return []

    return [
        row
        for row in rows
        if isinstance(row, list)
    ]


def _get_headers(table: dict[str, Any]) -> list[Any]:
    headers = table.get("headers", [])

    if not isinstance(headers, list):
        return []

    return headers


def _find_period_columns(
    table: dict[str, Any],
) -> list[tuple[int, str]]:
    """
    Detect columns representing financial periods.

    Examples:
    - Year ended March 31, 2022
    - Year ended March 31, 2021
    - As at March 31, 2022
    - 2022
    - 2021
    """

    headers = _get_headers(table)

    period_columns: list[tuple[int, str]] = []

    for index, header in enumerate(headers):

        text = str(header or "").strip()

        normalized = _normalize_label(text)

        if not normalized:
            continue

        is_period = bool(
            re.search(r"\b20\d{2}\b", text)
            or "year ended" in normalized
            or "as at" in normalized
            or "period ended" in normalized
            or "for the year" in normalized
            or "financial year" in normalized
        )

        if is_period:
            period_columns.append((index, text))

    if period_columns:
        return period_columns

    # Fallback:
    # Look at numeric density in columns.
    rows = _get_rows(table)

    if not rows:
        return []

    max_columns = max(len(row) for row in rows)

    candidates: list[tuple[int, str]] = []

    for column_index in range(max_columns):

        numeric_count = 0
        non_empty_count = 0

        for row in rows:

            if column_index >= len(row):
                continue

            value = row[column_index]

            if value in (None, ""):
                continue

            non_empty_count += 1

            if _to_number(value) is not None:
                numeric_count += 1

        if (
            non_empty_count > 0
            and numeric_count >= 2
            and numeric_count / non_empty_count >= 0.5
        ):
            candidates.append(
                (
                    column_index,
                    f"Period {len(candidates) + 1}",
                )
            )

    return candidates


def _find_row(
    rows: list[list[Any]],
    matcher,
    start_index: int = 0,
    end_index: int | None = None,
) -> tuple[int, list[Any]] | None:

    if end_index is None:
        end_index = len(rows)

    for index in range(start_index, min(end_index, len(rows))):

        row = rows[index]

        if not row:
            continue

        label = _row_label(row)

        if matcher(label):
            return index, row

    return None


def _find_concept_row(
    rows: list[list[Any]],
    concept: str,
    start_index: int = 0,
    end_index: int | None = None,
) -> tuple[int, list[Any]] | None:
    """
    General semantic concept recognition.
    """

    if concept == "interest_earned":

        matcher = lambda label: (
            _contains_all(label, "interest", "earned")
            and not _contains_any(label, "expense", "expended")
        )

    elif concept == "other_income":

        matcher = lambda label: (
            _contains_all(label, "other", "income")
            and not _contains_any(label, "expense")
        )

    elif concept == "total_income":

        matcher = lambda label: (
            _contains_all(label, "total", "income")
            or label.strip().lower() == "total"
        )

    elif concept == "interest_expended":

        matcher = lambda label: (
            _contains_all(label, "interest")
            and _contains_any(
                label,
                "expended",
                "expense",
            )
        )

    elif concept == "operating_expenses":

        matcher = lambda label: (
            _contains_all(label, "operating", "expense")
        )

    elif concept == "provisions_contingencies":

        matcher = lambda label: (
            _contains_any(
                label,
                "contingenc",
            )
            and _contains_any(
                label,
                "provision",
                "contingenc",
            )
        )

    elif concept == "total_expenditure":

        matcher = lambda label: (
            _contains_all(label, "total", "expenditure")
            or _contains_all(label, "total", "expense")
            or label.strip().lower() == "total"
        )

    elif concept == "profit_before_minority":

        matcher = lambda label: (
            (
                _contains_all(
                    label,
                    "profit",
                    "before",
                    "minority",
                )
            )
            or (
                _contains_all(
                    label,
                    "net",
                    "profit",
                    "before",
                )
                and _contains_any(
                    label,
                    "minority",
                    "minorities",
                )
            )
        )

    elif concept == "minority_interest":

        matcher = lambda label: (
            _contains_all(label, "minority", "interest")
            and not _contains_any(
                label,
                "transfer",
                "opening",
                "adjustment",
            )
        )

    elif concept == "share_in_associates":

        matcher = lambda label: (
            _contains_all(
                label,
                "share",
                "profit",
                "associate",
            )
        )

    elif concept == "group_attributable_profit":

        matcher = lambda label: (
            _contains_all(
                label,
                "attributable",
                "group",
            )
            and _contains_any(
                label,
                "profit",
                "net",
            )
        )

    elif concept == "brought_forward_profit":

        matcher = lambda label: (
            _contains_any(
                label,
                "brought forward",
                "brought",
            )
            and _contains_any(
                label,
                "profit",
            )
        )

    elif concept == "total_profit":

        matcher = lambda label: (
            _contains_all(label, "total", "profit")
            or label.strip().lower() == "total"
        )

    elif concept == "total_appropriations":

        matcher = lambda label: (
            _contains_all(label, "total", "appropriation")
        )

    else:
        return None

    return _find_row(
        rows,
        matcher,
        start_index,
        end_index,
    )


# ============================================================
# INVOICE VALIDATION
# ============================================================

def _invoice_raw_field(
    fields: dict[str, Any],
    *possible_names: str,
) -> Any:
    """Return an extracted invoice field value without converting it."""
    return _field_raw_value(fields, *possible_names)


def _invoice_number_field(
    fields: dict[str, Any],
    *possible_names: str,
) -> float | None:
    """Return an extracted invoice field as a number."""
    return _field_value(fields, *possible_names)


def _invoice_line_value(
    item: dict[str, Any],
    *possible_names: str,
) -> Any:
    """Read a line-item value, supporting nested Gemini field objects."""
    if not isinstance(item, dict):
        return None

    normalized = {
        _normalize_label(key): value
        for key, value in item.items()
    }

    for name in possible_names:
        key = _normalize_label(name)
        if key not in normalized:
            continue

        value = normalized[key]
        if isinstance(value, dict):
            return value.get("value")
        return value

    return None


def _invoice_line_amount(item: dict[str, Any]) -> float | None:
    """
    Return the actual reported monetary line amount.

    Extraction must identify the reported amount; this validator does not
    manufacture a line total from unrelated numbers.
    """
    return _to_number(
        _invoice_line_value(
            item,
            "line_total",
            "line amount",
            "amount",
            "net amount",
            "net worth",
            "gross worth",
            "total",
        )
    )


def _invoice_line_tax(item: dict[str, Any]) -> float | None:
    """Return a reported monetary tax amount for a line, if present."""
    return _to_number(
        _invoice_line_value(
            item,
            "tax_amount",
            "line tax",
            "tax",
            "vat amount",
            "gst amount",
        )
    )


def _invoice_text_indicates_tax_included(
    extracted_data: dict[str, Any],
) -> bool:
    """Detect explicit wording indicating that tax is included in a total."""
    fields = extracted_data.get("fields", {})
    texts: list[str] = []

    if isinstance(fields, dict):
        for key in ("total_amount", "tax_amount", "taxable_amount", "subtotal"):
            value = fields.get(key)
            if isinstance(value, dict):
                source = value.get("source_text")
                if source:
                    texts.append(str(source))
            elif value is not None:
                texts.append(f"{key} {value}")

    for table in _get_tables(extracted_data):
        headers = _get_headers(table)
        texts.extend(str(header) for header in headers if header is not None)

        for row in _get_rows(table):
            texts.extend(str(value) for value in row if value is not None)

    combined = _normalize_label(" ".join(texts))

    return any(
        phrase in combined
        for phrase in (
            "inclusive gst",
            "inclusive tax",
            "tax included",
            "gst included",
            "vat included",
            "including gst",
            "including tax",
        )
    )


def _extract_invoice_tax_from_tables(
    extracted_data: dict[str, Any],
) -> tuple[float | None, float | None]:
    """
    Extract taxable amount and monetary tax amount from invoice tax-summary
    tables. Tax percentages are never returned as tax amounts.
    """
    taxable: float | None = None
    tax_amount: float | None = None

    taxable_labels = (
        "taxable amount",
        "taxable",
        "net amount",
        "taxable value",
        "taxable sales",
    )
    tax_labels = (
        "tax amount",
        "tax",
        "gst amount",
        "vat amount",
        "sales tax amount",
    )

    for table in _get_tables(extracted_data):
        headers = [str(h or "") for h in _get_headers(table)]
        normalized_headers = [_normalize_label(h) for h in headers]

        for row in _get_rows(table):
            if not row:
                continue

            label_text = _normalize_label(" ".join(
                str(v or "") for v in row[: min(2, len(row))]
            ))

            # Prefer explicit row labels.
            for idx, value in enumerate(row):
                label = _normalize_label(headers[idx]) if idx < len(headers) else ""
                cell_text = _normalize_label(str(value or ""))

                if taxable is None and (
                    any(term in label for term in taxable_labels)
                    or any(term in label_text for term in taxable_labels)
                    or any(term in cell_text for term in taxable_labels)
                ):
                    numeric_candidates = [
                        _to_number(v)
                        for j, v in enumerate(row)
                        if j != idx
                    ]
                    numeric_candidates = [
                        n for n in numeric_candidates if n is not None
                    ]
                    if numeric_candidates:
                        taxable = numeric_candidates[-1]

                if tax_amount is None and (
                    any(term in label for term in tax_labels)
                    or any(term in label_text for term in tax_labels)
                ):
                    numeric_candidates = [
                        _to_number(v)
                        for j, v in enumerate(row)
                        if j != idx
                    ]
                    numeric_candidates = [
                        n for n in numeric_candidates if n is not None
                    ]
                    if numeric_candidates:
                        # In a tax-summary row, the monetary tax value is
                        # normally the last numeric value, while a percentage
                        # such as 6% must not be treated as the tax amount.
                        tax_amount = numeric_candidates[-1]

    return taxable, tax_amount


def validate_invoice(
    extracted_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Validate invoice arithmetic using only values explicitly extracted
    from the document.

    Missing or unreadable inputs produce NOT_APPLICABLE.
    No values are invented or silently corrected.
    """
    validations: list[dict[str, Any]] = []

    fields = extracted_data.get("fields", {})
    if not isinstance(fields, dict):
        fields = {}

    # ------------------------------------------------------------
    # Header-level monetary fields
    # ------------------------------------------------------------
    subtotal = _invoice_number_field(
        fields,
        "subtotal",
        "sub total",
        "net subtotal",
    )
    discount = _invoice_number_field(
        fields,
        "discount",
        "discount amount",
    )
    tax_amount = _invoice_number_field(
        fields,
        "tax_amount",
        "tax amount",
        "gst amount",
        "vat amount",
        "sales tax amount",
    )
    taxable_amount = _invoice_number_field(
        fields,
        "taxable_amount",
        "taxable amount",
        "taxable value",
        "net taxable amount",
    )
    total_amount = _invoice_number_field(
        fields,
        "total_amount",
        "total",
        "grand total",
        "amount due",
        "total amount",
        "total sales",
        "total sales inclusive gst",
    )
    cash_paid = _invoice_number_field(
        fields,
        "cash_paid",
        "cash",
        "cash received",
        "amount paid",
        "paid",
    )
    change = _invoice_number_field(
        fields,
        "change",
        "change due",
        "balance change",
    )
    roundoff = _invoice_number_field(
        fields,
        "round_off",
        "rounding",
        "rounding adjustment",
        "round off",
    )

    # If tax was not available in fields, use an explicit tax-summary table.
    table_taxable, table_tax = _extract_invoice_tax_from_tables(extracted_data)
    if taxable_amount is None:
        taxable_amount = table_taxable
    if tax_amount is None:
        tax_amount = table_tax

    line_items = extracted_data.get("line_items", [])
    if not isinstance(line_items, list):
        line_items = []

    # ------------------------------------------------------------
    # 1. Quantity x Unit Price = Reported Line Total
    # ------------------------------------------------------------
    line_amounts: list[float] = []
    line_amount_inputs: dict[str, Any] = {}

    for index, item in enumerate(line_items, start=1):
        if not isinstance(item, dict):
            continue

        description = _invoice_line_value(
            item,
            "description",
            "item",
            "product",
            "service",
            "name",
        )

        quantity = _to_number(
            _invoice_line_value(
                item,
                "quantity",
                "qty",
            )
        )
        unit_price = _to_number(
            _invoice_line_value(
                item,
                "unit_price",
                "unit price",
                "rate",
                "price",
            )
        )
        reported_line_total = _invoice_line_amount(item)
        line_tax = _invoice_line_tax(item)

        # When an actual line tax amount is explicitly present, compare the
        # base amount + line tax to the reported line amount if possible.
        line_base = None
        if quantity is not None and unit_price is not None:
            line_base = quantity * unit_price

        if line_base is not None and reported_line_total is not None:
            if line_tax is not None:
                calculated_line_total = line_base + line_tax
                check_name = (
                    f"Line {index}: Quantity × Unit Price + Line Tax "
                    f"= Reported Line Total"
                )
                inputs = {
                    "line": index,
                    "description": description,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "line_tax": line_tax,
                }
            else:
                calculated_line_total = line_base
                check_name = (
                    f"Line {index}: Quantity × Unit Price "
                    f"= Reported Line Total"
                )
                inputs = {
                    "line": index,
                    "description": description,
                    "quantity": quantity,
                    "unit_price": unit_price,
                }

            validations.append(
                _validation(
                    check=check_name,
                    input_values=inputs,
                    calculated_value=calculated_line_total,
                    reported_value=reported_line_total,
                )
            )

        if reported_line_total is not None:
            line_amounts.append(reported_line_total)
            line_amount_inputs[f"line_{index}"] = reported_line_total

    # ------------------------------------------------------------
    # 2. Sum of reported line amounts = subtotal
    # ------------------------------------------------------------
    calculated_line_sum = sum(line_amounts) if line_amounts else None

    validations.append(
        _validation(
            check="Sum of Reported Line Amounts = Subtotal",
            input_values={
                "line_amounts": line_amount_inputs,
                "subtotal": subtotal,
            },
            calculated_value=calculated_line_sum,
            reported_value=subtotal,
        )
    )

    # ------------------------------------------------------------
    # 3. Tax-inclusive relationship
    # ------------------------------------------------------------
    tax_inclusive = _invoice_text_indicates_tax_included(extracted_data)

    if (
        taxable_amount is not None
        and tax_amount is not None
        and total_amount is not None
        and tax_inclusive
    ):
        validations.append(
            _validation(
                check="Taxable Amount + Tax Amount = Tax-Inclusive Total",
                input_values={
                    "taxable_amount": taxable_amount,
                    "tax_amount": tax_amount,
                    "total_amount": total_amount,
                    "tax_inclusive": True,
                },
                calculated_value=taxable_amount + tax_amount,
                reported_value=total_amount,
            )
        )
    else:
        # If the document does not explicitly indicate tax-inclusive wording,
        # validate the standard subtotal/discount/tax/rounding relationship
        # only when the necessary inputs are actually present.
        calculated_total = None

        if subtotal is not None and tax_amount is not None:
            calculated_total = subtotal
            if discount is not None:
                calculated_total -= discount
            calculated_total += tax_amount
            if roundoff is not None:
                calculated_total += roundoff

        validations.append(
            _validation(
                check=(
                    "Subtotal - Discount + Tax + Round-off "
                    "= Total Amount"
                ),
                input_values={
                    "subtotal": subtotal,
                    "discount": discount,
                    "tax_amount": tax_amount,
                    "round_off": roundoff,
                    "total_amount": total_amount,
                },
                calculated_value=calculated_total,
                reported_value=total_amount,
            )
        )

    # ------------------------------------------------------------
    # 4. Cash paid - total = change
    # ------------------------------------------------------------
    validations.append(
        _validation(
            check="Cash Paid - Total Amount = Change",
            input_values={
                "cash_paid": cash_paid,
                "total_amount": total_amount,
                "change": change,
            },
            calculated_value=(
                cash_paid - total_amount
                if cash_paid is not None and total_amount is not None
                else None
            ),
            reported_value=change,
        )
    )

    return validations

# ============================================================
# BALANCE SHEET
# ============================================================

# ============================================================
# BALANCE SHEET
# ============================================================

def _find_section_start(
    rows: list[list[Any]],
    start: int,
    keywords: tuple[str, ...],
) -> int | None:
    """
    Find the first row whose label contains all supplied keywords.
    """
    for index in range(start, len(rows)):
        label = _normalize_label(_row_label(rows[index]))

        if all(keyword.lower() in label for keyword in keywords):
            return index

    return None


def _find_total_row(
    rows: list[list[Any]],
    start: int,
    end: int,
    keywords: tuple[str, ...] = (),
) -> tuple[int, list[Any]] | None:
    """
    Find an explicit total row within a section.

    Prefer rows containing both 'total' and the requested keywords.
    Then fall back to a row labelled simply 'total'.
    """

    end = min(end, len(rows))

    # First: explicit total containing requested keywords.
    for index in range(start, end):
        label = _normalize_label(_row_label(rows[index]))

        if "total" not in label:
            continue

        if keywords and all(
            keyword.lower() in label
            for keyword in keywords
        ):
            return index, rows[index]

    # Second: literal "total".
    for index in range(start, end):
        label = _normalize_label(_row_label(rows[index]))

        if label == "total":
            return index, rows[index]

    return None


def _collect_section_components(
    rows: list[list[Any]],
    start: int,
    end: int,
    column_index: int,
) -> tuple[list[str], list[float]]:
    """
    Collect meaningful financial components from a section.

    Header rows, blank rows and total/subtotal rows are excluded.
    """

    labels: list[str] = []
    values: list[float] = []

    for row in rows[start:end]:

        if _is_header_row(row):
            continue

        label = _row_label(row)
        normalized = _normalize_label(label)

        if not normalized:
            continue

        # Do not double-count reported totals/subtotals.
        if (
            "total" in normalized
            or "subtotal" in normalized
        ):
            continue

        value = _row_value(row, column_index)

        if value is None:
            continue

        labels.append(label)
        values.append(value)

    return labels, values


def validate_balance_sheet(
    extracted_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Validate Balance Sheet financial relationships.

    Required checks:

    1. Total Capital & Liabilities = Total Assets
    2. Sum of Capital & Liability components = Total Capital & Liabilities
    3. Sum of Asset components = Total Assets

    Every available comparative period is validated independently.

    Missing required values produce NOT_APPLICABLE rather than
    inventing or inferring values.
    """

    validations: list[dict[str, Any]] = []

    tables = _get_tables(extracted_data)

    if not tables:
        return validations

    for table in tables:

        rows = _get_rows(table)

        if not rows:
            continue

        period_columns = _find_period_columns(table)

        if not period_columns:
            continue

        # --------------------------------------------------------
        # Find Capital & Liabilities section
        # --------------------------------------------------------

        capital_start = _find_section_start(
            rows,
            0,
            ("capital", "liabilit"),
        )

        if capital_start is None:
            continue

        # --------------------------------------------------------
        # Find Assets section
        # --------------------------------------------------------

        assets_start = _find_section_start(
            rows,
            capital_start + 1,
            ("asset",),
        )

        if assets_start is None:
            continue

        # --------------------------------------------------------
        # Find Capital & Liabilities total
        # --------------------------------------------------------

        capital_total = _find_total_row(
            rows,
            capital_start + 1,
            assets_start,
            ("capital", "liabilit"),
        )

        if capital_total is None:
            capital_total = _find_total_row(
                rows,
                capital_start + 1,
                assets_start,
            )

        # --------------------------------------------------------
        # Find Assets total
        # --------------------------------------------------------

        assets_total = _find_total_row(
            rows,
            assets_start + 1,
            len(rows),
            ("asset",),
        )

        if assets_total is None:
            assets_total = _find_total_row(
                rows,
                assets_start + 1,
                len(rows),
            )

        capital_index = (
            capital_total[0]
            if capital_total is not None
            else assets_start
        )

        assets_index = (
            assets_total[0]
            if assets_total is not None
            else len(rows)
        )

        capital_row = (
            capital_total[1]
            if capital_total is not None
            else None
        )

        assets_row = (
            assets_total[1]
            if assets_total is not None
            else None
        )

        # --------------------------------------------------------
        # Validate every comparative period independently
        # --------------------------------------------------------

        for column_index, period in period_columns:

            # ====================================================
            # 1. TOTAL CAPITAL & LIABILITIES = TOTAL ASSETS
            # ====================================================

            total_capital_liabilities = (
                _row_value(
                    capital_row,
                    column_index,
                )
                if capital_row is not None
                else None
            )

            total_assets = (
                _row_value(
                    assets_row,
                    column_index,
                )
                if assets_row is not None
                else None
            )

            validations.append(
                _validation(
                    check=(
                        "Total Capital & Liabilities "
                        "= Total Assets"
                    ),
                    input_values={
                        "period": period,
                        "total_capital_and_liabilities":
                            total_capital_liabilities,
                        "total_assets":
                            total_assets,
                    },
                    calculated_value=(
                        total_capital_liabilities
                    ),
                    reported_value=total_assets,
                )
            )

            # ====================================================
            # 2. CAPITAL & LIABILITIES COMPONENT SUM
            # ====================================================

            (
                capital_component_labels,
                capital_component_values,
            ) = _collect_section_components(
                rows,
                capital_start + 1,
                capital_index,
                column_index,
            )

            calculated_capital_components = (
                sum(capital_component_values)
                if capital_component_values
                else None
            )

            validations.append(
                _validation(
                    check=(
                        "Sum of Capital & Liabilities "
                        "components = Total Capital & Liabilities"
                    ),
                    input_values={
                        "period": period,
                        "components": dict(
                            zip(
                                capital_component_labels,
                                capital_component_values,
                            )
                        ),
                        "total_capital_and_liabilities":
                            total_capital_liabilities,
                    },
                    calculated_value=(
                        calculated_capital_components
                    ),
                    reported_value=(
                        total_capital_liabilities
                    ),
                )
            )

            # ====================================================
            # 3. ASSET COMPONENT SUM
            # ====================================================

            (
                asset_component_labels,
                asset_component_values,
            ) = _collect_section_components(
                rows,
                assets_start + 1,
                assets_index,
                column_index,
            )

            calculated_asset_components = (
                sum(asset_component_values)
                if asset_component_values
                else None
            )

            validations.append(
                _validation(
                    check=(
                        "Sum of Assets components "
                        "= Total Assets"
                    ),
                    input_values={
                        "period": period,
                        "components": dict(
                            zip(
                                asset_component_labels,
                                asset_component_values,
                            )
                        ),
                        "total_assets": total_assets,
                    },
                    calculated_value=(
                        calculated_asset_components
                    ),
                    reported_value=total_assets,
                )
            )

    return validations
# ============================================================
# PROFIT & LOSS
# ============================================================

def _find_pl_section(
    rows: list[list[Any]],
    keyword: str,
) -> int | None:

    for index, row in enumerate(rows):

        label = _normalize_label(
            _row_label(row)
        )

        if keyword in label:

            # Avoid ordinary financial rows.
            if (
                len(label.split()) <= 8
                or label.startswith(("i ", "ii ", "iii ", "iv "))
            ):
                return index

    return None


def validate_profit_and_loss(
    extracted_data: dict[str, Any],
) -> list[dict[str, Any]]:

    validations: list[dict[str, Any]] = []

    for table in _get_tables(extracted_data):

        rows = _get_rows(table)

        if not rows:
            continue

        period_columns = _find_period_columns(table)

        if not period_columns:
            continue

        income_start = _find_pl_section(
            rows,
            "income",
        )

        expenditure_start = _find_pl_section(
            rows,
            "expenditure",
        )

        profit_start = _find_pl_section(
            rows,
            "profit",
        )

        # If section headers are unavailable, search whole table.
        if income_start is None:
            income_start = 0

        if expenditure_start is None:
            expenditure_start = 0

        if profit_start is None:
            profit_start = 0

        # ----------------------------------------------------
        # Find concepts.
        # ----------------------------------------------------

        interest_earned = _find_concept_row(
            rows,
            "interest_earned",
            income_start,
            expenditure_start
            if expenditure_start > income_start
            else len(rows),
        )

        other_income = _find_concept_row(
            rows,
            "other_income",
            income_start,
            expenditure_start
            if expenditure_start > income_start
            else len(rows),
        )

        total_income = _find_concept_row(
            rows,
            "total_income",
            income_start,
            expenditure_start
            if expenditure_start > income_start
            else len(rows),
        )

        interest_expended = _find_concept_row(
            rows,
            "interest_expended",
            expenditure_start,
            profit_start
            if profit_start > expenditure_start
            else len(rows),
        )

        operating_expenses = _find_concept_row(
            rows,
            "operating_expenses",
            expenditure_start,
            profit_start
            if profit_start > expenditure_start
            else len(rows),
        )

        provisions = _find_concept_row(
            rows,
            "provisions_contingencies",
            expenditure_start,
            profit_start
            if profit_start > expenditure_start
            else len(rows),
        )

        total_expenditure = _find_concept_row(
            rows,
            "total_expenditure",
            expenditure_start,
            profit_start
            if profit_start > expenditure_start
            else len(rows),
        )

        profit_before_minority = _find_concept_row(
            rows,
            "profit_before_minority",
            profit_start,
        )

        minority_interest = None

        if profit_before_minority is not None:
            minority_interest = _find_concept_row(
                rows,
                "minority_interest",
                profit_before_minority[0] + 1,
            )
        else:
            minority_interest = _find_concept_row(
                rows,
                "minority_interest",
                profit_start,
            )

        group_profit = _find_concept_row(
            rows,
            "group_attributable_profit",
            profit_start,
        )

        share_associates = _find_concept_row(
            rows,
            "share_in_associates",
            profit_start,
        )

        brought_forward = _find_concept_row(
            rows,
            "brought_forward_profit",
            profit_start,
        )

        total_profit = _find_concept_row(
            rows,
            "total_profit",
            profit_start,
        )

        # ----------------------------------------------------
        # Helper for row values.
        # ----------------------------------------------------

        def value_from(
            found: tuple[int, list[Any]] | None,
            column_index: int,
        ) -> float | None:

            if found is None:
                return None

            return _row_value(
                found[1],
                column_index,
            )

        # ----------------------------------------------------
        # Validate every period.
        # ----------------------------------------------------

        for column_index, period in period_columns:

            interest_value = value_from(
                interest_earned,
                column_index,
            )

            other_income_value = value_from(
                other_income,
                column_index,
            )

            total_income_value = value_from(
                total_income,
                column_index,
            )

            validations.append(
                _validation(
                    check=(
                        "Interest Earned + Other Income "
                        "= Total Income"
                    ),
                    input_values={
                        "period": period,
                        "interest_earned": interest_value,
                        "other_income": other_income_value,
                    },
                    calculated_value=(
                        interest_value + other_income_value
                        if (
                            interest_value is not None
                            and other_income_value is not None
                        )
                        else None
                    ),
                    reported_value=total_income_value,
                )
            )

            interest_expended_value = value_from(
                interest_expended,
                column_index,
            )

            operating_expenses_value = value_from(
                operating_expenses,
                column_index,
            )

            provisions_value = value_from(
                provisions,
                column_index,
            )

            total_expenditure_value = value_from(
                total_expenditure,
                column_index,
            )

            validations.append(
                _validation(
                    check=(
                        "Interest Expended + Operating Expenses "
                        "+ Provisions & Contingencies "
                        "= Total Expenditure"
                    ),
                    input_values={
                        "period": period,
                        "interest_expended":
                            interest_expended_value,
                        "operating_expenses":
                            operating_expenses_value,
                        "provisions_and_contingencies":
                            provisions_value,
                    },
                    calculated_value=(
                        interest_expended_value
                        + operating_expenses_value
                        + provisions_value
                        if (
                            interest_expended_value is not None
                            and operating_expenses_value is not None
                            and provisions_value is not None
                        )
                        else None
                    ),
                    reported_value=total_expenditure_value,
                )
            )

            # ------------------------------------------------
            # Total Income - Total Expenditure
            # ------------------------------------------------

            calculated_profit = None

            if (
                total_income_value is not None
                and total_expenditure_value is not None
            ):

                calculated_profit = (
                    total_income_value
                    - total_expenditure_value
                )

            reported_profit = value_from(
                profit_before_minority,
                column_index,
            )

            validations.append(
                _validation(
                    check=(
                        "Total Income - Total Expenditure "
                        "= Net Profit Before Minority Interest"
                    ),
                    input_values={
                        "period": period,
                        "total_income":
                            total_income_value,
                        "total_expenditure":
                            total_expenditure_value,
                    },
                    calculated_value=calculated_profit,
                    reported_value=reported_profit,
                )
            )

            # ------------------------------------------------
            # Group attributable profit
            # ------------------------------------------------

            minority_value = value_from(
                minority_interest,
                column_index,
            )

            associate_value = value_from(
                share_associates,
                column_index,
            )

            calculated_group_profit = None

            if (
                reported_profit is not None
                and minority_value is not None
            ):

                calculated_group_profit = (
                    reported_profit
                    - minority_value
                )

                # Only add associates when the statement
                # actually contains such a row.
                if associate_value is not None:
                    calculated_group_profit += (
                        associate_value
                    )

            reported_group_profit = value_from(
                group_profit,
                column_index,
            )

            validations.append(
                _validation(
                    check=(
                        "Profit Before Minority Interest "
                        "- Minority Interest "
                        "+ Share in Associates where applicable "
                        "= Group Attributable Profit"
                    ),
                    input_values={
                        "period": period,
                        "profit_before_minority":
                            reported_profit,
                        "minority_interest":
                            minority_value,
                        "share_in_profits_of_associates":
                            associate_value,
                    },
                    calculated_value=calculated_group_profit,
                    reported_value=reported_group_profit,
                )
            )

            # ------------------------------------------------
            # Appropriations
            # ------------------------------------------------

            brought_forward_value = value_from(
                brought_forward,
                column_index,
            )

            total_profit_value = value_from(
                total_profit,
                column_index,
            )

            calculated_available_profit = None

            # Store explicit adjustments found between
            # brought-forward profit and total profit.
            applicable_adjustments = 0.0
            adjustment_values = {}

            if (
                reported_group_profit is not None
                and brought_forward_value is not None
            ):

                calculated_available_profit = (
                    reported_group_profit
                    + brought_forward_value
                )

                # ------------------------------------------------
                # Find explicit applicable adjustments.
                #
                # Example:
                # Addition on amalgamation
                #
                # Only values actually present in the extracted
                # statement are included. Nothing is inferred.
                # ------------------------------------------------

                if brought_forward is not None:

                    adjustment_end = (
                        total_profit[0]
                        if (
                            total_profit is not None
                            and total_profit[0] > brought_forward[0]
                        )
                        else len(rows)
                    )

                    adjustment_keywords = (
                        "amalgamation",
                        "addition on",
                        "acquisition",
                    )

                    for adjustment_row in rows[
                        brought_forward[0] + 1:adjustment_end
                    ]:

                        if not adjustment_row:
                            continue

                        adjustment_label = _normalize_label(
                            _row_label(adjustment_row)
                        )

                        if not adjustment_label:
                            continue

                        # Do not accidentally treat minority
                        # interest-related rows as adjustments.
                        if "minority" in adjustment_label:
                            continue

                        if any(
                            keyword in adjustment_label
                            for keyword in adjustment_keywords
                        ):

                            adjustment_value = _row_value(
                                adjustment_row,
                                column_index,
                            )

                            if adjustment_value is not None:

                                applicable_adjustments += (
                                    adjustment_value
                                )

                                adjustment_values[
                                    _row_label(adjustment_row)
                                ] = adjustment_value

                calculated_available_profit += (
                    applicable_adjustments
                )

            if (
                calculated_available_profit is not None
                or total_profit_value is not None
            ):

                validations.append(
                    _validation(
                        check=(
                            "Current Profit + Brought Forward Profit "
                            "+ Applicable Adjustments = Total Profit"
                        ),
                        input_values={
                            "period": period,
                            "current_profit":
                                reported_group_profit,
                            "brought_forward_profit":
                                brought_forward_value,
                            "applicable_adjustments":
                                adjustment_values,
                        },
                        calculated_value=(
                            calculated_available_profit
                        ),
                        reported_value=total_profit_value,
                    )
                )

    return validations
# ============================================================
# CASH FLOW VALIDATION
# ============================================================

def _cash_flow_matcher(
    concept: str,
):
    """
    Match common Cash Flow Statement concepts without depending
    on one exact wording.

    The validator works from the extracted table structure and
    validates each financial period independently.
    """

    if concept == "operating":
        return lambda label: (
            _contains_all(label, "cash", "operating", "activ")
            and _contains_any(label, "net")
        )

    if concept == "investing":
        return lambda label: (
            _contains_all(label, "cash", "investing", "activ")
            and _contains_any(label, "net")
        )

    if concept == "financing":
        return lambda label: (
            _contains_all(label, "cash", "financing", "activ")
            and _contains_any(label, "net")
        )

    if concept == "fx":
        return lambda label: (
            _contains_any(
                label,
                "foreign exchange",
                "exchange rate",
                "exchange rates",
                "translation",
                "fx",
            )
        )

    if concept == "net_change":
        return lambda label: (
            _contains_any(
                label,
                "net increase",
                "net decrease",
                "net change",
            )
            and _contains_any(
                label,
                "cash",
                "cash equivalents",
            )
        )

    if concept == "opening_cash":
        return lambda label: (
            _contains_all(
                label,
                "cash",
                "equivalent",
            )
            and _contains_any(
                label,
                "beginning",
                "opening",
                "april 1",
                "at the beginning",
                "start of",
            )
        )

    if concept == "closing_cash":
        return lambda label: (
            _contains_all(
                label,
                "cash",
                "equivalent",
            )
            and _contains_any(
                label,
                "closing",
                "end",
                "march 31",
                "at the end",
                "end of",
            )
        )

    if concept == "amalgamation":
        return lambda label: (
            _contains_any(
                label,
                "amalgamation",
                "cash and cash equivalents on amalgamation",
                "cash acquired",
                "cash acquired on acquisition",
                "acquired cash",
            )
        )

    return lambda label: False


def _find_cash_flow_row(
    rows: list[list[Any]],
    concept: str,
) -> tuple[int, list[Any]] | None:
    """
    Find a Cash Flow Statement row for a financial concept.
    """
    return _find_row(
        rows,
        _cash_flow_matcher(concept),
    )


def _cash_flow_value_from_row(
    found: tuple[int, list[Any]] | None,
    column_index: int,
) -> float | None:
    """
    Safely extract a numeric value from a matched row.
    """
    if found is None:
        return None

    return _row_value(
        found[1],
        column_index,
    )


def validate_cash_flow(
    extracted_data: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Validate Cash Flow Statements.

    Required checks:

    1. Operating CF + Investing CF + Financing CF
       + FX/translation + applicable cash adjustments
       = Net Increase / (Decrease) in Cash

    2. Opening Cash + Reported Net Increase / (Decrease)
       = Closing Cash

    Important:
    - Comparative periods are validated independently.
    - Parentheses/brackets are treated as negative numbers.
    - FX is optional.
    - Amalgamation/acquisition cash is optional.
    - An adjustment is never added twice.
    - Missing required values produce NOT_APPLICABLE.
    - No values are invented.
    """

    validations: list[dict[str, Any]] = []

    tables = _get_tables(extracted_data)

    for table in tables:

        rows = _get_rows(table)

        if not rows:
            continue

        period_columns = _find_period_columns(table)

        if not period_columns:
            continue

        # --------------------------------------------------------
        # Locate important Cash Flow Statement rows
        # --------------------------------------------------------

        operating = _find_cash_flow_row(
            rows,
            "operating",
        )

        investing = _find_cash_flow_row(
            rows,
            "investing",
        )

        financing = _find_cash_flow_row(
            rows,
            "financing",
        )

        fx = _find_cash_flow_row(
            rows,
            "fx",
        )

        net_change = _find_cash_flow_row(
            rows,
            "net_change",
        )

        opening_cash = _find_cash_flow_row(
            rows,
            "opening_cash",
        )

        closing_cash = _find_cash_flow_row(
            rows,
            "closing_cash",
        )

        amalgamation = _find_cash_flow_row(
            rows,
            "amalgamation",
        )

        # --------------------------------------------------------
        # Validate every comparative period independently
        # --------------------------------------------------------

        for column_index, period in period_columns:

            operating_value = _cash_flow_value_from_row(
                operating,
                column_index,
            )

            investing_value = _cash_flow_value_from_row(
                investing,
                column_index,
            )

            financing_value = _cash_flow_value_from_row(
                financing,
                column_index,
            )

            fx_value = _cash_flow_value_from_row(
                fx,
                column_index,
            )

            net_change_value = _cash_flow_value_from_row(
                net_change,
                column_index,
            )

            amalgamation_value = _cash_flow_value_from_row(
                amalgamation,
                column_index,
            )

            # ----------------------------------------------------
            # CHECK 1
            #
            # CFO + CFI + CFF + FX + applicable adjustment
            # = Net Increase / (Decrease) in Cash
            #
            # Example:
            #
            # 172,815,931
            # - 11,476,802
            # - 58,929,743
            # - 282,622
            # + 295,617
            # = 102,422,381
            #
            # The amalgamation adjustment is included here only
            # when it is explicitly present in the statement.
            # ----------------------------------------------------

            calculated_net_change = None

            if (
                operating_value is not None
                and investing_value is not None
                and financing_value is not None
            ):

                calculated_net_change = (
                    operating_value
                    + investing_value
                    + financing_value
                    + (fx_value or 0)
                    + (amalgamation_value or 0)
                )

            validations.append(
                _validation(
                    check=(
                        "Operating Cash Flow + Investing Cash Flow "
                        "+ Financing Cash Flow + FX/Translation "
                        "+ Applicable Cash Adjustment "
                        "= Net Increase/Decrease in Cash"
                    ),
                    input_values={
                        "period": period,
                        "operating_cash_flow":
                            operating_value,
                        "investing_cash_flow":
                            investing_value,
                        "financing_cash_flow":
                            financing_value,
                        "fx_translation":
                            fx_value,
                        "amalgamation_or_other_adjustment":
                            amalgamation_value,
                    },
                    calculated_value=calculated_net_change,
                    reported_value=net_change_value,
                )
            )

            # ----------------------------------------------------
            # CHECK 2
            #
            # Opening Cash + Reported Net Increase/Decrease
            # = Closing Cash
            #
            # IMPORTANT:
            #
            # Do NOT add amalgamation again here.
            #
            # If the reported Net Increase already includes the
            # amalgamation/acquisition adjustment, adding it again
            # would double-count the adjustment.
            #
            # Example:
            #
            # 390,688,815
            # + 102,422,381
            # = 493,111,196
            # ----------------------------------------------------

            opening_value = _cash_flow_value_from_row(
                opening_cash,
                column_index,
            )

            closing_value = _cash_flow_value_from_row(
                closing_cash,
                column_index,
            )

            calculated_closing = None

            if (
                opening_value is not None
                and net_change_value is not None
            ):

                calculated_closing = (
                    opening_value
                    + net_change_value
                )

            validations.append(
                _validation(
                    check=(
                        "Opening Cash + Reported "
                        "Net Increase/Decrease "
                        "= Closing Cash"
                    ),
                    input_values={
                        "period": period,
                        "opening_cash":
                            opening_value,
                        "reported_net_increase_or_decrease":
                            net_change_value,
                    },
                    calculated_value=calculated_closing,
                    reported_value=closing_value,
                )
            )

    return validations

# ============================================================
# MAIN DISPATCH
# ============================================================

def validate_financial_document(
    document_type: str,
    extracted_data: dict[str, Any],
) -> list[dict[str, Any]]:

    document_type = str(document_type).lower().strip()

    if document_type == "invoice":

        return validate_invoice(
            extracted_data
        )

    if document_type == "balance_sheet":

        return validate_balance_sheet(
            extracted_data
        )

    if document_type == "profit_and_loss":

        return validate_profit_and_loss(
            extracted_data
        )

    if document_type == "cash_flow_statement":

        return validate_cash_flow(
            extracted_data
        )

    return []