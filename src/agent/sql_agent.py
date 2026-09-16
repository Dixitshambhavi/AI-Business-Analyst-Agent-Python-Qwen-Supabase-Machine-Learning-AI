from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from sqlalchemy import text

from src.database.connection import engine
from src.agent.llm import generate_response


# ============================================================
# CONFIGURATION
# ============================================================

TABLE_NAME = "business_sales"


# ============================================================
# BUSINESS COLUMN DEFINITIONS
# ============================================================

COLUMN_DEFINITIONS = {
    "sku": "Product/SKU identifier.",
    "unit_ordered": "Number of units ordered.",
    "gross_sales": "Gross sales revenue amount already calculated at row level.",
    "ad_spend": "Advertising spend amount already calculated at row level.",
    "ad_revenue": "Revenue attributed to advertising.",
    "tacos": "Total advertising cost of sales percentage.",
    "acos": "Advertising cost of sales percentage.",
    "roas": "Source ROAS percentage-style metric from the original dataset.",
    "roas_standard": "Standard ROAS ratio = ad_revenue / ad_spend.",
    "roas_percentage": "Standard ROAS expressed as a percentage.",
    "ad_orders": "Orders attributed to advertising.",
    "ad_units": "Units attributed to advertising.",
    "cvr": "Conversion rate.",
    "impression": "Advertising impressions.",
    "click": "Advertising clicks.",
    "ctr": "Click-through rate.",
    "cpc": "Cost per click.",
    "organic_percentage": "Organic sales percentage.",
    "organic_sale": "Organic sales amount already calculated at row level.",
    "fba_inv": "FBA inventory quantity.",
    "awd": "AWD inventory quantity.",
    "fba_other": "Other FBA inventory quantity.",
    "esq": "Inventory ESQ metric.",
    "moc_sellable": "MOC sellable inventory.",
    "moc_wh": "MOC warehouse inventory.",
    "country": "Country code.",
    "platform": "Sales platform.",
    "year_month": "Month represented as a PostgreSQL DATE containing the first day of the month.",
}


# ============================================================
# DATABASE SCHEMA
# ============================================================

def get_table_schema() -> list[dict[str, Any]]:
    """
    Read the actual schema of public.business_sales.
    """

    query = text("""
        SELECT
            column_name,
            data_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = :table_name
        ORDER BY ordinal_position
    """)

    with engine.connect() as connection:

        rows = connection.execute(
            query,
            {"table_name": TABLE_NAME}
        ).mappings().all()

    return [
        dict(row)
        for row in rows
    ]


def build_schema_text() -> str:
    """
    Convert the PostgreSQL schema into LLM-readable text.
    """

    schema = get_table_schema()

    if not schema:

        raise ValueError(
            f"Table public.{TABLE_NAME} was not found."
        )

    lines = []

    for column in schema:

        name = column["column_name"]
        dtype = column["data_type"]

        definition = COLUMN_DEFINITIONS.get(
            name,
            "Business data column."
        )

        lines.append(
            f"- {name} ({dtype}): {definition}"
        )

    return "\n".join(lines)


# ============================================================
# SQL EXTRACTION
# ============================================================

def extract_sql(response: str) -> str:
    """
    Extract a SQL statement from the LLM response.
    """

    if not response:

        raise ValueError(
            "The LLM returned an empty SQL response."
        )

    response = response.strip()

    # --------------------------------------------
    # SQL markdown block
    # --------------------------------------------

    match = re.search(
        r"```sql\s*(.*?)```",
        response,
        flags=re.IGNORECASE | re.DOTALL
    )

    if match:
        return match.group(1).strip()

    # --------------------------------------------
    # Generic code block
    # --------------------------------------------

    match = re.search(
        r"```\s*(.*?)```",
        response,
        flags=re.DOTALL
    )

    if match:

        candidate = match.group(1).strip()

        if candidate.lower().startswith(
            ("select", "with")
        ):

            return candidate

    # --------------------------------------------
    # Search for SELECT / WITH inside response
    # --------------------------------------------

    sql_match = re.search(
        r"(?is)\b(select|with)\b.*",
        response
    )

    if sql_match:
        return sql_match.group(0).strip()

    return response


# ============================================================
# GENERAL SQL SAFETY VALIDATION
# ============================================================

def validate_sql(
    sql: str
) -> tuple[bool, str]:
    """
    Validate SQL before it reaches Supabase.

    Only read-only SELECT / WITH queries against
    public.business_sales are permitted.
    """

    if not sql or not sql.strip():

        return (
            False,
            "SQL query is empty."
        )

    normalized = re.sub(
        r"\s+",
        " ",
        sql.strip().lower()
    )

    # --------------------------------------------
    # Remove trailing semicolon for inspection
    # --------------------------------------------

    cleaned = normalized.rstrip(";").strip()

    # --------------------------------------------
    # Must start with SELECT or WITH
    # --------------------------------------------

    if not (
        cleaned.startswith("select ")
        or cleaned.startswith("select(")
        or cleaned.startswith("with ")
    ):

        return (
            False,
            "Only SELECT or WITH queries are allowed."
        )

    # --------------------------------------------
    # Prevent multiple statements
    # --------------------------------------------

    if ";" in cleaned:

        return (
            False,
            "Multiple SQL statements are not allowed."
        )

    # --------------------------------------------
    # Forbidden operations
    # --------------------------------------------

    forbidden_patterns = [
        r"\binsert\b",
        r"\bupdate\b",
        r"\bdelete\b",
        r"\bdrop\b",
        r"\balter\b",
        r"\btruncate\b",
        r"\bcreate\b",
        r"\bgrant\b",
        r"\brevoke\b",
        r"\bcomment\b",
        r"\bcopy\b",
        r"\bvacuum\b",
        r"\bmerge\b",
        r"\brefresh\b",
        r"\bcall\b",
        r"\bdo\b",
    ]

    for pattern in forbidden_patterns:

        if re.search(
            pattern,
            cleaned
        ):

            return (
                False,
                f"Forbidden SQL operation detected: {pattern}"
            )

    # --------------------------------------------
    # Only allow expected table
    # --------------------------------------------

    if not re.search(
        r"\bpublic\s*\.\s*business_sales\b|\bbusiness_sales\b",
        cleaned
    ):

        return (
            False,
            "Query must reference public.business_sales."
        )

    # --------------------------------------------
    # Block system-table access except schema lookup
    # --------------------------------------------

    dangerous_system_objects = [
        "pg_catalog",
        "pg_roles",
        "pg_user",
        "pg_shadow",
        "pg_authid",
    ]

    for object_name in dangerous_system_objects:

        if object_name in cleaned:

            return (
                False,
                f"Access to {object_name} is not allowed."
            )

    return True, ""


