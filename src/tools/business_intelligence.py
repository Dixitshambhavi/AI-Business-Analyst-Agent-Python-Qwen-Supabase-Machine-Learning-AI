from pathlib import Path
import sys
import re
from sqlalchemy import text


# ============================================================
# PROJECT PATH
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))


from src.database.connection import engine


TABLE_NAME = "business_sales"


# ============================================================
# DATABASE HELPER
# ============================================================

def fetch_all(query, params=None):

    with engine.connect() as connection:

        result = connection.execute(
            query,
            params or {}
        )

        return result.fetchall()


# ============================================================
# 1. EXECUTIVE KPI TOOL
# ============================================================

def executive_kpis():

    query = text(f"""
        SELECT

            COUNT(*) AS rows,

            COUNT(DISTINCT sku) AS unique_skus,

            COUNT(DISTINCT country) AS countries,

            MIN(year_month) AS first_month,

            MAX(year_month) AS last_month,

            SUM(unit_ordered) AS units,

            SUM(gross_sales) AS sales,

            SUM(ad_spend) AS ad_spend,

            SUM(ad_revenue) AS ad_revenue,

            SUM(organic_sale) AS organic_sales,

            CASE

                WHEN SUM(ad_spend) > 0

                THEN SUM(ad_revenue)
                     / SUM(ad_spend)

                ELSE NULL

            END AS roas,

            CASE

                WHEN SUM(gross_sales) > 0

                THEN SUM(ad_spend)
                     / SUM(gross_sales) * 100

                ELSE NULL

            END AS tacos,

            CASE

                WHEN SUM(gross_sales) > 0

                THEN SUM(organic_sale)
                     / SUM(gross_sales) * 100

                ELSE NULL

            END AS organic_pct

        FROM {TABLE_NAME};
    """)

    row = fetch_all(query)[0]

    return {
        "rows": row.rows,
        "unique_skus": row.unique_skus,
        "countries": row.countries,
        "first_month": str(row.first_month),
        "last_month": str(row.last_month),
        "units": float(row.units or 0),
        "sales": float(row.sales or 0),
        "ad_spend": float(row.ad_spend or 0),
        "ad_revenue": float(row.ad_revenue or 0),
        "organic_sales": float(row.organic_sales or 0),
        "roas": float(row.roas) if row.roas is not None else None,
        "tacos": float(row.tacos) if row.tacos is not None else None,
        "organic_pct": (
            float(row.organic_pct)
            if row.organic_pct is not None
            else None
        )
    }


# ============================================================
# 2. MONTHLY PERFORMANCE TOOL
# ============================================================

def monthly_performance():
    """
    Return trusted month-by-month business performance.

    Metrics returned for every month:
        - sales
        - units
        - ad_spend
        - ad_revenue
        - organic_sales
        - roas
        - tacos
        - organic_pct
        - sales_growth_pct

    Business definitions:
        ROAS       = ad_revenue / ad_spend
        TACOS      = ad_spend / sales * 100
        Organic %  = organic_sales / sales * 100

    All business calculations are performed in SQL/Python.
    The LLM does not calculate these metrics.
    """

    query = text(f"""
        WITH monthly AS (

            SELECT

                year_month,

                SUM(gross_sales) AS sales,

                SUM(ad_spend) AS ad_spend,

                SUM(ad_revenue) AS ad_revenue,

                SUM(organic_sale) AS organic_sales,

                SUM(unit_ordered) AS units

            FROM {TABLE_NAME}

            GROUP BY year_month

        )

        SELECT

            year_month,

            sales,

            ad_spend,

            ad_revenue,

            organic_sales,

            units,

            CASE

                WHEN ad_spend > 0

                THEN ad_revenue / ad_spend

                ELSE NULL

            END AS roas,

            CASE

                WHEN sales > 0

                THEN ad_spend / sales * 100

                ELSE NULL

            END AS tacos,

            CASE

                WHEN sales > 0

                THEN organic_sales / sales * 100

                ELSE NULL

            END AS organic_pct

        FROM monthly

        ORDER BY year_month;
    """)

    rows = fetch_all(query)

    results = []

    previous_sales = None

    for row in rows:

        sales = float(row.sales or 0)
        ad_spend = float(row.ad_spend or 0)
        ad_revenue = float(row.ad_revenue or 0)
        organic_sales = float(row.organic_sales or 0)
        units = float(row.units or 0)

        roas = (
            float(row.roas)
            if row.roas is not None
            else None
        )

        tacos = (
            float(row.tacos)
            if row.tacos is not None
            else None
        )

        organic_pct = (
            float(row.organic_pct)
            if row.organic_pct is not None
            else None
        )

        sales_growth = None

        if previous_sales is not None and previous_sales > 0:

            sales_growth = (
                (sales - previous_sales)
                / previous_sales
            ) * 100

        results.append({

            "month": str(row.year_month),

            "sales": sales,

            "ad_spend": ad_spend,

            "ad_revenue": ad_revenue,

            "organic_sales": organic_sales,

            "units": units,

            "roas": roas,

            "tacos": tacos,

            "organic_pct": organic_pct,

            "sales_growth_pct": sales_growth

        })

        previous_sales = sales

    return results


