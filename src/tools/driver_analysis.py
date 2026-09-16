from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
import re
import sys
from typing import Any

from sqlalchemy import text


# ============================================================
# PROJECT PATH
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))


from src.database.connection import engine


# ============================================================
# CONFIGURATION
# ============================================================

TABLE_NAME = "business_sales"

ALLOWED_COUNTRIES = {
    "IN",
    "US",
    "DE",
    "UK",
    "CA",
    "AE",
}


# ============================================================
# DATABASE HELPER
# ============================================================

def fetch_all(query, params=None):
    """
    Execute a read-only SQL query and return all rows.
    """

    with engine.connect() as connection:
        result = connection.execute(
            query,
            params or {}
        )

        return result.fetchall()


# ============================================================
# INPUT VALIDATION
# ============================================================

def validate_year(year: int | None) -> int | None:
    """
    Validate an optional calendar year.
    """

    if year is None:
        return None

    try:
        year = int(year)
    except (TypeError, ValueError):
        raise ValueError("Year must be an integer.")

    if year < 2000 or year > 2100:
        raise ValueError(
            "Year must be between 2000 and 2100."
        )

    return year


def validate_month(month: str) -> str:
    """
    Validate a YYYY-MM month string.
    """

    month = str(month).strip()

    if not re.match(r"^\d{4}-\d{2}$", month):
        raise ValueError(
            "Month must use YYYY-MM format."
        )

    year_part = int(month[:4])
    month_part = int(month[5:7])

    if year_part < 2000 or year_part > 2100:
        raise ValueError(
            "Month year must be between 2000 and 2100."
        )

    if month_part < 1 or month_part > 12:
        raise ValueError(
            "Month must be between 01 and 12."
        )

    return month


def validate_country(country: str | None) -> str | None:
    """
    Validate an optional country code.
    """

    if country is None:
        return None

    country = str(country).strip().upper()

    if country not in ALLOWED_COUNTRIES:
        raise ValueError(
            f"Unsupported country code: {country}"
        )

    return country


def previous_month(month: str) -> str:
    """
    Return the immediately previous calendar month.

    Example:
        2026-05 -> 2026-04
        2026-01 -> 2025-12
    """

    month = validate_month(month)

    year = int(month[:4])
    month_number = int(month[5:7])

    if month_number == 1:
        year -= 1
        month_number = 12
    else:
        month_number -= 1

    return f"{year:04d}-{month_number:02d}"


# ============================================================
# GENERIC CONTRIBUTION CALCULATOR
# ============================================================

def _calculate_contribution(
    current_sales: float,
    previous_sales: float,
    total_current_sales: float,
    total_previous_sales: float,
) -> dict[str, Any]:
    """
    Calculate how much a segment contributed to the total
    month-over-month sales change.

    Contribution is measured against the total sales change:

        segment_change / total_sales_change * 100

    A positive contribution percentage means the segment added
    to the overall change.

    A negative contribution percentage means the segment moved
    opposite to the overall change.

    For example, during a total sales decline:
        - negative segment change -> positive decline contribution
        - positive segment change -> negative decline contribution
    """

    sales_change = current_sales - previous_sales
    total_change = total_current_sales - total_previous_sales

    sales_change_pct = None
    if previous_sales != 0:
        sales_change_pct = (
            sales_change / abs(previous_sales)
        ) * 100

    contribution_pct = None
    if total_change != 0:
        contribution_pct = (
            sales_change / total_change
        ) * 100

    return {
        "current_sales": current_sales,
        "previous_sales": previous_sales,
        "sales_change": sales_change,
        "sales_change_pct": sales_change_pct,
        "contribution_pct": contribution_pct,
    }


# ============================================================
# MONTH-OVER-MONTH TOTAL SALES
# ============================================================