# ============================================================
# BUSINESS SQL VALIDATION
# ============================================================

def validate_business_sql(
    sql: str
) -> tuple[bool, str]:
    """
    Validate common business-metric mistakes that a small LLM
    could otherwise make.
    """

    normalized = re.sub(
        r"\s+",
        " ",
        sql.lower()
    ).strip()

    # ========================================================
    # SALES CALCULATION PROTECTION
    # ========================================================

    invalid_sales_patterns = [
        r"unit_ordered\s*\*\s*gross_sales",
        r"gross_sales\s*\*\s*unit_ordered",
        r"gross_sales\s*/\s*unit_ordered",
    ]

    for pattern in invalid_sales_patterns:

        if re.search(
            pattern,
            normalized
        ):

            return (
                False,
                (
                    "Invalid sales calculation detected. "
                    "gross_sales is already a sales amount and "
                    "must not be multiplied or divided by "
                    "unit_ordered."
                )
            )

    # ========================================================
    # AD REVENUE CALCULATION PROTECTION
    # ========================================================

    invalid_ad_revenue_patterns = [
        r"unit_ordered\s*\*\s*ad_revenue",
        r"ad_revenue\s*\*\s*unit_ordered",
    ]

    for pattern in invalid_ad_revenue_patterns:

        if re.search(
            pattern,
            normalized
        ):

            return (
                False,
                (
                    "Invalid advertising revenue calculation. "
                    "ad_revenue is already an amount."
                )
            )

    # ========================================================
    # AD SPEND CALCULATION PROTECTION
    # ========================================================

    invalid_ad_spend_patterns = [
        r"unit_ordered\s*\*\s*ad_spend",
        r"ad_spend\s*\*\s*unit_ordered",
    ]

    for pattern in invalid_ad_spend_patterns:

        if re.search(
            pattern,
            normalized
        ):

            return (
                False,
                (
                    "Invalid advertising spend calculation. "
                    "ad_spend is already an amount."
                )
            )

    # ========================================================
    # ORGANIC SALES CALCULATION PROTECTION
    # ========================================================

    invalid_organic_patterns = [
        r"unit_ordered\s*\*\s*organic_sale",
        r"organic_sale\s*\*\s*unit_ordered",
    ]

    for pattern in invalid_organic_patterns:

        if re.search(
            pattern,
            normalized
        ):

            return (
                False,
                (
                    "Invalid organic sales calculation. "
                    "organic_sale is already an amount."
                )
            )

    # ========================================================
    # ROAS AGGREGATION WARNING / PROTECTION
    # ========================================================

    if re.search(
        r"sum\s*\(\s*roas_standard\s*\)",
        normalized
    ):

        return (
            False,
            (
                "Do not SUM(roas_standard) for aggregate ROAS. "
                "Calculate it as "
                "SUM(ad_revenue) / NULLIF(SUM(ad_spend), 0)."
            )
        )

    if re.search(
        r"sum\s*\(\s*roas_percentage\s*\)",
        normalized
    ):

        return (
            False,
            (
                "Do not SUM(roas_percentage) for aggregate ROAS."
            )
        )

    # ========================================================
    # RATE-METRIC AGGREGATION PROTECTION
    # ========================================================

    invalid_rate_aggregations = {
        "cvr": (
            "Do not SUM(cvr) for aggregate conversion rate. "
            "Use the underlying ad_orders and ad_units/click "
            "logic when an aggregate conversion rate is required."
        ),
        "ctr": (
            "Do not SUM(ctr) for aggregate click-through rate. "
            "Use aggregated clicks divided by aggregated impressions."
        ),
        "cpc": (
            "Do not SUM(cpc) for aggregate cost per click. "
            "Use aggregated ad spend divided by aggregated clicks."
        ),
        "tacos": (
            "Do not SUM(tacos) for aggregate TACOS. "
            "Calculate SUM(ad_spend) / NULLIF(SUM(gross_sales), 0) * 100."
        ),
        "acos": (
            "Do not SUM(acos) for aggregate ACOS. "
            "Calculate SUM(ad_spend) / NULLIF(SUM(ad_revenue), 0) * 100 "
            "when ACOS is defined against ad revenue."
        ),
    }

    for metric, message in invalid_rate_aggregations.items():

        pattern = rf"sum\s*\(\s*{re.escape(metric)}\s*\)"

        if re.search(
            pattern,
            normalized
        ):

            return (
                False,
                message
            )

    # ========================================================
    # PARTIAL DATE PROTECTION
    # ========================================================

    # Reject bare YYYY-MM values used as DATE comparisons.
    partial_date_comparison_patterns = [
        r"\byear_month\s*(?:>=|<=|=|>|<)\s*'20\d{2}-\d{2}'",
        r"\byear_month\s+between\s*'20\d{2}-\d{2}'",
        r"\band\s+year_month\s*(?:>=|<=|=|>|<)\s*'20\d{2}-\d{2}'",
    ]

    for pattern in partial_date_comparison_patterns:

        if re.search(
            pattern,
            normalized
        ):

            return (
                False,
                (
                    "Invalid partial DATE filter detected. "
                    "year_month is a PostgreSQL DATE. "
                    "Use complete dates such as DATE '2026-01-01' "
                    "and DATE '2027-01-01'."
                )
            )

    # ========================================================
    # FAKE / MEANINGLESS CLASSIFICATION PROTECTION
    # ========================================================

    fake_label_patterns = [
        r"""['"]yeah['"]""",
        r"""['"]yep['"]""",
        r"""['"]nope['"]""",
        r"""['"]nah['"]""",
        r"""['"]good['"]""",
        r"""['"]bad['"]""",
        r"""['"]maybe['"]""",
        r"""['"]unknown['"]""",
    ]

    for pattern in fake_label_patterns:

        if re.search(
            pattern,
            normalized
        ):

            return (
                False,
                (
                    "Unsupported arbitrary classification detected. "
                    "Generated SQL must use measurable business "
                    "metrics rather than labels such as YEAH/NOPE."
                )
            )

    return True, ""