# ============================================================
# 2B. TREND ANALYSIS TOOL
# ============================================================

def trend_analysis(
    country=None,
    year=None,
):
    """
    Trusted monthly trend analysis.

    Optional filters:
        country -> IN, US, DE, UK, CA, AE
        year    -> calendar year
    """

    conditions = []
    params = {}

    if country:
        country = str(country).upper().strip()
        allowed_countries = {"IN", "US", "DE", "UK", "CA", "AE"}

        if country not in allowed_countries:
            raise ValueError(f"Unsupported country code: {country}")

        conditions.append("country = :country")
        params["country"] = country

    if year is not None:
        try:
            year = int(year)
        except (TypeError, ValueError):
            raise ValueError("Year must be an integer.")

        if year < 2000 or year > 2100:
            raise ValueError("Year must be between 2000 and 2100.")

        conditions.append(
            "year_month >= :year_start "
            "AND year_month < :year_end"
        )
        params["year_start"] = f"{year}-01-01"
        params["year_end"] = f"{year + 1}-01-01"

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    query = text(f"""
        SELECT
            year_month,
            SUM(gross_sales) AS sales,
            SUM(unit_ordered) AS units,
            SUM(ad_spend) AS ad_spend,
            SUM(ad_revenue) AS ad_revenue,
            SUM(organic_sale) AS organic_sales,

            CASE
                WHEN SUM(ad_spend) > 0
                THEN SUM(ad_revenue) / SUM(ad_spend)
                ELSE NULL
            END AS roas,

            CASE
                WHEN SUM(gross_sales) > 0
                THEN SUM(ad_spend) / SUM(gross_sales) * 100
                ELSE NULL
            END AS tacos,

            CASE
                WHEN SUM(gross_sales) > 0
                THEN SUM(organic_sale) / SUM(gross_sales) * 100
                ELSE NULL
            END AS organic_pct

        FROM {TABLE_NAME}
        {where_clause}
        GROUP BY year_month
        ORDER BY year_month;
    """)

    rows = fetch_all(query, params)

    monthly = []
    previous_sales = None
    previous_roas = None
    previous_tacos = None

    for row in rows:
        sales = float(row.sales or 0)
        units = float(row.units or 0)
        ad_spend = float(row.ad_spend or 0)
        ad_revenue = float(row.ad_revenue or 0)
        organic_sales = float(row.organic_sales or 0)

        roas = (
            float(row.roas)
            if row.roas is not None
            else None
        )
        tacos = (
            float(row.tacos)
            if row.tacos is not None
            else None
        )
        organic_pct = (
            float(row.organic_pct)
            if row.organic_pct is not None
            else None
        )

        sales_growth_pct = None
        if previous_sales is not None and previous_sales != 0:
            sales_growth_pct = (
                (sales - previous_sales)
                / abs(previous_sales)
            ) * 100

        roas_change = None
        if roas is not None and previous_roas is not None:
            roas_change = roas - previous_roas

        tacos_change = None
        if tacos is not None and previous_tacos is not None:
            tacos_change = tacos - previous_tacos

        monthly.append({
            "month": str(row.year_month),
            "sales": sales,
            "units": units,
            "ad_spend": ad_spend,
            "ad_revenue": ad_revenue,
            "organic_sales": organic_sales,
            "roas": roas,
            "tacos": tacos,
            "organic_pct": organic_pct,
            "sales_growth_pct": sales_growth_pct,
            "roas_change": roas_change,
            "tacos_change": tacos_change,
        })

        previous_sales = sales
        previous_roas = roas
        previous_tacos = tacos

    if not monthly:
        return {
            "filters": {"country": country, "year": year},
            "monthly": [],
            "summary": {
                "months": 0,
                "best_sales_month": None,
                "best_sales": None,
                "worst_sales_month": None,
                "worst_sales": None,
                "highest_roas_month": None,
                "highest_roas": None,
                "lowest_roas_month": None,
                "lowest_roas": None,
                "largest_sales_growth_month": None,
                "largest_sales_growth_pct": None,
                "largest_sales_decline_month": None,
                "largest_sales_decline_pct": None,
                "first_month": None,
                "last_month": None,
                "first_to_last_sales_change_pct": None,
                "first_to_last_roas_change": None,
                "first_to_last_tacos_change": None,
            },
        }

    best_sales = max(monthly, key=lambda r: r["sales"])
    worst_sales = min(monthly, key=lambda r: r["sales"])

    roas_rows = [r for r in monthly if r["roas"] is not None]
    highest_roas = max(roas_rows, key=lambda r: r["roas"]) if roas_rows else None
    lowest_roas = min(roas_rows, key=lambda r: r["roas"]) if roas_rows else None

    growth_rows = [
        r for r in monthly
        if r["sales_growth_pct"] is not None
    ]
    largest_growth = (
        max(growth_rows, key=lambda r: r["sales_growth_pct"])
        if growth_rows else None
    )
    largest_decline = (
        min(growth_rows, key=lambda r: r["sales_growth_pct"])
        if growth_rows else None
    )

    first = monthly[0]
    last = monthly[-1]

    first_to_last_sales_change_pct = None
    if first["sales"] != 0:
        first_to_last_sales_change_pct = (
            (last["sales"] - first["sales"])
            / abs(first["sales"])
        ) * 100

    first_to_last_roas_change = None
    if first["roas"] is not None and last["roas"] is not None:
        first_to_last_roas_change = last["roas"] - first["roas"]

    first_to_last_tacos_change = None
    if first["tacos"] is not None and last["tacos"] is not None:
        first_to_last_tacos_change = last["tacos"] - first["tacos"]

    return {
        "filters": {
            "country": country,
            "year": year,
        },
        "monthly": monthly,
        "summary": {
            "months": len(monthly),
            "best_sales_month": best_sales["month"],
            "best_sales": best_sales["sales"],
            "worst_sales_month": worst_sales["month"],
            "worst_sales": worst_sales["sales"],
            "highest_roas_month": highest_roas["month"] if highest_roas else None,
            "highest_roas": highest_roas["roas"] if highest_roas else None,
            "lowest_roas_month": lowest_roas["month"] if lowest_roas else None,
            "lowest_roas": lowest_roas["roas"] if lowest_roas else None,
            "largest_sales_growth_month": largest_growth["month"] if largest_growth else None,
            "largest_sales_growth_pct": largest_growth["sales_growth_pct"] if largest_growth else None,
            "largest_sales_decline_month": largest_decline["month"] if largest_decline else None,
            "largest_sales_decline_pct": largest_decline["sales_growth_pct"] if largest_decline else None,
            "first_month": first["month"],
            "last_month": last["month"],
            "first_to_last_sales_change_pct": first_to_last_sales_change_pct,
            "first_to_last_roas_change": first_to_last_roas_change,
            "first_to_last_tacos_change": first_to_last_tacos_change,
        },
    }


