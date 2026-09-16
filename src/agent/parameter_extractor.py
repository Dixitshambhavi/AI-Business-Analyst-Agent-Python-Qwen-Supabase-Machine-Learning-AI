import re


# ============================================================
# COUNTRY ALIASES
# ============================================================

COUNTRY_ALIASES = {
    "india": "IN",
    "indian": "IN",

    "usa": "US",
    "us": "US",
    "u.s.": "US",
    "united states": "US",
    "united states of america": "US",
    "america": "US",

    "germany": "DE",
    "german": "DE",

    "uk": "UK",
    "u.k.": "UK",
    "united kingdom": "UK",
    "britain": "UK",

    "canada": "CA",
    "canadian": "CA",

    "uae": "AE",
    "united arab emirates": "AE",
}


# ============================================================
# MONTH ALIASES
# ============================================================

MONTH_ALIASES = {
    "january": 1,
    "jan": 1,

    "february": 2,
    "feb": 2,

    "march": 3,
    "mar": 3,

    "april": 4,
    "apr": 4,

    "may": 5,

    "june": 6,
    "jun": 6,

    "july": 7,
    "jul": 7,

    "august": 8,
    "aug": 8,

    "september": 9,
    "sep": 9,
    "sept": 9,

    "october": 10,
    "oct": 10,

    "november": 11,
    "nov": 11,

    "december": 12,
    "dec": 12,
}


# ============================================================
# EXTRACT YEAR
# ============================================================

def extract_year(question: str):

    match = re.search(
        r"\b(20\d{2})\b",
        question
    )

    if match:
        return int(match.group(1))

    return None


# ============================================================
# EXTRACT ALL COUNTRIES
# ============================================================

def extract_countries(question: str):
    """
    Return all countries mentioned in the question.

    Example:
        Compare India and US
        -> ["IN", "US"]
    """

    question_lower = question.lower()

    matches = []

    aliases = sorted(
        COUNTRY_ALIASES.items(),
        key=lambda x: len(x[0]),
        reverse=True
    )

    for alias, code in aliases:

        pattern = rf"\b{re.escape(alias)}\b"

        if re.search(
            pattern,
            question_lower
        ):

            if code not in matches:
                matches.append(code)

    return matches


# ============================================================
# EXTRACT FIRST COUNTRY
# ============================================================

def extract_country(question: str):

    countries = extract_countries(
        question
    )

    if countries:
        return countries[0]

    return None


# ============================================================
# EXTRACT MONTH
# ============================================================

def extract_month(question: str):
    """
    Extract:

        August
        Aug
        August 2026
        Aug 2026
        2026-08
        08/2026
    """

    question_lower = question.lower()

    # YYYY-MM
    match = re.search(
        r"\b(20\d{2})-(0[1-9]|1[0-2])\b",
        question_lower
    )

    if match:

        year = int(
            match.group(1)
        )

        month = int(
            match.group(2)
        )

        return f"{year:04d}-{month:02d}"

    # MM/YYYY
    match = re.search(
        r"\b(0?[1-9]|1[0-2])/(20\d{2})\b",
        question_lower
    )

    if match:

        month = int(
            match.group(1)
        )

        year = int(
            match.group(2)
        )

        return f"{year:04d}-{month:02d}"

    # Month names
    month_names = sorted(
        MONTH_ALIASES.items(),
        key=lambda x: len(x[0]),
        reverse=True
    )

    for month_name, month_number in month_names:

        pattern = rf"\b{re.escape(month_name)}\b"

        if re.search(
            pattern,
            question_lower
        ):

            year = extract_year(
                question
            )

            if year is not None:

                return (
                    f"{year:04d}-"
                    f"{month_number:02d}"
                )

            return f"--{month_number:02d}"

    return None


# ============================================================
# EXTRACT LIMIT
# ============================================================

def extract_limit(question: str):

    question_lower = question.lower()

    # top N
    match = re.search(
        r"\btop\s+(\d+)\b",
        question_lower
    )

    if match:
        return int(
            match.group(1)
        )

    # first N
    match = re.search(
        r"\bfirst\s+(\d+)\b",
        question_lower
    )

    if match:
        return int(
            match.group(1)
        )

    ranking_words = [
        "highest",
        "best",
        "greatest",
        "largest",
        "maximum",
        "max",
        "lowest",
        "worst",
        "minimum",
        "min",
    ]

    if any(
        word in question_lower
        for word in ranking_words
    ):
        return 1

    return None

# ============================================================
# DETECT TREND INTENT
# ============================================================

def detect_trend_intent(question: str) -> bool:
    question_lower = question.lower()

    trend_keywords = [
        "trend",
        "trends",
        "sales trend",
        "revenue trend",
        "roas trend",
        "tacos trend",
        "growth trend",
        "growth",
        "month over month",
        "month-over-month",
        "mom",
        "change over time",
        "performance trend",
        "trajectory",
        "best month",
        "worst month",
        "highest sales month",
        "lowest sales month",
        "largest increase",
        "largest decline",
        "increase in sales",
        "decrease in sales",
    ]

    return any(
        keyword in question_lower
        for keyword in trend_keywords
    )

# ============================================================
# EXTRACT BUSINESS PARAMETERS
# ============================================================
def extract_parameters(
    question: str
) -> dict:

    countries = extract_countries(
        question
    )

    return {
        "country": (
            countries[0]
            if countries
            else None
        ),

        "country1": (
            countries[0]
            if len(countries) >= 1
            else None
        ),

        "country2": (
            countries[1]
            if len(countries) >= 2
            else None
        ),

        "countries": countries,

        "year": extract_year(
            question
        ),

        "month": extract_month(
            question
        ),

        "limit": extract_limit(
            question
        ),

        "trend": detect_trend_intent(
            question
        ),
    }

# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    questions = [

        "Compare India and US.",

        "Compare India and United States in 2026.",

        "Compare Germany and India.",

        "Which country has the highest sales?",

        "What are the top 5 products in US?",

        "Show monthly sales and ROAS for 2026.",

        "Which SKU has the highest revenue in India in August 2026?",

        "What are the top 5 products in the US in July 2026.",
    ]

    for question in questions:

        print()
        print("=" * 70)

        print(
            question
        )

        print("=" * 70)

        print(
            extract_parameters(
                question
            )
        )