# ============================================================
# COMBINED VALIDATION
# ============================================================

def validate_generated_sql(
    sql: str
) -> tuple[bool, str]:
    """
    Run all SQL validators.
    """

    valid, reason = validate_sql(
        sql
    )

    if not valid:
        return False, reason

    valid, reason = validate_business_sql(
        sql
    )

    if not valid:
        return False, reason

    return True, ""


# ============================================================
# SQL EXECUTION
# ============================================================

def execute_sql(
    sql: str
) -> list[dict[str, Any]]:
    """
    Execute a validated read-only SQL query.
    """

    valid, reason = validate_generated_sql(
        sql
    )

    if not valid:

        raise ValueError(
            f"SQL validation failed: {reason}"
        )

    # --------------------------------------------
    # Execute validated query
    # --------------------------------------------

    query = text(
        sql
    )

    with engine.connect() as connection:

        result = connection.execute(
            query
        )

        rows = result.mappings().fetchall()

    # --------------------------------------------
    # Prevent enormous result payloads
    # --------------------------------------------

    MAX_RESULT_ROWS = 200

    if len(rows) > MAX_RESULT_ROWS:

        rows = rows[:MAX_RESULT_ROWS]

    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# SQL GENERATION
# ============================================================

def _extract_change_period(question: str) -> tuple[date, date] | None:
    """
    Detect a specific month/year from a sales-change or "why" question.

    Examples supported:
        "Why did sales decline in May 2026?"
        "Why did sales decrease in 2026-05?"
        "Why did sales increase in May 2026?"

    Returns:
        (previous_month, target_month) when a specific month is detected,
        otherwise None.
    """

    if not question:
        return None

    normalized = question.lower().strip()

    change_terms = (
        "why did",
        "why has",
        "why have",
        "why was",
        "why were",
        "decline",
        "declined",
        "decrease",
        "decreased",
        "decreasing",
        "increase",
        "increased",
        "increasing",
        "change",
        "changed",
    )

    if not any(term in normalized for term in change_terms):
        return None

    month_lookup = {
        "jan": 1,
        "january": 1,
        "feb": 2,
        "february": 2,
        "mar": 3,
        "march": 3,
        "apr": 4,
        "april": 4,
        "may": 5,
        "jun": 6,
        "june": 6,
        "jul": 7,
        "july": 7,
        "aug": 8,
        "august": 8,
        "sep": 9,
        "sept": 9,
        "september": 9,
        "oct": 10,
        "october": 10,
        "nov": 11,
        "november": 11,
        "dec": 12,
        "december": 12,
    }

    # YYYY-MM
    iso_match = re.search(r"\b(20\d{2})[-/](0?[1-9]|1[0-2])\b", normalized)

    if iso_match:
        year = int(iso_match.group(1))
        month = int(iso_match.group(2))
    else:
        # Month name + year, e.g. May 2026 / May, 2026
        name_pattern = "|".join(
            sorted(month_lookup.keys(), key=len, reverse=True)
        )
        named_match = re.search(
            rf"\b({name_pattern})\s*,?\s*(20\d{{2}})\b",
            normalized,
            flags=re.IGNORECASE,
        )

        if not named_match:
            return None

        month = month_lookup[named_match.group(1).lower()]
        year = int(named_match.group(2))

    try:
        target_month = date(year, month, 1)
    except ValueError:
        return None

    if month == 1:
        previous_month = date(year - 1, 12, 1)
    else:
        previous_month = date(year, month - 1, 1)

    return previous_month, target_month


def build_change_analysis_sql(question: str) -> str | None:
    """
    Build a deterministic, evidence-first SQL query for questions that
    ask why sales changed in a specific month.

    This protects the application from a small local LLM returning only
    the target month's sales when a previous-period comparison is required.
    """

    periods = _extract_change_period(question)

    if periods is None:
        return None

    previous_month, target_month = periods

    previous_literal = previous_month.isoformat()
    target_literal = target_month.isoformat()

    return f"""
WITH monthly_metrics AS (
    SELECT
        year_month,
        SUM(gross_sales) AS total_sales,
        SUM(unit_ordered) AS total_units,
        SUM(ad_spend) AS total_ad_spend,
        SUM(ad_revenue) AS total_ad_revenue,
        SUM(organic_sale) AS total_organic_sales
    FROM public.business_sales
    WHERE year_month IN (
        DATE '{previous_literal}',
        DATE '{target_literal}'
    )
    GROUP BY year_month
),
comparison AS (
    SELECT
        year_month,
        total_sales,
        LAG(total_sales) OVER (ORDER BY year_month) AS previous_sales,
        total_units,
        LAG(total_units) OVER (ORDER BY year_month) AS previous_units,
        total_ad_spend,
        LAG(total_ad_spend) OVER (ORDER BY year_month) AS previous_ad_spend,
        total_ad_revenue,
        LAG(total_ad_revenue) OVER (ORDER BY year_month) AS previous_ad_revenue,
        total_organic_sales,
        LAG(total_organic_sales) OVER (ORDER BY year_month) AS previous_organic_sales
    FROM monthly_metrics
)
SELECT
    year_month,
    total_sales,
    previous_sales,
    total_sales - previous_sales AS sales_change,
    ROUND(
        100.0 * (total_sales - previous_sales)
        / NULLIF(previous_sales, 0),
        2
    ) AS sales_growth_pct,
    total_units,
    previous_units,
    total_units - previous_units AS units_change,
    ROUND(
        100.0 * (total_units - previous_units)
        / NULLIF(previous_units, 0),
        2
    ) AS units_growth_pct,
    total_ad_spend,
    previous_ad_spend,
    total_ad_spend - previous_ad_spend AS ad_spend_change,
    ROUND(
        100.0 * (total_ad_spend - previous_ad_spend)
        / NULLIF(previous_ad_spend, 0),
        2
    ) AS ad_spend_growth_pct,
    total_ad_revenue,
    previous_ad_revenue,
    total_ad_revenue - previous_ad_revenue AS ad_revenue_change,
    ROUND(
        100.0 * (total_ad_revenue - previous_ad_revenue)
        / NULLIF(previous_ad_revenue, 0),
        2
    ) AS ad_revenue_growth_pct,
    total_organic_sales,
    previous_organic_sales,
    total_organic_sales - previous_organic_sales AS organic_sales_change,
    ROUND(
        100.0 * (total_organic_sales - previous_organic_sales)
        / NULLIF(previous_organic_sales, 0),
        2
    ) AS organic_sales_growth_pct,
    total_ad_revenue / NULLIF(total_ad_spend, 0) AS roas,
    previous_ad_revenue / NULLIF(previous_ad_spend, 0) AS previous_roas,
    100.0 * total_ad_spend / NULLIF(total_sales, 0) AS tacos,
    100.0 * previous_ad_spend / NULLIF(previous_sales, 0) AS previous_tacos
FROM comparison
WHERE year_month = DATE '{target_literal}';
""".strip()