# ============================================================
# 3. TOP PRODUCTS TOOL
# ============================================================

def top_products(limit=10):

    query = text(f"""
        SELECT

            sku,

            SUM(gross_sales) AS sales,

            SUM(unit_ordered) AS units,

            SUM(ad_spend) AS ad_spend,

            SUM(ad_revenue) AS ad_revenue,

            CASE

                WHEN SUM(ad_spend) > 0

                THEN SUM(ad_revenue)
                     / SUM(ad_spend)

                ELSE NULL

            END AS roas

        FROM {TABLE_NAME}

        GROUP BY sku

        ORDER BY sales DESC

        LIMIT :limit;
    """)

    rows = fetch_all(
        query,
        {"limit": limit}
    )

    return [

        {
            "sku": row.sku,
            "sales": float(row.sales or 0),
            "units": float(row.units or 0),
            "ad_spend": float(row.ad_spend or 0),
            "ad_revenue": float(row.ad_revenue or 0),
            "roas": (
                float(row.roas)
                if row.roas is not None
                else None
            )
        }

        for row in rows

    ]

# ============================================================
# 3B. PARAMETERIZED PRODUCT RANKING
# ============================================================

def product_ranking(
    country=None,
    year=None,
    month=None,
    limit=10
):
    """
    Return products/SKUs ranked by gross sales with optional
    country, year and month filters.

    Business definition:
        revenue/sales = SUM(gross_sales)

    The SQL is generated by Python, not by the LLM.
    """

    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 10

    limit = max(1, min(limit, 100))

    conditions = []
    params = {
        "limit": limit
    }

    # --------------------------------------------------------
    # COUNTRY FILTER
    # --------------------------------------------------------

    if country:

        conditions.append(
            "country = :country"
        )

        params["country"] = str(
            country
        ).upper().strip()

    # --------------------------------------------------------
    # YEAR FILTER
    # --------------------------------------------------------

    if year is not None:

        try:
            year = int(year)
        except (TypeError, ValueError):

            raise ValueError(
                "Year must be an integer."
            )

        if year < 2000 or year > 2100:

            raise ValueError(
                "Year must be between 2000 and 2100."
            )

        conditions.append(
            "year_month >= :year_start "
            "AND year_month < :year_end"
        )

        params["year_start"] = f"{year}-01-01"
        params["year_end"] = f"{year + 1}-01-01"

    # --------------------------------------------------------
    # MONTH FILTER
    # --------------------------------------------------------

    if month:

        # Expected format:
        # YYYY-MM

        if not re.match(
            r"^\d{4}-\d{2}$",
            str(month)
        ):

            raise ValueError(
                "Month must use YYYY-MM format."
            )

        conditions.append(
            "year_month = CAST(:month AS DATE)"
        )

        params["month"] = (
            f"{month}-01"
        )

    # --------------------------------------------------------
    # WHERE CLAUSE
    # --------------------------------------------------------

    where_clause = ""

    if conditions:

        where_clause = (
            "WHERE "
            + " AND ".join(conditions)
        )

    # --------------------------------------------------------
    # QUERY
    # --------------------------------------------------------

    query = text(f"""
        SELECT
            sku,
            SUM(gross_sales) AS sales,
            SUM(unit_ordered) AS units,
            SUM(ad_spend) AS ad_spend,
            SUM(ad_revenue) AS ad_revenue,

            CASE
                WHEN SUM(ad_spend) > 0
                THEN SUM(ad_revenue)
                     / SUM(ad_spend)
                ELSE NULL
            END AS roas

        FROM {TABLE_NAME}

        {where_clause}

        GROUP BY sku

        ORDER BY sales DESC

        LIMIT :limit;
    """)

    rows = fetch_all(
        query,
        params
    )

    return [
        {
            "sku": row.sku,
            "sales": float(
                row.sales or 0
            ),
            "units": float(
                row.units or 0
            ),
            "ad_spend": float(
                row.ad_spend or 0
            ),
            "ad_revenue": float(
                row.ad_revenue or 0
            ),
            "roas": (
                float(row.roas)
                if row.roas is not None
                else None
            )
        }
        for row in rows
    ]