def sales_change_summary(
    month: str,
    country: str | None = None,
) -> dict[str, Any]:
    """
    Calculate the total month-over-month sales change.

    Example:
        May 2026 -> compares April 2026 vs May 2026.

    Optional:
        country -> restrict analysis to one country.
    """

    month = validate_month(month)
    country = validate_country(country)

    previous = previous_month(month)

    conditions = [
        "year_month IN (:previous_month, :current_month)"
    ]

    params = {
        "previous_month": f"{previous}-01",
        "current_month": f"{month}-01",
    }

    if country:
        conditions.append(
            "country = :country"
        )
        params["country"] = country

    where_clause = (
        "WHERE "
        + " AND ".join(conditions)
    )

    query = text(
        f"""
        SELECT
            year_month,
            SUM(gross_sales) AS sales,
            SUM(unit_ordered) AS units,
            SUM(ad_spend) AS ad_spend,
            SUM(ad_revenue) AS ad_revenue,
            SUM(organic_sale) AS organic_sales
        FROM {TABLE_NAME}
        {where_clause}
        GROUP BY year_month
        ORDER BY year_month;
        """
    )

    rows = fetch_all(
        query,
        params
    )

    by_month = {}

    for raw_row in rows:
        if hasattr(raw_row, "_mapping"):
            row = dict(raw_row._mapping)
        else:
            row = dict(raw_row)

        by_month[str(row["year_month"])[:7]] = {
            "sales": float(row["sales"] or 0),
            "units": float(row["units"] or 0),
            "ad_spend": float(row["ad_spend"] or 0),
            "ad_revenue": float(row["ad_revenue"] or 0),
            "organic_sales": float(row["organic_sales"] or 0),
        }

    current_data = by_month.get(month)
    previous_data = by_month.get(previous)

    if current_data is None:
        raise ValueError(
            f"No sales data found for {month}."
        )

    if previous_data is None:
        raise ValueError(
            f"No sales data found for previous month {previous}."
        )

    total_current_sales = current_data["sales"]
    total_previous_sales = previous_data["sales"]

    sales_change = (
        total_current_sales
        - total_previous_sales
    )

    sales_change_pct = None
    if total_previous_sales != 0:
        sales_change_pct = (
            sales_change
            / abs(total_previous_sales)
        ) * 100

    roas_current = None
    if current_data["ad_spend"] > 0:
        roas_current = (
            current_data["ad_revenue"]
            / current_data["ad_spend"]
        )

    roas_previous = None
    if previous_data["ad_spend"] > 0:
        roas_previous = (
            previous_data["ad_revenue"]
            / previous_data["ad_spend"]
        )

    tacos_current = None
    if total_current_sales > 0:
        tacos_current = (
            current_data["ad_spend"]
            / total_current_sales
        ) * 100

    tacos_previous = None
    if total_previous_sales > 0:
        tacos_previous = (
            previous_data["ad_spend"]
            / total_previous_sales
        ) * 100

    return {
        "current_month": month,
        "previous_month": previous,
        "country": country,
        "current": current_data,
        "previous": previous_data,
        "sales_change": sales_change,
        "sales_change_pct": sales_change_pct,
        "roas_current": roas_current,
        "roas_previous": roas_previous,
        "tacos_current": tacos_current,
        "tacos_previous": tacos_previous,
    }


# ============================================================
# SKU DRIVER ANALYSIS
# ============================================================

