from app.services.financial_validation_service import (
    validate_invoice,
)


def test_invoice_line_total_failure():

    extracted_data = {
        "fields": {
            "subtotal": {
                "value": "250"
            },
            "total_amount": {
                "value": "250"
            },
        },
        "line_items": [
            {
                "description": "Test Item",
                "quantity": "2",
                "unit_price": "100",
                "line_total": "250",
            }
        ],
    }

    validations = validate_invoice(extracted_data)

    assert validations

    line_validation = next(
        item
        for item in validations
        if "Quantity × Unit Price" in item["check"]
    )

    assert line_validation["calculated_value"] == 200
    assert line_validation["reported_value"] == 250
    assert line_validation["variance"] == -50
    assert line_validation["status"] == "FAIL"