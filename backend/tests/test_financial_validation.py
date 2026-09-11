from app.services.financial_validation_service import (
    validate_profit_and_loss,
)


def test_profit_and_loss_generalized_headings():

    extracted_data = {
        "tables": [
            {
                "headers": [
                    "Particulars",
                    "Schedule",
                    "Year ended March 31, 2022",
                    "Year ended March 31, 2021",
                ],
                "rows": [
                    ["I INCOME", "", "", ""],
                    ["Interest earned", "13", "135936.41", "128552.40"],
                    ["Other income", "14", "31758.99", "27332.88"],
                    ["Total Income", "", "167695.40", "155885.28"],

                    ["II EXPENDITURE", "", "", ""],
                    [
                        "Interest expended",
                        "15",
                        "58584.33",
                        "59247.59",
                    ],
                    [
                        "Operating expenses",
                        "16",
                        "40312.43",
                        "35001.26",
                    ],
                    [
                        "Provisions and contingencies [Refer Schedule 18 (12)]",
                        "",
                        "30647.74",
                        "29779.66",
                    ],
                    [
                        "Total Expenditure",
                        "",
                        "129544.50",
                        "124028.51",
                    ],

                    ["III PROFIT", "", "", ""],
                    [
                        "Consolidated Net Profit for the year before minorities' interest",
                        "",
                        "38150.90",
                        "31856.77",
                    ],
                    [
                        "Less : Minorities' Interest",
                        "",
                        "98.15",
                        "23.56",
                    ],
                    [
                        "Consolidated Net Profit for the year attributable to the group",
                        "",
                        "38052.75",
                        "31833.21",
                    ],
                    [
                        "Add: Brought forward consolidated profit attributable to the group",
                        "",
                        "78594.20",
                        "61817.68",
                    ],
                    [
                        "Total Profit",
                        "",
                        "116646.95",
                        "93650.89",
                    ],
                ],
            }
        ]
    }

    validations = validate_profit_and_loss(extracted_data)

    assert validations

    # All validations that can be calculated should pass.
    calculated_validations = [
        item
        for item in validations
        if item["status"] != "NOT_APPLICABLE"
    ]

    assert calculated_validations

    print("\nVALIDATION RESULTS:")
    for item in validations:
        print(item)

    assert all(
        item["status"] == "PASS"
        for item in calculated_validations
)