# ============================================================
# 4. ADVERTISING RISK TOOL
# ============================================================

def advertising_risks(limit=20):

    query = text(f"""
        SELECT

            sku,

            country,

            year_month,

            gross_sales,

            ad_spend,

            ad_revenue,

            CASE

                WHEN ad_spend > 0
                     AND ad_revenue = 0

                THEN 'NO_AD_REVENUE'

                WHEN ad_spend > 0
                     AND ad_revenue > 0
                     AND ad_revenue / ad_spend < 1

                THEN 'ROAS_BELOW_1'

                WHEN ad_spend > 0
                     AND ad_revenue > 0
                     AND ad_spend / ad_revenue * 100 >= 100

                THEN 'HIGH_ACOS'

                WHEN gross_sales = 0
                     AND ad_spend > 0

                THEN 'SALES_ATTRIBUTION_CHECK'

                ELSE 'NORMAL'

            END AS risk

        FROM {TABLE_NAME}

        WHERE ad_spend > 0

        ORDER BY

            CASE

                WHEN ad_spend > 0
                     AND ad_revenue = 0
                THEN 1

                WHEN ad_spend > 0
                     AND ad_revenue > 0
                     AND ad_revenue / ad_spend < 1
                THEN 2

                WHEN ad_spend > 0
                     AND ad_revenue > 0
                     AND ad_spend / ad_revenue * 100 >= 100
                THEN 3

                WHEN gross_sales = 0
                     AND ad_spend > 0
                THEN 4

                ELSE 5

            END,

            ad_spend DESC

        LIMIT :limit;
    """)

    rows = fetch_all(
        query,
        {"limit": limit}
    )

    return [

        {
            "sku": row.sku,
            "country": row.country,
            "month": str(row.year_month),
            "gross_sales": float(row.gross_sales or 0),
            "ad_spend": float(row.ad_spend or 0),
            "ad_revenue": float(row.ad_revenue or 0),
            "risk": row.risk
        }

        for row in rows

    ]


# ============================================================
# 5. INVENTORY RISK TOOL
# ============================================================

def inventory_risks(limit=20):

    query = text(f"""
        SELECT

            sku,

            country,

            SUM(unit_ordered) AS units,

            SUM(gross_sales) AS sales,

            AVG(fba_inv) AS fba_inventory,

            AVG(awd) AS awd_inventory,

            CASE

                WHEN AVG(fba_inv) <= 0
                     AND SUM(unit_ordered) > 0

                THEN 'CRITICAL'

                WHEN AVG(fba_inv)
                     < SUM(unit_ordered) * 0.25

                THEN 'HIGH'

                WHEN AVG(fba_inv)
                     < SUM(unit_ordered) * 0.50

                THEN 'MEDIUM'

                ELSE 'NORMAL'

            END AS risk

        FROM {TABLE_NAME}

        GROUP BY

            sku,

            country

        HAVING SUM(unit_ordered) > 0

        ORDER BY

            CASE

                WHEN AVG(fba_inv) <= 0
                THEN 1

                WHEN AVG(fba_inv)
                     < SUM(unit_ordered) * 0.25
                THEN 2

                WHEN AVG(fba_inv)
                     < SUM(unit_ordered) * 0.50
                THEN 3

                ELSE 4

            END,

            sales DESC

        LIMIT :limit;
    """)

    rows = fetch_all(
        query,
        {"limit": limit}
    )

    return [

        {
            "sku": row.sku,
            "country": row.country,
            "units": float(row.units or 0),
            "sales": float(row.sales or 0),
            "fba_inventory": float(
                row.fba_inventory or 0
            ),
            "awd_inventory": float(
                row.awd_inventory or 0
            ),
            "risk": row.risk
        }

        for row in rows

    ]

