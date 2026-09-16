from pathlib import Path
import sys

from sqlalchemy import text


# ============================================================
# PROJECT PATH
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(PROJECT_ROOT))


from src.database.connection import engine


# ============================================================
# DATABASE TABLE
# ============================================================

TABLE_NAME = "business_sales"


# ============================================================
# 1. OVERALL BUSINESS KPIs
# ============================================================

def get_business_kpis():

    query = text(f"""
        SELECT
            COUNT(*) AS rows,
            COUNT(DISTINCT sku) AS unique_skus,
            COUNT(DISTINCT country) AS countries,
            MIN(year_month) AS first_month,
            MAX(year_month) AS last_month,

            SUM(unit_ordered) AS total_units,
            SUM(gross_sales) AS total_sales,
            SUM(ad_spend) AS total_ad_spend,
            SUM(ad_revenue) AS total_ad_revenue,
            SUM(organic_sale) AS total_organic_sales,

            SUM(impression) AS total_impressions,
            SUM(click) AS total_clicks,
            SUM(ad_orders) AS total_ad_orders

        FROM {TABLE_NAME};
    """)

    with engine.connect() as connection:

        result = connection.execute(query)

        return result.fetchone()


# ============================================================
# 2. MONTHLY PERFORMANCE
# ============================================================

def get_monthly_performance():

    query = text(f"""
        SELECT

            year_month,

            SUM(unit_ordered) AS units,
            SUM(gross_sales) AS sales,
            SUM(ad_spend) AS ad_spend,
            SUM(ad_revenue) AS ad_revenue,
            SUM(organic_sale) AS organic_sales,

            CASE
                WHEN SUM(ad_spend) > 0
                THEN SUM(ad_revenue) / SUM(ad_spend)
                ELSE NULL
            END AS roas,

            CASE
                WHEN SUM(ad_revenue) > 0
                THEN SUM(ad_spend) / SUM(ad_revenue) * 100
                ELSE NULL
            END AS acos,

            CASE
                WHEN SUM(gross_sales) > 0
                THEN SUM(ad_spend) / SUM(gross_sales) * 100
                ELSE NULL
            END AS tacos

        FROM {TABLE_NAME}

        GROUP BY year_month

        ORDER BY year_month;
    """)

    with engine.connect() as connection:

        result = connection.execute(query)

        return result.fetchall()


# ============================================================
# 3. TOP SKUs BY SALES
# ============================================================

def get_top_skus(limit=10):

    query = text(f"""
        SELECT

            sku,

            SUM(unit_ordered) AS units,
            SUM(gross_sales) AS sales,
            SUM(ad_spend) AS ad_spend,
            SUM(ad_revenue) AS ad_revenue,

            CASE
                WHEN SUM(ad_spend) > 0
                THEN SUM(ad_revenue) / SUM(ad_spend)
                ELSE NULL
            END AS roas

        FROM {TABLE_NAME}

        GROUP BY sku

        ORDER BY sales DESC

        LIMIT :limit;
    """)

    with engine.connect() as connection:

        result = connection.execute(
            query,
            {"limit": limit}
        )

        return result.fetchall()


# ============================================================
# 4. WORST SKUs BY SALES
# ============================================================

def get_worst_skus(limit=10):

    query = text(f"""
        SELECT

            sku,

            SUM(unit_ordered) AS units,
            SUM(gross_sales) AS sales,
            SUM(ad_spend) AS ad_spend,
            SUM(ad_revenue) AS ad_revenue,

            CASE
                WHEN SUM(ad_spend) > 0
                THEN SUM(ad_revenue) / SUM(ad_spend)
                ELSE NULL
            END AS roas

        FROM {TABLE_NAME}

        GROUP BY sku

        HAVING SUM(gross_sales) > 0

        ORDER BY sales ASC

        LIMIT :limit;
    """)

    with engine.connect() as connection:

        result = connection.execute(
            query,
            {"limit": limit}
        )

        return result.fetchall()


# ============================================================
# 5. ADVERTISING PERFORMANCE
# ============================================================