def build_country_best_why_sql(question: str) -> str | None:
    """
    Build a deterministic country-performance query for questions that ask
    which country performed best in a year and why.

    A small local LLM can produce unnecessarily complex multi-CTE SQL for
    this question and may truncate the query. This deterministic shape is
    sufficient because it returns the core country-level metrics needed for
    a grounded comparison.
    """

    if not question:
        return None

    normalized = question.lower().strip()

    best_country_patterns = (
        "which country performed best",
        "what country performed best",
        "best country",
        "top country",
    )

    why_patterns = (
        "why",
        "because",
        "reason",
        "why did",
        "why was",
    )

    if not any(pattern in normalized for pattern in best_country_patterns):
        return None

    if not any(pattern in normalized for pattern in why_patterns):
        return None

    year_match = re.search(r"\b(20\d{2})\b", normalized)
    if year_match:
        year = int(year_match.group(1))
    else:
        return None

    next_year = year + 1

    return f"""
SELECT
    country,
    SUM(gross_sales) AS total_sales,
    SUM(unit_ordered) AS total_units,
    SUM(ad_spend) AS total_ad_spend,
    SUM(ad_revenue) AS total_ad_revenue,
    SUM(organic_sale) AS total_organic_sales,
    SUM(ad_revenue) / NULLIF(SUM(ad_spend), 0) AS roas,
    100.0 * SUM(ad_spend) / NULLIF(SUM(gross_sales), 0) AS tacos,
    100.0 * SUM(organic_sale) / NULLIF(SUM(gross_sales), 0) AS organic_pct
FROM public.business_sales
WHERE year_month >= DATE '{year}-01-01'
  AND year_month < DATE '{next_year}-01-01'
  AND country IS NOT NULL
GROUP BY country
ORDER BY total_sales DESC;
""".strip()