# ============================================================
# 5B. INVENTORY RISK FOR SPECIFIC SKUS
# ============================================================
def inventory_risks_for_skus(skus):
    """
    Return inventory risk for the requested SKUs.

    The database contains inventory information at country level.
    This function:

        1. Cleans the requested SKU list.
        2. Gets country-level inventory data.
        3. Calculates inventory risk using the trusted business rules.
        4. Combines countries into ONE result per SKU.
        5. Keeps the highest-risk country for each SKU.

    Risk rules:
        CRITICAL -> FBA <= 0 and units > 0
        HIGH     -> FBA < units * 0.25
        MEDIUM   -> FBA < units * 0.50
        NORMAL   -> otherwise

    Important:
        SQLAlchemy Row objects are converted to normal dictionaries
        before field access so this works with the current fetch_all().
    """

    # ========================================================
    # 1. VALIDATE INPUT
    # ========================================================

    if not skus:
        return []

    cleaned_skus = []

    for sku in skus:

        if sku is None:
            continue

        sku = str(sku).strip()

        if not sku:
            continue

        if sku not in cleaned_skus:
            cleaned_skus.append(sku)

    # Safety limit
    cleaned_skus = cleaned_skus[:100]

    if not cleaned_skus:
        return []

    # ========================================================
    # 2. PARAMETERIZED SQL
    # ========================================================

    placeholders = ", ".join(
        f":sku_{i}"
        for i in range(len(cleaned_skus))
    )

    params = {
        f"sku_{i}": sku
        for i, sku in enumerate(cleaned_skus)
    }

    # ========================================================
    # 3. COUNTRY-LEVEL INVENTORY DATA
    # ========================================================

    query = text(
        f"""
        SELECT
            sku,
            country,
            SUM(unit_ordered) AS units,
            SUM(gross_sales) AS sales,
            AVG(fba_inv) AS fba_inventory,
            AVG(awd) AS awd_inventory
        FROM {TABLE_NAME}
        WHERE sku IN ({placeholders})
        GROUP BY sku, country
        ORDER BY sku, country
        """
    )

    rows = fetch_all(
        query,
        params
    )

    if not rows:
        return []

    # ========================================================
    # 4. RISK PRIORITY
    # ========================================================

    risk_priority = {
        "CRITICAL": 4,
        "HIGH": 3,
        "MEDIUM": 2,
        "NORMAL": 1,
    }

    # ========================================================
    # 5. CALCULATE COUNTRY-LEVEL RISK
    # ========================================================

    grouped = {}

    for raw_row in rows:

        # ----------------------------------------------------
        # SQLAlchemy Row -> normal dict
        # ----------------------------------------------------

        if hasattr(raw_row, "_mapping"):
            row = dict(raw_row._mapping)
        else:
            try:
                row = dict(raw_row)
            except (TypeError, ValueError):
                # Defensive fallback for tuple-like rows.
                # Expected column order from SELECT:
                # sku, country, units, sales,
                # fba_inventory, awd_inventory
                row = {
                    "sku": raw_row[0],
                    "country": raw_row[1],
                    "units": raw_row[2],
                    "sales": raw_row[3],
                    "fba_inventory": raw_row[4],
                    "awd_inventory": raw_row[5],
                }

        sku = str(
            row.get("sku", "")
        ).strip()

        if not sku:
            continue

        country = row.get("country")

        units = float(
            row.get("units", 0) or 0
        )

        sales = float(
            row.get("sales", 0) or 0
        )

        fba_inventory = float(
            row.get("fba_inventory", 0) or 0
        )

        awd_inventory = float(
            row.get("awd_inventory", 0) or 0
        )

        # ====================================================
        # TRUSTED INVENTORY RISK RULES
        # ====================================================

        if (
            fba_inventory <= 0
            and units > 0
        ):
            risk = "CRITICAL"

        elif (
            fba_inventory < units * 0.25
        ):
            risk = "HIGH"

        elif (
            fba_inventory < units * 0.50
        ):
            risk = "MEDIUM"

        else:
            risk = "NORMAL"

        country_result = {
            "sku": sku,
            "country": country,
            "sales": sales,
            "units": units,
            "fba_inventory": fba_inventory,
            "awd_inventory": awd_inventory,
            "risk": risk,
        }

        grouped.setdefault(
            sku,
            []
        ).append(
            country_result
        )

    # ========================================================
    # 6. ONE RESULT PER SKU
    # ========================================================

    final_results = []

    # Preserve the order of the requested SKUs.
    for sku in cleaned_skus:

        sku_rows = grouped.get(
            sku,
            []
        )

        if not sku_rows:
            continue

        # ----------------------------------------------------
        # Highest-risk country for the SKU
        # ----------------------------------------------------

        highest_risk_row = max(
            sku_rows,
            key=lambda row: (
                risk_priority.get(
                    str(
                        row.get("risk", "")
                    ).strip().upper(),
                    0
                ),
                float(
                    row.get("units", 0) or 0
                ),
            )
        )

        # ----------------------------------------------------
        # ONE FINAL ROW PER SKU
        # ----------------------------------------------------

        final_results.append(
            {
                "sku": sku,
                "country": highest_risk_row.get(
                    "country"
                ),
                "sales": highest_risk_row.get(
                    "sales",
                    0
                ),
                "units": highest_risk_row.get(
                    "units",
                    0
                ),
                "fba_inventory": highest_risk_row.get(
                    "fba_inventory",
                    0
                ),
                "awd_inventory": highest_risk_row.get(
                    "awd_inventory",
                    0
                ),
                "risk": highest_risk_row.get(
                    "risk",
                    "NORMAL"
                ),
            }
        )

    return final_results

