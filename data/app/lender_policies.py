LENDER_POLICIES = {
    "nira": {
        "lender_id": "nira",
        "policy": """
            policy_version: "2026-04-18.v1"
            lender: "Nira Finance"
            cases:
              hardship: hardship team contacts within 24 hours
              lump sum discount:
                if the person is fulltime eomployed: discount upto 5 percent if paying immidiately
                if person is partially emplyed: discount upto 20 percent if lunpsum is agreed to
              structured payment plan:
                2 months max extension
        """,
    },
    "slice": {
        "lender_id": "slice",
        "policy": """
            policy_version: "2026-04-18.v1"
            lender: "Slice"
            cases:
              hardship: hardship team reviews within 48 hours
              lump sum discount:
                if the person is salaried: discount upto 10 percent if paying within 3 days
                if the person has irregular income: discount upto 15 percent if one time payment is confirmed
              structured payment plan:
                3 months max extension
        """,
    },
}