def get_advertising_performance():

    query = text(f"""
        SELECT

            SUM(ad_spend) AS ad_spend,

            SUM(ad_revenue) AS ad_revenue,

            SUM(ad_orders) AS ad_orders,

            SUM(impression) AS impressions,

            SUM(click) AS clicks,

            CASE
                WHEN SUM(ad_spend) > 0
                THEN SUM(ad_revenue) / SUM(ad_spend)
                ELSE NULL
            END AS roas,

            CASE
                WHEN SUM(ad_revenue) > 0
                THEN SUM(ad_spend) / SUM(ad_revenue) * 100
                ELSE NULL
            END AS acos,

            CASE
                WHEN SUM(impression) > 0
                THEN SUM(click) / SUM(impression) * 100
                ELSE NULL
            END AS ctr,

            CASE
                WHEN SUM(clicks) > 0
                THEN SUM(ad_orders) / SUM(clicks) * 100
                ELSE NULL
            END AS cvr

        FROM {TABLE_NAME};
    """)

    with engine.connect() as connection:

        result = connection.execute(query)

        return result.fetchone()


# ============================================================
# 6. COUNTRY PERFORMANCE
# ============================================================

def get_country_performance():

    query = text(f"""
        SELECT

            country,

            SUM(unit_ordered) AS units,

            SUM(gross_sales) AS sales,

            SUM(ad_spend) AS ad_spend,

            SUM(ad_revenue) AS ad_revenue,

            CASE
                WHEN SUM(ad_spend) > 0
                THEN SUM(ad_revenue) / SUM(ad_spend)
                ELSE NULL
            END AS roas,

            CASE
                WHEN SUM(gross_sales) > 0
                THEN SUM(ad_spend) / SUM(gross_sales) * 100
                ELSE NULL
            END AS tacos

        FROM {TABLE_NAME}

        GROUP BY country

        ORDER BY sales DESC;
    """)

    with engine.connect() as connection:

        result = connection.execute(query)

        return result.fetchall()


# ============================================================
# 7. INVENTORY RISK
# ============================================================

def get_inventory_risk(limit=20):

    query = text(f"""
        SELECT

            sku,

            country,

            year_month,

            unit_ordered,

            gross_sales,

            fba_inv,

            awd,

            moc_sellable,

            quality_status,

            CASE
                WHEN fba_inv <= 0
                     AND unit_ordered > 0
                THEN 'CRITICAL'

                WHEN fba_inv <= unit_ordered * 2
                THEN 'HIGH'

                ELSE 'NORMAL'

            END AS inventory_risk

        FROM {TABLE_NAME}

        WHERE unit_ordered > 0

        ORDER BY

            CASE
                WHEN fba_inv <= 0
                     AND unit_ordered > 0
                THEN 1

                WHEN fba_inv <= unit_ordered * 2
                THEN 2

                ELSE 3

            END,

            unit_ordered DESC

        LIMIT :limit;
    """)

    with engine.connect() as connection:

        result = connection.execute(
            query,
            {"limit": limit}
        )

        return result.fetchall()


# ============================================================
# 8. HIGH ACOS PRODUCTS
# ============================================================

def get_high_acos_products(limit=20):

    query = text(f"""
        SELECT

            sku,

            SUM(gross_sales) AS sales,

            SUM(ad_spend) AS ad_spend,

            SUM(ad_revenue) AS ad_revenue,

            CASE
                WHEN SUM(ad_revenue) > 0
                THEN SUM(ad_spend) / SUM(ad_revenue) * 100
                ELSE NULL
            END AS acos,

            CASE
                WHEN SUM(ad_spend) > 0
                THEN SUM(ad_revenue) / SUM(ad_spend)
                ELSE NULL
            END AS roas

        FROM {TABLE_NAME}

        GROUP BY sku

        HAVING SUM(ad_spend) > 0

        ORDER BY acos DESC

        LIMIT :limit;
    """)

    with engine.connect() as connection:

        result = connection.execute(
            query,
            {"limit": limit}
        )

        return result.fetchall()


# ============================================================
# 9. ZERO SALES BUT AD SPEND
# ============================================================

def get_zero_sales_ad_spend(limit=20):

    query = text(f"""
        SELECT

            sku,

            country,

            year_month,

            gross_sales,

            ad_spend,

            ad_revenue,

            impression,

            click,

            ad_orders

        FROM {TABLE_NAME}

        WHERE gross_sales = 0
          AND ad_spend > 0

        ORDER BY ad_spend DESC

        LIMIT :limit;
    """)

    with engine.connect() as connection:

        result = connection.execute(
            query,
            {"limit": limit}
        )

        return result.fetchall()


# ============================================================
# 10. DATA QUALITY ISSUES
# ============================================================

def get_data_quality_summary():

    query = text(f"""
        SELECT

            quality_status,

            COUNT(*) AS row_count

        FROM {TABLE_NAME}

        GROUP BY quality_status

        ORDER BY row_count DESC;
    """)

    with engine.connect() as connection:

        result = connection.execute(query)

        return result.fetchall()


