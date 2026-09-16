import re
from typing import Any


# ============================================================
# NUMBER NORMALIZATION
# ============================================================

def normalize_number(value: Any) -> str:
    """
    Normalize a numeric value for comparison.
    """

    if value is None:
        return ""

    text = str(value)

    text = text.replace("$", "")
    text = text.replace(",", "")
    text = text.replace("%", "")
    text = text.strip()

    return text


# ============================================================
# EXTRACT NUMBERS
# ============================================================

def extract_numbers(text: str) -> list[str]:
    """
    Extract numeric values from text.
    """

    if not text:
        return []

    matches = re.findall(
        r"(?<![A-Za-z])"
        r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?"
        r"%?",
        text
    )

    return [
        normalize_number(value)
        for value in matches
    ]


# ============================================================
# EXTRACT SKU-LIKE TOKENS
# ============================================================

def extract_skus_from_text(
    text: str,
    authorized_skus: set[str]
) -> list[str]:
    """
    Only identify SKUs that actually exist in the trusted
    database results.

    This avoids treating normal English words as SKUs.
    """

    if not text:
        return []

    answer_upper = text.upper()

    mentioned = []

    # --------------------------------------------------------
    # Instead of guessing what looks like a SKU, search only
    # for SKUs that are actually authorized by the database.
    # --------------------------------------------------------

    for sku in authorized_skus:

        if not sku:
            continue

        # Escape special regex characters
        escaped = re.escape(sku.upper())

        if re.search(
            rf"(?<![A-Z0-9]){escaped}(?![A-Z0-9])",
            answer_upper
        ):

            mentioned.append(
                sku.upper()
            )

    return mentioned


# ============================================================
# EXTRACT COUNTRIES
# ============================================================

def extract_countries_from_text(
    text: str,
    authorized_countries: set[str]
) -> list[str]:
    """
    Identify only countries that were returned by the database.
    """

    if not text:
        return []

    answer_upper = text.upper()

    mentioned = []

    for country in authorized_countries:

        if not country:
            continue

        escaped = re.escape(
            country.upper()
        )

        if re.search(
            rf"(?<![A-Z0-9]){escaped}(?![A-Z0-9])",
            answer_upper
        ):

            mentioned.append(
                country.upper()
            )

    return mentioned


# ============================================================
# COLLECT AUTHORIZED FACTS
# ============================================================

def collect_authorized_facts(
    analysis: dict[str, Any]
) -> dict[str, set[str]]:
    """
    Collect facts directly present in trusted tool results.
    """

    authorized = {
        "numbers": set(),
        "skus": set(),
        "countries": set(),
        "months": set(),
        "risks": set(),
    }

    # Support both legacy {"results": ...} structures and the
    # current multi-step {"steps": ...} execution structure.
    candidates = []

    if isinstance(analysis, dict):
        if "results" in analysis:
            candidates.append(analysis.get("results"))
        if "steps" in analysis:
            candidates.append(analysis.get("steps"))

    iterable = []

    def _extend_candidate(value):
        if isinstance(value, dict):
            iterable.extend(value.values())
        elif isinstance(value, list):
            iterable.extend(value)

    for candidate in candidates:
        _extend_candidate(candidate)

    # If neither structure was available, keep validation safe.
    if not iterable:
        iterable = []

    # --------------------------------------------------------
    # Recursive traversal
    # --------------------------------------------------------

    def traverse(value):

        if isinstance(value, dict):

            for key, item in value.items():

                key_lower = str(key).lower()

                # --------------------------------------------
                # SKU
                # --------------------------------------------

                if (
                    key_lower == "sku"
                    and item is not None
                ):

                    authorized["skus"].add(
                        str(item).upper().strip()
                    )

                # --------------------------------------------
                # Country
                # --------------------------------------------

                elif (
                    key_lower == "country"
                    and item is not None
                ):

                    authorized["countries"].add(
                        str(item).upper().strip()
                    )

                # --------------------------------------------
                # Month
                # --------------------------------------------

                elif key_lower in {
                    "month",
                    "year_month"
                } and item is not None:

                    authorized["months"].add(
                        str(item).strip()
                    )

                # --------------------------------------------
                # Risk
                # --------------------------------------------

                elif (
                    key_lower == "risk"
                    and item is not None
                ):

                    authorized["risks"].add(
                        str(item).upper().strip()
                    )

                # --------------------------------------------
                # Numbers
                # --------------------------------------------

                elif isinstance(
                    item,
                    (int, float)
                ):

                    authorized["numbers"].add(
                        normalize_number(item)
                    )

                traverse(item)

        elif isinstance(value, list):

            for item in value:
                traverse(item)

    for result in iterable:

        traverse(result)

    return authorized