def generate_sql(
    question: str,
    repair_context: str | None = None
) -> str:
    """
    Ask the local Hugging Face LLM to generate SQL.
    """

    # ------------------------------------------------------------
    # Deterministic protection for country-ranking "why" questions
    # ------------------------------------------------------------
    protected_country_sql = build_country_best_why_sql(question)

    if protected_country_sql is not None:
        return protected_country_sql

    schema_text = build_schema_text()

    repair_section = ""

    if repair_context:

        repair_section = f"""
PREVIOUS SQL ERROR:

{repair_context}

You MUST correct the problem in your new SQL.
Do not repeat the same mistake.
"""

    prompt = f"""
You are a PostgreSQL analytics engineer working as part of
a private, LOCAL AI Business Analyst application.

Your task is to generate ONE accurate, read-only PostgreSQL
query that answers the user's business question.

The business database is:

public.business_sales

DATABASE SCHEMA:

{schema_text}

USER QUESTION:

{question}

{repair_section}

============================================================
BUSINESS SEMANTICS
============================================================

The following definitions are authoritative.

1. gross_sales is ALREADY the sales/revenue amount for each
   database row.

   Correct:
       SUM(gross_sales)

   Incorrect:
       SUM(unit_ordered * gross_sales)

2. NEVER multiply gross_sales by unit_ordered.

3. unit_ordered is the number of units.

   Correct:
       SUM(unit_ordered)

4. ad_spend is already the advertising spend amount.

   Correct:
       SUM(ad_spend)

5. ad_revenue is already advertising-attributed revenue.

   Correct:
       SUM(ad_revenue)

6. organic_sale is already the organic sales amount.

   Correct:
       SUM(organic_sale)

7. For aggregate standard ROAS:

       SUM(ad_revenue) / NULLIF(SUM(ad_spend), 0)

8. Do NOT use:

       SUM(roas_standard)

   to calculate overall ROAS.

9. Do NOT use:

       SUM(roas_percentage)

   to calculate overall ROAS.

10. For "sales", use gross_sales unless the user explicitly
    asks for ad revenue or organic sales.

11. For product rankings:

       GROUP BY sku
       ORDER BY SUM(gross_sales) DESC

12. For country rankings:

       GROUP BY country
       ORDER BY SUM(gross_sales) DESC

13. year_month is a PostgreSQL DATE representing the FIRST DAY
    of each month.

14. For a full year, always use complete DATE values.

    Correct example for 2026:

       year_month >= DATE '2026-01-01'
       AND year_month < DATE '2027-01-01'

    Incorrect:

       year_month >= '2026-01'
       AND year_month <= '2026-12'

15. For a specific month, use a complete DATE.

    Correct:

       year_month = DATE '2026-05-01'

16. Never compare year_month with partial dates such as:

       '2026-01'
       '2026-05'
       '2026-12'

17. When the user asks for month-over-month analysis,
    prefer LAG() or an explicit previous-period comparison.

18. When the user asks why sales changed, decreased, or increased,
    the query MUST compare the affected period with the immediately
    previous comparable period.

    For example:

       "Why did sales decline in May 2026?"

    MUST retrieve enough data to compare:

       April 2026 vs May 2026

    The result MUST contain, when applicable:

       - current sales
       - previous sales
       - sales change
       - sales growth percentage
       - current and previous units
       - current and previous ad_spend
       - current and previous ad_revenue
       - current and previous organic_sales
       - current and previous ROAS
       - current and previous TACOS

    Prefer LAG() or an explicit previous-period comparison.
    A query containing only the affected month's sales is NOT a
    complete answer to a "why did sales change" question.

19. For "why" questions, do not invent a cause.

    Only return metrics that can provide evidence for a
    possible explanation. A metric moving at the same time does
    not by itself prove causation.

20. Never create arbitrary classifications such as:

       YEAH
       NOPE
       GOOD
       BAD
       YEP
       NAH

    unless the user explicitly requests such labels.

21. Do not create meaningless columns simply to make the query
    look analytical.

22. Rate metrics must not be summed directly.

    Do NOT use:

       SUM(cvr)
       SUM(ctr)
       SUM(cpc)
       SUM(tacos)
       SUM(acos)

23. When aggregate CTR is required:

       SUM(click) / NULLIF(SUM(impression), 0) * 100

24. When aggregate CPC is required:

       SUM(ad_spend) / NULLIF(SUM(click), 0)

25. When aggregate TACOS is required:

       SUM(ad_spend) / NULLIF(SUM(gross_sales), 0) * 100

26. When aggregate ACOS is requested against ad revenue:

       SUM(ad_spend) / NULLIF(SUM(ad_revenue), 0) * 100

27. Do not calculate business conclusions inside arbitrary
    CASE statements unless the conditions are directly supported
    by measurable database values.

28. Use the user's requested filters exactly.

============================================================
SQL SAFETY
============================================================

1. Generate ONLY one SQL SELECT query or WITH query.
2. Query ONLY public.business_sales.
3. Never use INSERT.
4. Never use UPDATE.
5. Never use DELETE.
6. Never use DROP.
7. Never use ALTER.
8. Never use TRUNCATE.
9. Never use CREATE.
10. Never use GRANT.
11. Never use REVOKE.
12. Never access pg_catalog or user/security tables.
13. Never invent column names.
14. Use only columns in the supplied schema.
15. Do not generate multiple SQL statements.
16. Do not explain the SQL.
17. Return ONLY the SQL query.

============================================================
SELF-CHECK BEFORE RETURNING SQL
============================================================

Before returning your query, verify:

- Is gross_sales being summed directly?
- Did I accidentally multiply sales by units?
- Am I using the correct column for the user's question?
- If calculating ROAS, am I using aggregated ad revenue
  divided by aggregated ad spend?
- If calculating TACOS, am I using aggregated ad spend divided
  by aggregated gross sales?
- If calculating CTR, am I using aggregated clicks divided by
  aggregated impressions?
- If calculating CPC, am I using aggregated ad spend divided by
  aggregated clicks?
- Are the requested filters applied correctly?
- Are all year_month comparisons using complete PostgreSQL DATE values?
- Did I avoid partial dates such as '2026-01'?
- Did I avoid SUM(cvr), SUM(ctr), SUM(cpc), SUM(tacos), and SUM(acos)?
- Did I avoid fake YEAH/NOPE style labels?
- Does every column actually exist?
- Does the query reference public.business_sales?
- Is the query read-only?
- Does the query actually answer the user's question?

Return ONLY the SQL.
"""

    response = generate_response(
        prompt,
        max_new_tokens=400
    )

    sql = extract_sql(
        response
    )

    # ------------------------------------------------------------
    # Deterministic protection for specific-month change questions
    # ------------------------------------------------------------
    # A small local model can follow the date rule but still return
    # only the affected month. For a "why did sales change" question,
    # that query is analytically incomplete because it has no baseline.
    # When a specific month is detectable, use the trusted comparison
    # shape above so the answer always has a previous-period baseline.
    protected_change_sql = build_change_analysis_sql(question)

    if protected_change_sql is not None:
        sql = protected_change_sql

    return sql.strip()


# ============================================================
# SQL REPAIR
# ============================================================

def repair_sql(
    question: str,
    bad_sql: str,
    error_message: str
) -> str:
    """
    Ask the local LLM to repair invalid SQL.
    """

    schema_text = build_schema_text()

    prompt = f"""
You are a PostgreSQL SQL repair engine.

USER QUESTION:

{question}

DATABASE TABLE:

public.business_sales

DATABASE SCHEMA:

{schema_text}

INVALID SQL:

{bad_sql}

VALIDATION ERROR:

{error_message}

Repair the SQL.

============================================================
BUSINESS RULES
============================================================

- gross_sales is already a sales amount.
- NEVER multiply gross_sales by unit_ordered.
- unit_ordered is already the unit count.
- ad_spend is already the ad spend amount.
- ad_revenue is already the ad revenue amount.
- organic_sale is already the organic sales amount.

Aggregate standard ROAS:

    SUM(ad_revenue) / NULLIF(SUM(ad_spend), 0)

Do not SUM(roas_standard).
Do not SUM(roas_percentage).

For aggregate TACOS:

    SUM(ad_spend) / NULLIF(SUM(gross_sales), 0) * 100

For aggregate CTR:

    SUM(click) / NULLIF(SUM(impression), 0) * 100

For aggregate CPC:

    SUM(ad_spend) / NULLIF(SUM(click), 0)

Do not SUM(cvr).
Do not SUM(ctr).
Do not SUM(cpc).
Do not SUM(tacos).
Do not SUM(acos).

============================================================
DATE RULES
============================================================

year_month is a PostgreSQL DATE representing the first day
of each month.

For a full year such as 2026:

    year_month >= DATE '2026-01-01'
    AND year_month < DATE '2027-01-01'

For a specific month such as May 2026:

    year_month = DATE '2026-05-01'

NEVER use:

    '2026-01'
    '2026-05'
    '2026-12'

for direct DATE comparisons.

============================================================
ANALYTICAL QUALITY RULES
============================================================

- Do not create fake labels such as YEAH or NOPE.
- Do not create meaningless CASE statements.
- Do not invent causes.
- For month-over-month questions, use explicit previous-period
  comparisons or LAG().
- For sales-change questions, compare the affected period with the
  immediately previous comparable period.
- Return current value, previous value, absolute change, and
  percentage change for the primary metric.
- For "why" sales questions, include supporting metrics such as
  units, ad_spend, ad_revenue, organic_sales, ROAS, and TACOS when
  they are relevant to the question.
- Never answer a "why did sales change" question with only the
  affected month's sales.

============================================================
SAFETY
============================================================

- Only public.business_sales.
- Only SELECT / WITH queries.
- Never modify data.
- Never access system/security tables.
- Never generate multiple SQL statements.
- Return ONLY the corrected SQL query.
"""

    response = generate_response(
        prompt,
        max_new_tokens=400
    )

    return extract_sql(
        response
    ).strip()