# ============================================================
# 6. COUNTRY PERFORMANCE TOOL
# ============================================================

def country_performance():

    query = text(f"""
        SELECT

            country,

            SUM(gross_sales) AS sales,

            SUM(unit_ordered) AS units,

            SUM(ad_spend) AS ad_spend,

            SUM(ad_revenue) AS ad_revenue,

            CASE

                WHEN SUM(ad_spend) > 0

                THEN SUM(ad_revenue)
                     / SUM(ad_spend)

                ELSE NULL

            END AS roas,

            CASE

                WHEN SUM(gross_sales) > 0

                THEN SUM(ad_spend)
                     / SUM(gross_sales) * 100

                ELSE NULL

            END AS tacos

        FROM {TABLE_NAME}

        GROUP BY country

        ORDER BY sales DESC;
    """)

    rows = fetch_all(query)

    return [

        {
            "country": row.country,
            "sales": float(row.sales or 0),
            "units": float(row.units or 0),
            "ad_spend": float(row.ad_spend or 0),
            "ad_revenue": float(row.ad_revenue or 0),
            "roas": (
                float(row.roas)
                if row.roas is not None
                else None
            ),
            "tacos": (
                float(row.tacos)
                if row.tacos is not None
                else None
            )
        }

        for row in rows

    ]

# ============================================================
# COMPARISON ANALYSIS
# ============================================================

