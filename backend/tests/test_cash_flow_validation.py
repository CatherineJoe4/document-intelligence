from app.services.financial_validation_service import (
    validate_cash_flow,
)


def test_cash_flow_generalized_headings():

    extracted_data = {
        "tables": [
            {
                "headers": [
                    "Particulars",
                    "Year ended March 31, 2022",
                    "Year ended March 31, 2021",
                ],
                "rows": [
                    [
                        "Net cash flow from operating activities",
                        "1000",
                        "900",
                    ],
                    [
                        "Net cash used in investing activities",
                        "(400)",
                        "(300)",
                    ],
                    [
                        "Net cash generated from financing activities",
                        "200",
                        "150",
                    ],
                    [
                        "Net increase / (decrease) in cash and cash equivalents",
                        "800",
                        "750",
                    ],
                    [
                        "Cash and cash equivalents at the beginning of the year",
                        "2000",
                        "1250",
                    ],
                    [
                        "Cash and cash equivalents at the end of the year",
                        "2800",
                        "2000",
                    ],
                ],
            }
        ]
    }

    validations = validate_cash_flow(extracted_data)

    assert validations

    calculated_validations = [
        item
        for item in validations
        if item["status"] != "NOT_APPLICABLE"
    ]

    assert calculated_validations

    assert all(
        item["status"] == "PASS"
        for item in calculated_validations
    )