# ============================================================
# BUSINESS ANSWER GENERATION
# ============================================================

def generate_business_answer(
    question: str,
    sql: str,
    result: list[dict[str, Any]]
) -> str:
    """
    Turn validated database results into a grounded business answer.

    For analytical comparison questions, especially WHY / DECLINE /
    INCREASE questions, use deterministic formatting for the factual
    portion so the small local model cannot change numbers, periods,
    or metric direction.
    """

    result_text = json.dumps(
        result,
        indent=2,
        default=str
    )

    # ------------------------------------------------------------
    # No-result handling
    # ------------------------------------------------------------

    if not result:
        return (
            "Key findings:\n\n"
            "- The SQL query returned no matching records.\n\n"
            "Business interpretation:\n\n"
            "- No conclusion can be drawn because the query returned no data.\n\n"
            "Recommendation:\n\n"
            "- No specific recommendation can be made from this result alone."
        )

    # ------------------------------------------------------------
    # Helpers for safe numeric formatting
    # ------------------------------------------------------------

    def _to_float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _money(value: Any) -> str:
        number = _to_float(value)
        if number is None:
            return "N/A"
        return f"${number:,.2f}"

    def _number(value: Any) -> str:
        number = _to_float(value)
        if number is None:
            return "N/A"
        if number.is_integer():
            return f"{int(number):,}"
        return f"{number:,.2f}"

    def _pct(value: Any) -> str:
        number = _to_float(value)
        if number is None:
            return "N/A"
        return f"{number:,.2f}%"

    def _x(value: Any) -> str:
        number = _to_float(value)
        if number is None:
            return "N/A"
        return f"{number:,.2f}x"

    def _period(value: Any) -> str:
        if value is None:
            return "N/A"
        text_value = str(value)
        if len(text_value) >= 10 and text_value[4] == "-":
            try:
                year_value = int(text_value[:4])
                month_value = int(text_value[5:7])
                month_names = [
                    "January", "February", "March", "April",
                    "May", "June", "July", "August",
                    "September", "October", "November", "December"
                ]
                if 1 <= month_value <= 12:
                    return f"{month_names[month_value - 1]} {year_value}"
            except (TypeError, ValueError):
                pass
        return text_value

    # Normalize the question once before any deterministic
    # question-routing logic uses it.
    normalized_question = re.sub(r"\s+", " ", question.lower()).strip()


    # ------------------------------------------------------------
    # COUNTRY "BEST + WHY" QUESTIONS
    # ------------------------------------------------------------
    # These are answered deterministically from the returned SQL rows.
    # The local LLM must not rewrite country values or monetary amounts.
    # ------------------------------------------------------------

    country_best_why_question = (
        "which country performed best" in normalized_question
        or "what country performed best" in normalized_question
        or "best country" in normalized_question
        or "top country" in normalized_question
    ) and any(
        phrase in normalized_question
        for phrase in (
            "why",
            "because",
            "reason",
            "why did",
            "why was",
        )
    )

    if country_best_why_question and result and all(
        isinstance(row, dict) for row in result
    ):
        country_rows = [
            row for row in result
            if row.get("country") is not None
        ]

        if country_rows and all(
            key in country_rows[0]
            for key in (
                "country",
                "total_sales",
            )
        ):
            best_row = country_rows[0]

            best_country = str(
                best_row.get("country")
            ).strip()

            best_sales = _money(
                best_row.get("total_sales")
            )

            best_units = _number(
                best_row.get("total_units")
            ) if "total_units" in best_row else None

            best_ad_spend = _money(
                best_row.get("total_ad_spend")
            ) if "total_ad_spend" in best_row else None

            best_ad_revenue = _money(
                best_row.get("total_ad_revenue")
            ) if "total_ad_revenue" in best_row else None

            best_roas = _x(
                best_row.get("roas")
            ) if "roas" in best_row else None

            best_tacos = _pct(
                best_row.get("tacos")
            ) if "tacos" in best_row else None

            best_organic_pct = _pct(
                best_row.get("organic_pct")
            ) if "organic_pct" in best_row else None

            lines = [
                "Key findings:",
                "",
                f"- {best_country} was the top-performing country by total sales, "
                f"with {best_sales}.",
            ]

            if best_units is not None:
                lines.append(
                    f"- Units sold: {best_units}."
                )

            if best_roas is not None:
                lines.append(
                    f"- ROAS: {best_roas}."
                )

            if best_tacos is not None:
                lines.append(
                    f"- TACOS: {best_tacos}."
                )

            if best_ad_spend is not None:
                lines.append(
                    f"- Ad spend: {best_ad_spend}."
                )

            if best_ad_revenue is not None:
                lines.append(
                    f"- Ad revenue: {best_ad_revenue}."
                )

            if best_organic_pct is not None:
                lines.append(
                    f"- Organic sales share: {best_organic_pct}."
                )

            if len(country_rows) > 1:
                second_row = country_rows[1]

                second_country = str(
                    second_row.get("country")
                ).strip()

                second_sales = _money(
                    second_row.get("total_sales")
                )

                second_roas = (
                    _x(second_row.get("roas"))
                    if "roas" in second_row
                    else None
                )

                second_tacos = (
                    _pct(second_row.get("tacos"))
                    if "tacos" in second_row
                    else None
                )

                lines.extend([
                    "",
                    "Business interpretation:",
                    "",
                    f"- {best_country} ranked first on total sales, ahead of "
                    f"{second_country} at {second_sales}.",
                ])

                if second_roas is not None and second_tacos is not None:
                    lines.append(
                        f"- Its advertising efficiency was also reflected in "
                        f"ROAS of {best_roas} and TACOS of {best_tacos}, "
                        f"versus {second_country} at ROAS {second_roas} "
                        f"and TACOS {second_tacos}."
                    )
                else:
                    lines.append(
                        "- The supporting metrics above describe the observed "
                        "performance; they do not establish causation."
                    )
            else:
                lines.extend([
                    "",
                    "Business interpretation:",
                    "",
                    "- The returned metrics describe observed performance "
                    "and do not establish a causal explanation."
                ])

            lines.extend([
                "",
                "Recommendation:",
                "",
                "- No specific recommendation can be made from this result alone."
            ])

            return "\n".join(lines)

    # ------------------------------------------------------------
    # WHY / DECLINE / INCREASE / CHANGE QUESTIONS
    # ------------------------------------------------------------
    # These are handled deterministically when the SQL returned the
    # comparison fields. This prevents Qwen from changing metric values
    # or inventing a causal explanation.
    # ------------------------------------------------------------

    normalized_question = re.sub(r"\s+", " ", question.lower()).strip()
    comparison_question = any(
        phrase in normalized_question
        for phrase in (
            "why did sales decline",
            "why did sales decrease",
            "why did sales increase",
            "why did sales change",
            "why did revenue decline",
            "why did revenue decrease",
            "why did revenue increase",
            "why did revenue change",
            "sales decline",
            "sales decrease",
            "sales increase",
            "sales change",
            "revenue decline",
            "revenue decrease",
            "revenue increase",
            "revenue change",
        )
    )

    if comparison_question and len(result) == 1:
        row = result[0]

        required_fields = {
            "year_month",
            "total_sales",
            "previous_sales",
            "sales_change",
            "sales_growth_pct",
        }

        if required_fields.issubset(row.keys()):
            current_period = _period(row.get("year_month"))
            total_sales = _money(row.get("total_sales"))
            previous_sales = _money(row.get("previous_sales"))
            sales_change_value = _to_float(row.get("sales_change"))
            sales_growth_value = _to_float(row.get("sales_growth_pct"))

            direction = "increased"
            if sales_change_value is not None and sales_change_value < 0:
                direction = "declined"
            elif sales_change_value is not None and sales_change_value == 0:
                direction = "remained unchanged"

            if sales_growth_value is not None:
                growth_text = _pct(abs(sales_growth_value))
            else:
                growth_text = "N/A"

            if sales_change_value is not None:
                absolute_change_text = _money(abs(sales_change_value))
            else:
                absolute_change_text = "N/A"

            lines = [
                "Key findings:",
                "",
                f"- Sales {direction} in {current_period} from {previous_sales} "
                f"to {total_sales}.",
                f"- The absolute change was {absolute_change_text}.",
            ]

            if sales_growth_value is not None:
                if sales_growth_value < 0:
                    lines.append(f"- Sales decreased by {growth_text} month-over-month.")
                elif sales_growth_value > 0:
                    lines.append(f"- Sales increased by {growth_text} month-over-month.")
                else:
                    lines.append("- Sales were unchanged month-over-month.")

            # Supporting metrics are observations only.
            support_fields = [
                (
                    "total_units",
                    "previous_units",
                    "units_growth_pct",
                    "Units",
                    _number,
                    _number,
                ),
                (
                    "total_ad_spend",
                    "previous_ad_spend",
                    "ad_spend_growth_pct",
                    "Ad spend",
                    _money,
                    _money,
                ),
                (
                    "total_ad_revenue",
                    "previous_ad_revenue",
                    "ad_revenue_growth_pct",
                    "Ad revenue",
                    _money,
                    _money,
                ),
                (
                    "total_organic_sales",
                    "previous_organic_sales",
                    "organic_sales_growth_pct",
                    "Organic sales",
                    _money,
                    _money,
                ),
            ]

            for current_key, previous_key, pct_key, label, current_fmt, previous_fmt in support_fields:
                if current_key in row and previous_key in row:
                    current_value = row.get(current_key)
                    previous_value = row.get(previous_key)
                    pct_value = _to_float(row.get(pct_key)) if pct_key in row else None

                    if current_value is not None and previous_value is not None:
                        if pct_value is not None:
                            change_word = "decreased" if pct_value < 0 else "increased" if pct_value > 0 else "was unchanged"
                            if change_word == "was unchanged":
                                lines.append(
                                    f"- {label} was unchanged at {current_fmt(current_value)}."
                                )
                            else:
                                lines.append(
                                    f"- {label} {change_word} from "
                                    f"{previous_fmt(previous_value)} to {current_fmt(current_value)} "
                                    f"({abs(pct_value):,.2f}% {'decrease' if pct_value < 0 else 'increase'})."
                                )

            # ROAS / TACOS are also observations, with correct current and
            # previous values taken directly from the database result.
            if "roas" in row and "previous_roas" in row:
                lines.append(
                    f"- ROAS was {_x(row.get('roas'))} in {current_period}, "
                    f"compared with {_x(row.get('previous_roas'))} in the previous month."
                )

            if "tacos" in row and "previous_tacos" in row:
                lines.append(
                    f"- TACOS was {_pct(row.get('tacos'))} in {current_period}, "
                    f"compared with {_pct(row.get('previous_tacos'))} in the previous month."
                )

            lines.extend([
                "",
                "Business interpretation:",
                "",
                "- The database result confirms the month-over-month sales change.",
                "- The supporting metrics above show which business metrics also changed "
                "during the same comparison period.",
                "- These movements are observations and do not by themselves establish "
                "that any one metric caused the sales change.",
                "- The available data confirms the change but does not establish a definitive cause.",
                "",
                "Recommendation:",
                "",
                "- No specific recommendation can be made from this result alone.",
            ])

            return "\n".join(lines)

    # ------------------------------------------------------------
    # GENERAL RESULT ANSWERING
    # ------------------------------------------------------------

    prompt = f"""
You are a highly reliable AI Business Analyst operating entirely
on a LOCAL model.

USER QUESTION:

{question}

SQL QUERY EXECUTED:

{sql}

AUTHORITATIVE DATABASE RESULT:

{result_text}

============================================================
STRICT GROUNDING RULES
============================================================

1. Use ONLY information present in the database result.
2. Never invent numbers.
3. Never invent SKUs, countries, dates, or months.
4. Never invent additional KPIs.
5. Never claim causation unless the result directly establishes it.
6. Never claim growth or decline unless the result contains the
   required comparison.
7. Never claim customer behavior, market conditions, operational
   problems, or business causes without direct evidence.
8. Never contradict a value in the database result.
9. Do not reinterpret a metric or swap current and previous values.
10. Do not perform mental calculations that change or replace the
    database values.
11. If the result is insufficient to answer part of the question,
    explicitly say so.
12. Numerical accuracy is more important than sounding confident.
13. Do not add recommendations unless the evidence supports them.
14. Do not make future predictions unless forecast data appears in
    the result.
15. Do not use generic filler such as "ongoing operational issues",
    "market conditions", "customer behavior", "general downward trend",
    or "business challenges" unless explicitly supported.

============================================================
RANKING / FACTUAL QUESTION RULES
============================================================

If the user asks for highest, lowest, top, bottom, best, worst,
or a ranking:

- Report the values exactly from the result.
- Do not add unsupported growth claims.
- Do not say a country/product is "driving growth" unless growth
  was actually returned.
- Do not invent recommendations.

============================================================
RESPONSE FORMAT
============================================================

Key findings:
- State the verified result directly.

Business interpretation:
- Explain only what the returned evidence supports.

Recommendation:
- Give one only when directly supported.
- Otherwise say:
  "No specific recommendation can be made from this result alone."

Return a concise, factual answer.
"""

    return generate_response(
        prompt,
        max_new_tokens=350
    )