def comparison_analysis(
    country1,
    country2,
    year=None,
    month=None,
):
    """
    Compare two countries using trusted business metrics.

    Metrics:
        sales
        units
        ad_spend
        ad_revenue
        ROAS
        TACOS
        sales difference
        sales ratio
        ROAS difference
        TACOS difference

    All calculations are performed in Python/SQL.
    The LLM does not calculate the numbers.
    """

    if not country1:
        raise ValueError(
            "country1 is required."
        )

    if not country2:
        raise ValueError(
            "country2 is required."
        )

    country1 = str(
        country1
    ).upper().strip()

    country2 = str(
        country2
    ).upper().strip()

    allowed_countries = {
        "IN",
        "US",
        "DE",
        "UK",
        "CA",
        "AE",
    }

    if country1 not in allowed_countries:
        raise ValueError(
            f"Unsupported country1: {country1}"
        )

    if country2 not in allowed_countries:
        raise ValueError(
            f"Unsupported country2: {country2}"
        )

    if country1 == country2:
        raise ValueError(
            "country1 and country2 must be different."
        )

    # --------------------------------------------------------
    # CONDITIONS
    # --------------------------------------------------------

    conditions = [
        "country IN (:country1, :country2)"
    ]

    params = {
        "country1": country1,
        "country2": country2,
    }

    # --------------------------------------------------------
    # YEAR FILTER
    # --------------------------------------------------------

    if year is not None:

        try:
            year = int(year)
        except (
            TypeError,
            ValueError,
        ):
            raise ValueError(
                "Year must be an integer."
            )

        if year < 2000 or year > 2100:
            raise ValueError(
                "Year must be between 2000 and 2100."
            )

        conditions.append(
            "year_month >= :year_start "
            "AND year_month < :year_end"
        )

        params["year_start"] = (
            f"{year}-01-01"
        )

        params["year_end"] = (
            f"{year + 1}-01-01"
        )

    # --------------------------------------------------------
    # MONTH FILTER
    # --------------------------------------------------------

    if month is not None:

        month = str(
            month
        ).strip()

        if not re.match(
            r"^\d{4}-\d{2}$",
            month,
        ):
            raise ValueError(
                "Month must use YYYY-MM format."
            )

        conditions.append(
            "year_month = CAST(:month AS DATE)"
        )

        params["month"] = (
            f"{month}-01"
        )

    where_clause = (
        "WHERE "
        + " AND ".join(conditions)
    )

    # --------------------------------------------------------
    # QUERY
    # --------------------------------------------------------

    query = text(
        f"""
        SELECT
            country,
            SUM(gross_sales) AS sales,
            SUM(unit_ordered) AS units,
            SUM(ad_spend) AS ad_spend,
            SUM(ad_revenue) AS ad_revenue,

            CASE
                WHEN SUM(ad_spend) > 0
                THEN SUM(ad_revenue)
                     / SUM(ad_spend)
                ELSE NULL
            END AS roas,

            CASE
                WHEN SUM(gross_sales) > 0
                THEN SUM(ad_spend)
                     / SUM(gross_sales) * 100
                ELSE NULL
            END AS tacos

        FROM {TABLE_NAME}

        {where_clause}

        GROUP BY country

        ORDER BY country;
        """
    )

    rows = fetch_all(
        query,
        params
    )

    # --------------------------------------------------------
    # CONVERT SQLALCHEMY ROWS
    # --------------------------------------------------------

    country_data = {}

    for raw_row in rows:

        if hasattr(
            raw_row,
            "_mapping"
        ):

            row = dict(
                raw_row._mapping
            )

        else:

            try:
                row = dict(
                    raw_row
                )

            except (
                TypeError,
                ValueError,
            ):

                row = {
                    "country": raw_row[0],
                    "sales": raw_row[1],
                    "units": raw_row[2],
                    "ad_spend": raw_row[3],
                    "ad_revenue": raw_row[4],
                    "roas": raw_row[5],
                    "tacos": raw_row[6],
                }

        country = str(
            row.get(
                "country",
                ""
            )
        ).upper()

        country_data[country] = {
            "country": country,
            "sales": float(
                row.get(
                    "sales",
                    0
                ) or 0
            ),
            "units": float(
                row.get(
                    "units",
                    0
                ) or 0
            ),
            "ad_spend": float(
                row.get(
                    "ad_spend",
                    0
                ) or 0
            ),
            "ad_revenue": float(
                row.get(
                    "ad_revenue",
                    0
                ) or 0
            ),
            "roas": (
                float(
                    row["roas"]
                )
                if row.get(
                    "roas"
                ) is not None
                else None
            ),
            "tacos": (
                float(
                    row["tacos"]
                )
                if row.get(
                    "tacos"
                ) is not None
                else None
            ),
        }

    if country1 not in country_data:
        raise ValueError(
            f"No data found for {country1}."
        )

    if country2 not in country_data:
        raise ValueError(
            f"No data found for {country2}."
        )

    first = country_data[
        country1
    ]

    second = country_data[
        country2
    ]

    # --------------------------------------------------------
    # TRUSTED CALCULATIONS
    # --------------------------------------------------------

    sales_difference = (
        first["sales"]
        - second["sales"]
    )

    if second["sales"] > 0:

        sales_ratio = (
            first["sales"]
            / second["sales"]
        )

    else:

        sales_ratio = None

    if (
        first["sales"] > 0
        and second["sales"] > 0
    ):

        sales_pct_difference = (
            (
                first["sales"]
                - second["sales"]
            )
            / second["sales"]
        ) * 100

    else:

        sales_pct_difference = None

    roas_difference = None

    if (
        first["roas"] is not None
        and second["roas"] is not None
    ):

        roas_difference = (
            first["roas"]
            - second["roas"]
        )

    tacos_difference = None

    if (
        first["tacos"] is not None
        and second["tacos"] is not None
    ):

        tacos_difference = (
            first["tacos"]
            - second["tacos"]
        )

    # --------------------------------------------------------
    # FINAL STRUCTURED RESULT
    # --------------------------------------------------------

    return {
        "country1": first,
        "country2": second,

        "sales_difference":
            sales_difference,

        "sales_ratio":
            sales_ratio,

        "sales_pct_difference":
            sales_pct_difference,

        "roas_difference":
            roas_difference,

        "tacos_difference":
            tacos_difference,

        "higher_sales_country": (
            country1
            if first["sales"]
            > second["sales"]
            else country2
        ),

        "higher_roas_country": (
            country1
            if (
                first["roas"] is not None
                and second["roas"] is not None
                and first["roas"]
                > second["roas"]
            )
            else country2
        ),
    }

# ============================================================
# 7. DATA QUALITY TOOL
# ============================================================

def data_quality():

    query = text(f"""
        SELECT

            quality_status,

            COUNT(*) AS rows

        FROM {TABLE_NAME}

        GROUP BY quality_status

        ORDER BY rows DESC;
    """)

    rows = fetch_all(query)

    return {

        row.quality_status: int(row.rows)

        for row in rows

    }


