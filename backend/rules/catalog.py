import re

FOOD_DOMESTIC_PROFILE = {
    "id": "food_domestic",
    "name": "Food - domestic retail package",
    "requires_country_of_origin": False,
    "requires_best_before": True,
}

RULE_CATALOG = {
    "R6_A": {
        "reference": "Rule 6(1)(a) and Rule 10",
        "title": "Name and address of manufacturer / packer / importer",
    },
    "R6_B": {
        "reference": "Rule 6(1)(b)",
        "title": "Common or generic name of commodity",
    },
    "R6_C": {
        "reference": "Rule 6(1)(c)",
        "title": "Net quantity in a standard unit",
    },
    "R6_D": {
        "reference": "Rule 6(1)(d)",
        "title": "Month and year of manufacture / packing / import",
    },
    "R6_E": {
        "reference": "Rule 6(1)(e)",
        "title": "MRP inclusive of all taxes",
    },
    "R6_2": {
        "reference": "Rule 6(2)",
        "title": "Consumer-care contact details",
    },
    "R7": {
        "reference": "Rule 7",
        "title": "Minimum font / numeral height",
    },
    "R8": {
        "reference": "Rule 8",
        "title": "Declaration placement on principal display panel",
    },
}


def find_value(text, patterns):
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)

        if match:
            return match.group(1).strip()

    return None


def find_generic_name(text):
    labelled_name = find_value(
        text,
        [
            r"(?:common\s*name|generic\s*name|product\s*name)\s*:\s*([^\n]+)",
        ],
    )

    if labelled_name:
        return labelled_name

    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for index, line in enumerate(lines):
        if re.search(r"net\s*(?:quantity|weight|wt\.?)", line, re.IGNORECASE):
            if index > 0:
                return lines[index - 1]

    return None