# ============================================================
# DYNAMIC SQL AGENT
# ============================================================

def answer_dynamic_question(
    question: str,
    max_retries: int = 2
) -> str:
    """
    End-to-end dynamic business question answering.

    Flow:

        Question
            ↓
        Local Qwen
            ↓
        SQL generation
            ↓
        SQL validation
            ↓
        SQL repair if needed
            ↓
        Supabase PostgreSQL
            ↓
        Query result
            ↓
        Local Qwen
            ↓
        Business answer
    """

    if not question or not question.strip():

        raise ValueError(
            "Business question cannot be empty."
        )

    question = question.strip()

    print()
    print("=" * 70)
    print("DYNAMIC SQL AGENT")
    print("=" * 70)

    # ========================================================
    # STEP 1 — GENERATE SQL
    # ========================================================

    print()
    print("Generating SQL...")

    sql = generate_sql(
        question
    )

    print()
    print("Generated SQL:")
    print(sql)

    # ========================================================
    # STEP 2 — VALIDATE / REPAIR
    # ========================================================

    for attempt in range(
        max_retries + 1
    ):

        valid, reason = (
            validate_generated_sql(
                sql
            )
        )

        if valid:

            print()
            print(
                "✓ SQL validation passed"
            )

            break

        print()
        print(
            f"✗ SQL validation failed "
            f"(attempt {attempt + 1}/{max_retries + 1})"
        )

        print(
            f"Reason: {reason}"
        )

        # --------------------------------------------
        # No more retries
        # --------------------------------------------

        if attempt >= max_retries:

            raise ValueError(
                f"Unable to generate valid SQL after "
                f"{max_retries + 1} attempts. "
                f"Last error: {reason}"
            )

        # --------------------------------------------
        # Repair SQL
        # --------------------------------------------

        print()
        print(
            "Repairing SQL..."
        )

        sql = repair_sql(
            question=question,
            bad_sql=sql,
            error_message=reason
        )

        print()
        print(
            "Repaired SQL:"
        )

        print(sql)

    else:

        raise ValueError(
            "SQL generation loop ended unexpectedly."
        )

    # ========================================================
    # STEP 3 — EXECUTE SQL
    # ========================================================

    print()
    print(
        "Executing query..."
    )

    result = execute_sql(
        sql
    )

    print(
        f"✓ Query returned {len(result)} rows"
    )

    # ========================================================
    # STEP 4 — DISPLAY SMALL RESULT PREVIEW
    # ========================================================

    if result:

        print()
        print(
            "Query result preview:"
        )

        preview = result[:10]

        for row in preview:

            print(row)

        if len(result) > 10:

            print(
                f"... showing first 10 of "
                f"{len(result)} returned rows"
            )

    # ========================================================
    # STEP 5 — GENERATE GROUNDED ANSWER
    # ========================================================

    print()
    print(
        "Generating business answer..."
    )

    answer = generate_business_answer(
        question=question,
        sql=sql,
        result=result
    )

    return answer