def sku_sales_drivers(
    month: str,
    country: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """
    Identify the SKUs contributing most to a month-over-month
    sales increase or decline.

    The analysis compares:
        previous month -> requested month

    Example:
        May 2026
        compares April 2026 vs May 2026.

    Results include:
        sku
        previous_sales
        current_sales
        sales_change
        sales_change_pct
        contribution_pct
        previous_units
        current_units
        units_change
        previous_ad_spend
        current_ad_spend
        ad_spend_change
        previous_ad_revenue
        current_ad_revenue
        ad_revenue_change
        previous_organic_sales
        current_organic_sales
        organic_sales_change

    Positive contribution_pct:
        contributes in the same direction as total sales change.

    Negative contribution_pct:
        offsets the total sales change.
    """

    month = validate_month(month)
    country = validate_country(country)

    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 10

    limit = max(1, min(limit, 100))

    previous = previous_month(month)

    conditions = [
        "year_month IN (:previous_month, :current_month)"
    ]

    params = {
        "previous_month": f"{previous}-01",
        "current_month": f"{month}-01",
    }

    if country:
        conditions.append(
            "country = :country"
        )
        params["country"] = country

    where_clause = (
        "WHERE "
        + " AND ".join(conditions)
    )

    query = text(
        f"""
        WITH monthly_sku AS (
            SELECT
                sku,
                year_month,

                SUM(gross_sales) AS sales,
                SUM(unit_ordered) AS units,
                SUM(ad_spend) AS ad_spend,
                SUM(ad_revenue) AS ad_revenue,
                SUM(organic_sale) AS organic_sales

            FROM {TABLE_NAME}

            {where_clause}

            GROUP BY
                sku,
                year_month
        ),

        pivoted AS (
            SELECT

                sku,

                MAX(
                    CASE
                        WHEN year_month = CAST(
                            :previous_month AS DATE
                        )
                        THEN sales
                        ELSE 0
                    END
                ) AS previous_sales,

                MAX(
                    CASE
                        WHEN year_month = CAST(
                            :current_month AS DATE
                        )
                        THEN sales
                        ELSE 0
                    END
                ) AS current_sales,

                MAX(
                    CASE
                        WHEN year_month = CAST(
                            :previous_month AS DATE
                        )
                        THEN units
                        ELSE 0
                    END
                ) AS previous_units,

                MAX(
                    CASE
                        WHEN year_month = CAST(
                            :current_month AS DATE
                        )
                        THEN units
                        ELSE 0
                    END
                ) AS current_units,

                MAX(
                    CASE
                        WHEN year_month = CAST(
                            :previous_month AS DATE
                        )
                        THEN ad_spend
                        ELSE 0
                    END
                ) AS previous_ad_spend,

                MAX(
                    CASE
                        WHEN year_month = CAST(
                            :current_month AS DATE
                        )
                        THEN ad_spend
                        ELSE 0
                    END
                ) AS current_ad_spend,

                MAX(
                    CASE
                        WHEN year_month = CAST(
                            :previous_month AS DATE
                        )
                        THEN ad_revenue
                        ELSE 0
                    END
                ) AS previous_ad_revenue,

                MAX(
                    CASE
                        WHEN year_month = CAST(
                            :current_month AS DATE
                        )
                        THEN ad_revenue
                        ELSE 0
                    END
                ) AS current_ad_revenue,

                MAX(
                    CASE
                        WHEN year_month = CAST(
                            :previous_month AS DATE
                        )
                        THEN organic_sales
                        ELSE 0
                    END
                ) AS previous_organic_sales,

                MAX(
                    CASE
                        WHEN year_month = CAST(
                            :current_month AS DATE
                        )
                        THEN organic_sales
                        ELSE 0
                    END
                ) AS current_organic_sales

            FROM monthly_sku

            GROUP BY sku
        )

        SELECT
            sku,

            previous_sales,
            current_sales,
            current_sales - previous_sales AS sales_change,

            previous_units,
            current_units,
            current_units - previous_units AS units_change,

            previous_ad_spend,
            current_ad_spend,
            current_ad_spend - previous_ad_spend
                AS ad_spend_change,

            previous_ad_revenue,
            current_ad_revenue,
            current_ad_revenue - previous_ad_revenue
                AS ad_revenue_change,

            previous_organic_sales,
            current_organic_sales,
            current_organic_sales
                - previous_organic_sales
                AS organic_sales_change

        FROM pivoted
        ORDER BY sales_change ASC
        LIMIT :limit;
        """
    )

    rows = fetch_all(
        query,
        {
            **params,
            "limit": limit,
        }
    )

    # --------------------------------------------------------
    # Total sales change for the selected scope
    # --------------------------------------------------------

    totals = sales_change_summary(
        month=month,
        country=country,
    )

    total_current_sales = totals["current"]["sales"]
    total_previous_sales = totals["previous"]["sales"]

    result = []

    for raw_row in rows:

        if hasattr(raw_row, "_mapping"):
            row = dict(raw_row._mapping)
        else:
            row = dict(raw_row)

        current_sales = float(
            row.get("current_sales", 0) or 0
        )

        previous_sales = float(
            row.get("previous_sales", 0) or 0
        )

        contribution = _calculate_contribution(
            current_sales=current_sales,
            previous_sales=previous_sales,
            total_current_sales=total_current_sales,
            total_previous_sales=total_previous_sales,
        )

        result.append(
            {
                "sku": str(
                    row.get("sku", "")
                ).strip(),

                **contribution,

                "previous_units": float(
                    row.get("previous_units", 0) or 0
                ),

                "current_units": float(
                    row.get("current_units", 0) or 0
                ),

                "units_change": float(
                    row.get("units_change", 0) or 0
                ),

                "previous_ad_spend": float(
                    row.get("previous_ad_spend", 0) or 0
                ),

                "current_ad_spend": float(
                    row.get("current_ad_spend", 0) or 0
                ),

                "ad_spend_change": float(
                    row.get("ad_spend_change", 0) or 0
                ),

                "previous_ad_revenue": float(
                    row.get("previous_ad_revenue", 0) or 0
                ),

                "current_ad_revenue": float(
                    row.get("current_ad_revenue", 0) or 0
                ),

                "ad_revenue_change": float(
                    row.get("ad_revenue_change", 0) or 0
                ),

                "previous_organic_sales": float(
                    row.get(
                        "previous_organic_sales",
                        0,
                    )
                    or 0
                ),

                "current_organic_sales": float(
                    row.get(
                        "current_organic_sales",
                        0,
                    )
                    or 0
                ),

                "organic_sales_change": float(
                    row.get(
                        "organic_sales_change",
                        0,
                    )
                    or 0
                ),
            }
        )

    # --------------------------------------------------------
    # Add rank and human-readable direction
    # --------------------------------------------------------

    total_change = totals["sales_change"]

    if total_change < 0:
        # Biggest negative SKU changes are the biggest contributors
        result = sorted(
            result,
            key=lambda item: item["sales_change"]
        )

        direction = "decline"
    elif total_change > 0:
        # Biggest positive SKU changes are the biggest contributors
        result = sorted(
            result,
            key=lambda item: item["sales_change"],
            reverse=True,
        )

        direction = "increase"
    else:
        result = sorted(
            result,
            key=lambda item: abs(
                item["sales_change"]
            ),
            reverse=True,
        )

        direction = "no_change"

    for index, item in enumerate(
        result,
        start=1,
    ):
        item["rank"] = index

    return {
        "analysis_type": "sku_sales_drivers",
        "month": month,
        "previous_month": previous,
        "country": country,
        "direction": direction,
        "total_sales_change": totals["sales_change"],
        "total_sales_change_pct": totals["sales_change_pct"],
        "total_current_sales": total_current_sales,
        "total_previous_sales": total_previous_sales,
        "drivers": result,
    }


# ============================================================
# COUNTRY DRIVER ANALYSIS
# ============================================================

def country_sales_drivers(
    month: str,
    limit: int = 10,
) -> dict[str, Any]:
    """
    Identify countries contributing most to the month-over-month
    sales increase or decline.

    Compares:
        previous month -> requested month

    Example:
        May 2026
        compares April 2026 vs May 2026.
    """

    month = validate_month(month)

    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 10

    limit = max(1, min(limit, 100))

    previous = previous_month(month)

    query = text(
        f"""
        WITH monthly_country AS (
            SELECT
                country,
                year_month,
                SUM(gross_sales) AS sales,
                SUM(unit_ordered) AS units,
                SUM(ad_spend) AS ad_spend,
                SUM(ad_revenue) AS ad_revenue,
                SUM(organic_sale) AS organic_sales
            FROM {TABLE_NAME}
            WHERE year_month IN (
                CAST(:previous_month AS DATE),
                CAST(:current_month AS DATE)
            )
            GROUP BY
                country,
                year_month
        ),

        pivoted AS (
            SELECT

                country,

                MAX(
                    CASE
                        WHEN year_month =
                            CAST(
                                :previous_month
                                AS DATE
                            )
                        THEN sales
                        ELSE 0
                    END
                ) AS previous_sales,

                MAX(
                    CASE
                        WHEN year_month =
                            CAST(
                                :current_month
                                AS DATE
                            )
                        THEN sales
                        ELSE 0
                    END
                ) AS current_sales,

                MAX(
                    CASE
                        WHEN year_month =
                            CAST(
                                :previous_month
                                AS DATE
                            )
                        THEN units
                        ELSE 0
                    END
                ) AS previous_units,

                MAX(
                    CASE
                        WHEN year_month =
                            CAST(
                                :current_month
                                AS DATE
                            )
                        THEN units
                        ELSE 0
                    END
                ) AS current_units,

                MAX(
                    CASE
                        WHEN year_month =
                            CAST(
                                :previous_month
                                AS DATE
                            )
                        THEN ad_spend
                        ELSE 0
                    END
                ) AS previous_ad_spend,

                MAX(
                    CASE
                        WHEN year_month =
                            CAST(
                                :current_month
                                AS DATE
                            )
                        THEN ad_spend
                        ELSE 0
                    END
                ) AS current_ad_spend,

                MAX(
                    CASE
                        WHEN year_month =
                            CAST(
                                :previous_month
                                AS DATE
                            )
                        THEN ad_revenue
                        ELSE 0
                    END
                ) AS previous_ad_revenue,

                MAX(
                    CASE
                        WHEN year_month =
                            CAST(
                                :current_month
                                AS DATE
                            )
                        THEN ad_revenue
                        ELSE 0
                    END
                ) AS current_ad_revenue,

                MAX(
                    CASE
                        WHEN year_month =
                            CAST(
                                :previous_month
                                AS DATE
                            )
                        THEN organic_sales
                        ELSE 0
                    END
                ) AS previous_organic_sales,

                MAX(
                    CASE
                        WHEN year_month =
                            CAST(
                                :current_month
                                AS DATE
                            )
                        THEN organic_sales
                        ELSE 0
                    END
                ) AS current_organic_sales

            FROM monthly_country

            GROUP BY country
        )

        SELECT
            country,

            previous_sales,
            current_sales,
            current_sales - previous_sales
                AS sales_change,

            previous_units,
            current_units,
            current_units - previous_units
                AS units_change,

            previous_ad_spend,
            current_ad_spend,
            current_ad_spend - previous_ad_spend
                AS ad_spend_change,

            previous_ad_revenue,
            current_ad_revenue,
            current_ad_revenue - previous_ad_revenue
                AS ad_revenue_change,

            previous_organic_sales,
            current_organic_sales,
            current_organic_sales
                - previous_organic_sales
                AS organic_sales_change

        FROM pivoted
        ORDER BY sales_change ASC
        LIMIT :limit;
        """
    )

    # --------------------------------------------------------
    # First get total scope totals
    # --------------------------------------------------------

    totals = sales_change_summary(
        month=month
    )

    total_current_sales = totals["current"]["sales"]
    total_previous_sales = totals["previous"]["sales"]

    rows = fetch_all(
        query,
        {
            "previous_month": f"{previous}-01",
            "current_month": f"{month}-01",
            "limit": limit,
        }
    )

    result = []

    for raw_row in rows:

        if hasattr(raw_row, "_mapping"):
            row = dict(raw_row._mapping)
        else:
            row = dict(raw_row)

        current_sales = float(
            row.get("current_sales", 0) or 0
        )

        previous_sales = float(
            row.get("previous_sales", 0) or 0
        )

        contribution = _calculate_contribution(
            current_sales=current_sales,
            previous_sales=previous_sales,
            total_current_sales=total_current_sales,
            total_previous_sales=total_previous_sales,
        )

        result.append(
            {
                "country": str(
                    row.get("country", "")
                ).strip().upper(),

                **contribution,

                "previous_units": float(
                    row.get("previous_units", 0) or 0
                ),

                "current_units": float(
                    row.get("current_units", 0) or 0
                ),

                "units_change": float(
                    row.get("units_change", 0) or 0
                ),

                "previous_ad_spend": float(
                    row.get("previous_ad_spend", 0) or 0
                ),

                "current_ad_spend": float(
                    row.get("current_ad_spend", 0) or 0
                ),

                "ad_spend_change": float(
                    row.get("ad_spend_change", 0) or 0
                ),

                "previous_ad_revenue": float(
                    row.get("previous_ad_revenue", 0) or 0
                ),

                "current_ad_revenue": float(
                    row.get("current_ad_revenue", 0) or 0
                ),

                "ad_revenue_change": float(
                    row.get("ad_revenue_change", 0) or 0
                ),

                "previous_organic_sales": float(
                    row.get(
                        "previous_organic_sales",
                        0,
                    )
                    or 0
                ),

                "current_organic_sales": float(
                    row.get(
                        "current_organic_sales",
                        0,
                    )
                    or 0
                ),

                "organic_sales_change": float(
                    row.get(
                        "organic_sales_change",
                        0,
                    )
                    or 0
                ),
            }
        )

    total_change = totals["sales_change"]

    if total_change < 0:
        result = sorted(
            result,
            key=lambda item: item["sales_change"]
        )
        direction = "decline"
    elif total_change > 0:
        result = sorted(
            result,
            key=lambda item: item["sales_change"],
            reverse=True,
        )
        direction = "increase"
    else:
        result = sorted(
            result,
            key=lambda item: abs(
                item["sales_change"]
            ),
            reverse=True,
        )
        direction = "no_change"

    for index, item in enumerate(
        result,
        start=1,
    ):
        item["rank"] = index

    return {
        "analysis_type": "country_sales_drivers",
        "month": month,
        "previous_month": previous,
        "direction": direction,
        "total_sales_change": totals["sales_change"],
        "total_sales_change_pct": totals["sales_change_pct"],
        "total_current_sales": total_current_sales,
        "total_previous_sales": total_previous_sales,
        "drivers": result,
    }


# ============================================================
# COMBINED DRIVER ANALYSIS
# ============================================================

def driver_analysis(
    month: str,
    country: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """
    Combined driver analysis for a month-over-month sales change.

    Returns:
        - overall sales comparison
        - SKU drivers
        - country drivers

    When country is supplied:
        SKU analysis is restricted to that country.

    Country-level driver analysis remains global because the
    requested country itself would otherwise produce only one
    country row.
    """

    month = validate_month(month)
    country = validate_country(country)

    summary = sales_change_summary(
        month=month,
        country=country,
    )

    sku_result = sku_sales_drivers(
        month=month,
        country=country,
        limit=limit,
    )

    country_result = None

    if country is None:
        country_result = country_sales_drivers(
            month=month,
            limit=limit,
        )

    return {
        "analysis_type": "driver_analysis",
        "month": month,
        "previous_month": summary["previous_month"],
        "country": country,
        "summary": summary,
        "sku_drivers": sku_result,
        "country_drivers": country_result,
    }


# ============================================================
# FORMATTER
# ============================================================

def format_driver_analysis(
    result: dict[str, Any],
) -> str:
    """
    Create a deterministic business-readable driver report.

    No LLM is used to calculate or rank drivers.
    """

    summary = result["summary"]

    current_month = summary["current_month"]
    previous_month_value = summary["previous_month"]

    total_change = summary["sales_change"]
    total_change_pct = summary["sales_change_pct"]

    lines = []

    lines.append(
        f"Sales Driver Analysis: "
        f"{previous_month_value} -> {current_month}"
    )

    lines.append(
        f"Previous Sales: "
        f"${summary['previous']['sales']:,.2f}"
    )

    lines.append(
        f"Current Sales: "
        f"${summary['current']['sales']:,.2f}"
    )

    lines.append(
        f"Sales Change: "
        f"${total_change:,.2f}"
    )

    if total_change_pct is not None:
        lines.append(
            f"Sales Change %: "
            f"{total_change_pct:.2f}%"
        )

    lines.append("")
    lines.append("Top SKU Drivers:")

    sku_drivers = result["sku_drivers"]["drivers"]

    if not sku_drivers:
        lines.append("No SKU driver data found.")
    else:
        for item in sku_drivers[:10]:
            contribution = item["contribution_pct"]

            contribution_text = (
                f"{contribution:.2f}%"
                if contribution is not None
                else "N/A"
            )

            lines.append(
                f"{item['rank']}. "
                f"{item['sku']} | "
                f"Sales Change="
                f"${item['sales_change']:,.2f} | "
                f"Contribution="
                f"{contribution_text}"
            )

    country_drivers = result.get(
        "country_drivers"
    )

    if country_drivers is not None:

        lines.append("")
        lines.append("Top Country Drivers:")

        for item in country_drivers["drivers"][:10]:
            contribution = item["contribution_pct"]

            contribution_text = (
                f"{contribution:.2f}%"
                if contribution is not None
                else "N/A"
            )

            lines.append(
                f"{item['rank']}. "
                f"{item['country']} | "
                f"Sales Change="
                f"${item['sales_change']:,.2f} | "
                f"Contribution="
                f"{contribution_text}"
            )

    lines.append("")
    lines.append(
        "Note: contribution percentages show how "
        "each segment contributed to the total "
        "month-over-month sales change. They do not "
        "by themselves establish causation."
    )

    return "\n".join(lines)


# ============================================================
# TEST
# ============================================================

def main():

    print()
    print("=" * 90)
    print("               AI BUSINESS ANALYST - DRIVER ANALYSIS")
    print("=" * 90)

    print()
    print(
        "Testing May 2026 driver analysis..."
    )

    result = driver_analysis(
        month="2026-05",
        limit=10,
    )

    print()
    print(
        format_driver_analysis(
            result
        )
    )

    print()
    print("=" * 90)
    print("                     DRIVER ANALYSIS READY")
    print("=" * 90)
    print()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