# ============================================================
# 8. FULL BUSINESS SNAPSHOT
# ============================================================

def business_snapshot():

    return {

        "executive_kpis": executive_kpis(),

        "monthly_performance": monthly_performance(),

        "top_products": top_products(10),

        "advertising_risks": advertising_risks(10),

        "inventory_risks": inventory_risks(10),

        "country_performance": country_performance(),

        "data_quality": data_quality()

    }


# ============================================================
# TEST
# ============================================================

def main():

    print()
    print("=" * 90)
    print("           AI BUSINESS ANALYST - BUSINESS INTELLIGENCE")
    print("=" * 90)

    # --------------------------------------------------------
    # EXECUTIVE
    # --------------------------------------------------------

    print()
    print("1. EXECUTIVE KPIs")
    print("-" * 90)

    kpis = executive_kpis()

    print(
        f"Sales       : ${kpis['sales']:,.2f}"
    )

    print(
        f"Ad Spend    : ${kpis['ad_spend']:,.2f}"
    )

    print(
        f"Ad Revenue  : ${kpis['ad_revenue']:,.2f}"
    )

    print(
        f"ROAS        : "
        f"{kpis['roas']:.2f}x"
        if kpis["roas"] is not None
        else "ROAS        : N/A"
    )

    print(
        f"TACOS       : "
        f"{kpis['tacos']:.2f}%"
        if kpis["tacos"] is not None
        else "TACOS       : N/A"
    )


    # --------------------------------------------------------
    # TOP PRODUCTS
    # --------------------------------------------------------

    print()
    print("2. TOP PRODUCTS")
    print("-" * 90)

    products = top_products(10)

    for index, product in enumerate(
        products,
        start=1
    ):

        roas = (

            f"{product['roas']:.2f}x"

            if product["roas"] is not None

            else "N/A"

        )

        print(

            f"{index:02d}. "
            f"{product['sku']} | "
            f"Sales=${product['sales']:,.2f} | "
            f"Units={product['units']:,.0f} | "
            f"ROAS={roas}"

        )


    # --------------------------------------------------------
    # ADVERTISING RISKS
    # --------------------------------------------------------

    print()
    print("3. ADVERTISING RISKS")
    print("-" * 90)

    risks = advertising_risks(10)

    for risk in risks:

        print(

            f"{risk['sku']} | "
            f"{risk['country']} | "
            f"{risk['month']} | "
            f"Spend=${risk['ad_spend']:,.2f} | "
            f"Ad Revenue=${risk['ad_revenue']:,.2f} | "
            f"Risk={risk['risk']}"

        )


    # --------------------------------------------------------
    # INVENTORY
    # --------------------------------------------------------

    print()
    print("4. INVENTORY RISKS")
    print("-" * 90)

    inventory = inventory_risks(10)

    for item in inventory:

        print(

            f"{item['sku']} | "
            f"{item['country']} | "
            f"Sales=${item['sales']:,.2f} | "
            f"FBA={item['fba_inventory']:,.0f} | "
            f"Risk={item['risk']}"

        )


    # --------------------------------------------------------
    # COUNTRIES
    # --------------------------------------------------------

    print()
    print("5. COUNTRY PERFORMANCE")
    print("-" * 90)

    countries = country_performance()

    for country in countries:

        roas = (

            f"{country['roas']:.2f}x"

            if country["roas"] is not None

            else "N/A"

        )

        print(

            f"{country['country']} | "
            f"Sales=${country['sales']:,.2f} | "
            f"ROAS={roas} | "
            f"TACOS={country['tacos']:.2f}%"

        )


    # --------------------------------------------------------
    # QUALITY
    # --------------------------------------------------------

    print()
    print("6. DATA QUALITY")
    print("-" * 90)

    quality = data_quality()

    for status, count in quality.items():

        print(
            f"{status:<12} | "
            f"{count:,} rows"
        )


    print()
    print("=" * 90)
    print("             BUSINESS INTELLIGENCE READY")
    print("=" * 90)
    print()


# ============================================================
# RUN
# ============================================================

# if __name__ == "__main__":
#     main()
if __name__ == "__main__":
    
    test_skus = [
        "CBP9RO50",
        "CNB5CMT50UB",
        "CNB3CMT50UB",
        "BFW48P02",
        "CNB5CMT25UB"
    ]

    print()
    print("=" * 90)
    print("TESTING INVENTORY RISK FOR SPECIFIC SKUS")
    print("=" * 90)

    results = inventory_risks_for_skus(test_skus)

    for item in results:
        print(
            f"{item['sku']} | "
            f"{item['country']} | "
            f"Sales=${item['sales']:,.2f} | "
            f"FBA={item['fba_inventory']:,.0f} | "
            f"Risk={item['risk']}"
        )