# ============================================================
# COMMAND-LINE TEST
# ============================================================

def main():
    """
    Run the dynamic SQL agent interactively.
    """

    print()
    print("=" * 70)
    print("LOCAL AI BUSINESS ANALYST")
    print("Hugging Face / Qwen + Supabase")
    print("=" * 70)

    print()
    print(
        "Database : Supabase PostgreSQL"
    )

    print(
        "LLM      : Local Hugging Face model"
    )

    print(
        "Table    : public.business_sales"
    )

    print()
    print(
        "Ask a business question."
    )

    print(
        "Type 'exit' to quit."
    )

    while True:

        print()

        question = input(
            "Ask a business question: "
        ).strip()

        if question.lower() in {
            "exit",
            "quit",
            "q"
        }:

            print()
            print(
                "Agent stopped."
            )

            break

        if not question:

            print(
                "Please enter a business question."
            )

            continue

        try:

            answer = answer_dynamic_question(
                question
            )

            print()
            print("=" * 70)
            print(
                "AI BUSINESS ANSWER"
            )
            print("=" * 70)

            print(
                answer
            )

            print()

        except Exception as error:

            print()
            print("=" * 70)
            print(
                "ERROR"
            )
            print("=" * 70)

            print(
                type(error).__name__,
                str(error)
            )

            print()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()