def find_address(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for index, line in enumerate(lines):
        if re.search(
            r"(?:packed\s*by|manufactured\s*by|manufacturer|packer|imported\s*by)",
            line,
            re.IGNORECASE,
        ):
            if index + 1 < len(lines):
                possible_address = lines[index + 1]

                if "," in possible_address or re.search(r"\d{5,6}", possible_address):
                    return possible_address

    return find_value(
        text,
        [
            r"(?:address|addr\.)\s*:\s*([^\n]+)",
        ],
    )


def extract_declarations(text):
    return {
        "Common / generic name": find_generic_name(text),
        "Manufacturer / packer / importer": find_value(
            text,
            [
                r"(?:packed\s*by|manufactured\s*by|manufacturer|packer|imported\s*by|importer)\s*:\s*([^\n]+)",
            ],
        ),
        "Address": find_address(text),
        "Net quantity": find_value(
            text,
            [
                r"(?:net\s*quantity|net\s*weight|net\s*wt\.?|quantity)\s*:\s*([^\n]+)",
            ],
        ),
        "MRP": find_value(
            text,
            [
                r"(?:mrp|maximum retail price)\s*:\s*([^\n]+)",
            ],
        ),
        "Manufacture / pack / import date": find_value(
            text,
            [
                r"(?:mfg\.?\s*date|manufacturing\s*date|packing\s*date|pack\s*date|import\s*date)\s*:\s*([^\n]+)",
            ],
        ),
        "Best before / use by": find_value(
            text,
            [
                r"(?:best\s*before|use\s*by|expiry\s*date|exp\.?\s*date)\s*:\s*([^\n]+)",
            ],
        ),
        "Consumer care": find_value(
            text,
            [
                r"(?:consumer\s*care|customer\s*care|helpline)\s*:\s*([^\n]+)",
            ],
        ),
        "Country of origin": find_value(
            text,
            [
                r"country\s*of\s*origin\s*:\s*([^\n]+)",
                r"made\s+in\s+([A-Za-z ]+)",
            ],
        ),
        "Batch number": find_value(
            text,
            [
                r"batch\s*(?:no\.?|number)?\s*:\s*([^\n]+)",
            ],
        ),
    }


def has_standard_quantity_unit(value):
    if not value:
        return False

    return bool(
        re.search(
            r"\b(?:mg|g|kg|ml|l|litre|litres|m|cm|mm|nos\.?|number|pieces?)\b",
            value,
            re.IGNORECASE,
        )
    )


def has_consumer_contact(value):
    if not value:
        return False

    return bool(re.search(r"\d{6,}", value) or "@" in value)


def add_rule(rule_code, status, evidence, reason, applicability="Applicable"):
    rule = RULE_CATALOG[rule_code]

    return {
        "rule_id": rule_code,
        "reference": rule["reference"],
        "title": rule["title"],
        "applicability": applicability,
        "status": status,
        "evidence": evidence or "Not detected",
        "reason": reason,
    }


def evaluate_rules(profile, declarations, image_size):
    rule_checks = []

    company = declarations["Manufacturer / packer / importer"]
    address = declarations["Address"]

    rule_checks.append(
        add_rule(
            "R6_A",
            "Pass" if company and address else "Potential violation",
            f"{company}; {address}" if company and address else company or address,
            "Responsible entity and address detected."
            if company and address
            else "Both a responsible entity name and an address are required.",
        )
    )

    generic_name = declarations["Common / generic name"]

    rule_checks.append(
        add_rule(
            "R6_B",
            "Pass" if generic_name else "Potential violation",
            generic_name,
            "Common or generic product name detected."
            if generic_name
            else "No common or generic product name detected.",
        )
    )

    quantity = declarations["Net quantity"]

    rule_checks.append(
        add_rule(
            "R6_C",
            "Pass" if has_standard_quantity_unit(quantity) else "Potential violation",
            quantity,
            "Net quantity with a standard unit detected."
            if has_standard_quantity_unit(quantity)
            else "Net quantity with a recognizable standard unit was not detected.",
        )
    )

    pack_date = declarations["Manufacture / pack / import date"]

    rule_checks.append(
        add_rule(
            "R6_D",
            "Pass" if pack_date else "Potential violation",
            pack_date,
            "Month and year declaration detected."
            if pack_date
            else "No manufacture, packing, or import month/year detected.",
        )
    )

    mrp = declarations["MRP"]

    mrp_has_tax_text = bool(
        mrp
        and re.search(
            r"incl\.?\s*of\s*all\s*taxes|inclusive\s*of\s*all\s*taxes",
            mrp,
            re.IGNORECASE,
        )
    )

    rule_checks.append(
        add_rule(
            "R6_E",
            "Pass" if mrp and mrp_has_tax_text else "Potential violation",
            mrp,
            "MRP and inclusive-of-all-taxes wording detected."
            if mrp and mrp_has_tax_text
            else "MRP must include inclusive-of-all-taxes wording.",
        )
    )

    consumer_care = declarations["Consumer care"]

    rule_checks.append(
        add_rule(
            "R6_2",
            "Pass" if has_consumer_contact(consumer_care) else "Potential violation",
            consumer_care,
            "Consumer-care contact detected."
            if has_consumer_contact(consumer_care)
            else "No consumer-care phone number or email address detected.",
        )
    )

    if profile["requires_best_before"]:
        best_before = declarations["Best before / use by"]

        rule_checks.append(
            {
                "rule_id": "FOOD_01",
                "reference": "Food-package profile",
                "title": "Best-before / use-by declaration",
                "applicability": "Applicable - food profile",
                "status": "Pass" if best_before else "Potential violation",
                "evidence": best_before or "Not detected",
                "reason": "Best-before / use-by declaration detected."
                if best_before
                else "No best-before / use-by declaration detected.",
            }
        )

    shortest_side = min(image_size)

    rule_checks.append(
        add_rule(
            "R7",
            "Needs review",
            f"Image resolution: {image_size[0]} x {image_size[1]} px",
            "Exact font size in millimetres needs package dimensions or a calibrated image.",
        )
    )

    rule_checks.append(
        add_rule(
            "R8",
            "Needs review",
            "Single label image",
            "Principal display-panel placement needs image-layout analysis.",
        )
    )

    automatic_checks = [
        rule
        for rule in rule_checks
        if rule["status"] in {"Pass", "Potential violation"}
    ]

    passed_checks = [
        rule
        for rule in automatic_checks
        if rule["status"] == "Pass"
    ]

    potential_violations = [
        rule["title"]
        for rule in rule_checks
        if rule["status"] == "Potential violation"
    ]

    manual_review_items = [
        rule["title"]
        for rule in rule_checks
        if rule["status"] == "Needs review"
    ]

    score = round((len(passed_checks) / len(automatic_checks)) * 100)

    if potential_violations:
        compliance = {
            "status": "Potential Violation",
            "score": score,
            "message": "One or more applicable declarations may be missing or non-compliant.",
            "issues": potential_violations,
            "manual_review_items": manual_review_items,
        }
    else:
        compliance = {
            "status": "Compliant",
            "score": score,
            "message": "All automatically verifiable declarations for this profile were detected.",
            "issues": [],
            "manual_review_items": manual_review_items,
        }

    return rule_checks, compliance