# ============================================================
# VALIDATE SKU CLAIMS
# ============================================================

def validate_sku_claims(
    answer: str,
    authorized_skus: set[str]
) -> tuple[bool, list[str]]:
    """
    Validate SKUs mentioned in the answer.

    Only database-authorized SKUs are checked.
    """

    mentioned = extract_skus_from_text(
        answer,
        authorized_skus
    )

    # Because we only search for authorized SKUs,
    # there cannot be an unauthorized SKU from this detector.
    #
    # This function mainly exists for future extension
    # where we may use a stricter SKU parser.

    unauthorized = []

    for sku in mentioned:

        if sku not in authorized_skus:

            unauthorized.append(
                sku
            )

    if unauthorized:

        return False, unauthorized

    return True, []


# ============================================================
# VALIDATE RISK CLAIMS
# ============================================================

def validate_risk_claims(
    answer: str,
    authorized_risks: set[str]
) -> tuple[bool, list[str]]:

    known_risks = {
        "CRITICAL",
        "HIGH",
        "MEDIUM",
        "NORMAL",
        "NO_AD_REVENUE",
        "ROAS_BELOW_1",
        "HIGH_ACOS",
        "SALES_ATTRIBUTION_CHECK",
    }

    answer_upper = answer.upper()

    mentioned = {
        risk
        for risk in known_risks
        if re.search(
            rf"\b{re.escape(risk)}\b",
            answer_upper
        )
    }

    unauthorized = [
        risk
        for risk in mentioned
        if risk not in authorized_risks
    ]

    if unauthorized:

        return False, unauthorized

    return True, []


# ============================================================
# VALIDATE UNSUPPORTED BUSINESS CLAIMS
# ============================================================

def validate_unsupported_claims(
    answer: str
) -> list[str]:
    """
    Detect common unsupported claims we don't want our
    small local model to invent.
    """

    unsupported_phrases = [
        "customers are likely",
        "customers are probably",
        "market penetration",
        "high-margin",
        "high margin",
        "gross margin",
        "profit margin",
        "customer loyalty",
        "customer engagement",
        "customers are buying repeatedly",
        "customers are purchasing repeatedly",
        "increasing market share",
        "market share is increasing",
    ]

    answer_lower = answer.lower()

    errors = []

    for phrase in unsupported_phrases:

        if phrase in answer_lower:

            errors.append(
                f"Unsupported statement detected: '{phrase}'"
            )

    return errors


# ============================================================
# VALIDATE RESULT COUNT
# ============================================================

