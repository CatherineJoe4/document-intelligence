from app.services.financial_validation_service import (
    validate_balance_sheet,
)


def test_balance_sheet_comparative_periods():

    extracted_data = {
        "tables": [
            {
                "headers": [
                    "Particulars",
                    "Schedule",
                    "As at March 31, 2022",
                    "As at March 31, 2021",
                ],
                "rows": [
                    ["CAPITAL AND LIABILITIES", "", "", ""],
                    ["Capital", "1", "554.55", "551.28"],
                    ["Reserves and surplus", "2", "246771.62", "209258.90"],
                    ["Minority interest", "2A", "720.41", "632.76"],
                    ["Deposits", "3", "1558003.03", "1333720.87"],
                    ["Borrowings", "4", "226966.50", "177696.75"],
                    [
                        "Other liabilities and provisions",
                        "5",
                        "89918.19",
                        "77646.07",
                    ],
                    [
                        "Total",
                        "",
                        "2122934.30",
                        "1799506.63",
                    ],
                    ["ASSETS", "", "", ""],
                    [
                        "Cash and balances with Reserve Bank of India",
                        "6",
                        "130030.71",
                        "97370.35",
                    ],
                    [
                        "Balances with banks and money at call and short notice",
                        "7",
                        "25355.02",
                        "23902.16",
                    ],
                    [
                        "Investments",
                        "8",
                        "449263.86",
                        "438823.11",
                    ],
                    [
                        "Advances",
                        "9",
                        "1420942.28",
                        "1185283.52",
                    ],
                    [
                        "Fixed assets",
                        "10",
                        "6283.28",
                        "5099.56",
                    ],
                    [
                        "Other assets",
                        "11",
                        "90910.36",
                        "48879.14",
                    ],
                    [
                        "Goodwill on Consolidation",
                        "",
                        "148.79",
                        "148.79",
                    ],
                    [
                        "Total",
                        "",
                        "2122934.30",
                        "1799506.63",
                    ],
                ],
            }
        ]
    }

    validations = validate_balance_sheet(extracted_data)

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