# ============================================================
# MAIN TEST
# ============================================================

def main():

    print()
    print("=" * 80)
    print("          AI BUSINESS ANALYST - ANALYTICS ENGINE")
    print("=" * 80)


    # --------------------------------------------------------
    # OVERALL KPIs
    # --------------------------------------------------------

    print()
    print("1. OVERALL BUSINESS KPIs")
    print("-" * 80)

    data = get_business_kpis()

    print(f"Rows              : {data.rows:,}")
    print(f"Unique SKUs       : {data.unique_skus:,}")
    print(f"Countries         : {data.countries:,}")
    print(f"First Month       : {data.first_month}")
    print(f"Last Month        : {data.last_month}")

    print(f"Total Units       : {data.total_units:,.0f}")
    print(f"Total Sales       : ${data.total_sales:,.2f}")
    print(f"Total Ad Spend    : ${data.total_ad_spend:,.2f}")
    print(f"Total Ad Revenue  : ${data.total_ad_revenue:,.2f}")
    print(f"Organic Sales     : ${data.total_organic_sales:,.2f}")


    # --------------------------------------------------------
    # MONTHLY PERFORMANCE
    # --------------------------------------------------------

    print()
    print("2. MONTHLY PERFORMANCE")
    print("-" * 80)

    monthly = get_monthly_performance()

    for row in monthly:

        print(
            f"{row.year_month} | "
            f"Sales=${row.sales:,.2f} | "
            f"Ad Spend=${row.ad_spend:,.2f} | "
            f"Ad Revenue=${row.ad_revenue:,.2f} | "
            f"ROAS={row.roas:.2f}x"
            if row.roas is not None
            else f"{row.year_month} | ROAS=N/A"
        )


    # --------------------------------------------------------
    # TOP SKUs
    # --------------------------------------------------------

    print()
    print("3. TOP 10 SKUs BY SALES")
    print("-" * 80)

    top_skus = get_top_skus(10)

    for index, row in enumerate(top_skus, start=1):

        print(
            f"{index:02d}. "
            f"{row.sku} | "
            f"Sales=${row.sales:,.2f} | "
            f"Units={row.units:,.0f} | "
            f"ROAS={row.roas:.2f}x"
            if row.roas is not None
            else f"{index:02d}. {row.sku} | ROAS=N/A"
        )


    # --------------------------------------------------------
    # COUNTRY PERFORMANCE
    # --------------------------------------------------------

    print()
    print("4. COUNTRY PERFORMANCE")
    print("-" * 80)

    countries = get_country_performance()

    for row in countries:

        print(
            f"{row.country} | "
            f"Sales=${row.sales:,.2f} | "
            f"Ad Spend=${row.ad_spend:,.2f} | "
            f"ROAS={row.roas:.2f}x"
            if row.roas is not None
            else f"{row.country} | ROAS=N/A"
        )


    # --------------------------------------------------------
    # HIGH ACOS
    # --------------------------------------------------------

    print()
    print("5. HIGH ACOS PRODUCTS")
    print("-" * 80)

    high_acos = get_high_acos_products(10)

    for row in high_acos:

        acos_display = (
            f"{row.acos:.2f}%"
            if row.acos is not None
            else "N/A"
        )

        roas_display = (
            f"{row.roas:.2f}x"
            if row.roas is not None
            else "N/A"
        )

        print(
            f"{row.sku} | "
            f"Sales=${row.sales:,.2f} | "
            f"Ad Spend=${row.ad_spend:,.2f} | "
            f"ACOS={acos_display} | "
            f"ROAS={roas_display}"
        )


    # --------------------------------------------------------
    # ZERO SALES + AD SPEND
    # --------------------------------------------------------

    print()
    print("6. ZERO SALES BUT AD SPEND")
    print("-" * 80)

    zero_sales = get_zero_sales_ad_spend(10)

    for row in zero_sales:

        print(
            f"{row.sku} | "
            f"{row.country} | "
            f"{row.year_month} | "
            f"Ad Spend=${row.ad_spend:,.2f}"
        )


    # --------------------------------------------------------
    # DATA QUALITY
    # --------------------------------------------------------

    print()
    print("7. DATA QUALITY")
    print("-" * 80)

    quality = get_data_quality_summary()

    for row in quality:

        print(
            f"{row.quality_status:<12} | "
            f"{row.row_count:,} rows"
        )


    print()
    print("=" * 80)
    print("              ANALYTICS ENGINE TEST COMPLETED")
    print("=" * 80)
    print()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()