def validate_requested_count(
    answer: str,
    analysis: dict[str, Any]
) -> tuple[bool, str | None]:
    """
    Basic protection against answers that obviously include
    an arbitrary number of products.

    This intentionally stays conservative.
    """

    results = analysis.get(
        "results",
        []
    )

    if isinstance(results, dict):

        iterable = list(
            results.values()
        )

    elif isinstance(results, list):

        iterable = results

    else:

        iterable = []

    # --------------------------------------------------------
    # Look for top_products result
    # --------------------------------------------------------

    product_count = None

    for result in iterable:

        if not isinstance(result, dict):
            continue

        tool_name = result.get(
            "tool",
            ""
        )

        if tool_name == "top_products":

            data = result.get(
                "data",
                []
            )

            if isinstance(data, list):

                product_count = len(data)

                break

    # Nothing to validate
    if product_count is None:

        return True, None

    # --------------------------------------------------------
    # If tool returned 5 products, we cannot reliably
    # count natural-language mentions, because the answer
    # may summarize rather than list all rows.
    #
    # So this function is intentionally informational only.
    # --------------------------------------------------------

    return True, None


# ============================================================
# FINAL ANSWER VALIDATION
# ============================================================

def validate_final_answer(
    answer: str,
    analysis: dict[str, Any]
) -> tuple[bool, list[str]]:
    """
    Validate the LLM response against trusted tool results.
    """

    errors = []

    if not answer or not answer.strip():

        return False, [
            "The LLM returned an empty answer."
        ]

    authorized = collect_authorized_facts(
        analysis
    )

    # --------------------------------------------------------
    # SKU validation
    # --------------------------------------------------------

    valid, sku_errors = validate_sku_claims(
        answer,
        authorized["skus"]
    )

    if not valid:

        errors.extend(
            [
                "Unauthorized SKU: " + sku
                for sku in sku_errors
            ]
        )

    # --------------------------------------------------------
    # Country validation
    # --------------------------------------------------------

    mentioned_countries = (
        extract_countries_from_text(
            answer,
            authorized["countries"]
        )
    )

    for country in mentioned_countries:

        if country not in authorized["countries"]:

            errors.append(
                f"Unauthorized country: {country}"
            )

    # --------------------------------------------------------
    # Risk validation
    # --------------------------------------------------------
    # Risk labels are only meaningful when the trusted execution
    # actually returned risk fields. This prevents ordinary words
    # such as "high sales" from being interpreted as HIGH risk.
    # --------------------------------------------------------

    risk_validation_required = bool(
        authorized["risks"]
    )

    if risk_validation_required:
        valid, risk_errors = validate_risk_claims(
            answer,
            authorized["risks"]
        )

        if not valid:
            errors.extend(
                [
                    "Unauthorized risk classification: "
                    + risk
                    for risk in risk_errors
                ]
            )

    # --------------------------------------------------------
    # Unsupported business claims
    # --------------------------------------------------------

    errors.extend(
        validate_unsupported_claims(
            answer
        )
    )

    # --------------------------------------------------------
    # Return
    # --------------------------------------------------------

    return (
        len(errors) == 0,
        errors
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    test_analysis = {

        "results": [

            {
                "tool": "top_products",

                "data": [

                    {
                        "sku": "CBP9RO50",
                        "sales": 2950198.32,
                        "risk": "CRITICAL"
                    },

                    {
                        "sku": "CNB5CMT50UB",
                        "sales": 2486596.89,
                        "risk": "HIGH"
                    }

                ]
            }
        ]
    }

    # --------------------------------------------------------
    # GOOD ANSWER
    # --------------------------------------------------------

    good_answer = """
    CBP9RO50 generated $2,950,198.32 in sales and
    has CRITICAL inventory risk.
    """

    valid, errors = validate_final_answer(
        good_answer,
        test_analysis
    )

    print()
    print("=" * 70)
    print("GOOD ANSWER TEST")
    print("=" * 70)
    print("Valid:", valid)
    print("Errors:", errors)

    # --------------------------------------------------------
    # BAD ANSWER
    # --------------------------------------------------------

    bad_answer = """
    Product ABC999 has excellent customer loyalty and
    $99,999,999 in profit.
    """

    valid, errors = validate_final_answer(
        bad_answer,
        test_analysis
    )

    print()
    print("=" * 70)
    print("BAD ANSWER TEST")
    print("=" * 70)
    print("Valid:", valid)
    print("Errors:", errors)