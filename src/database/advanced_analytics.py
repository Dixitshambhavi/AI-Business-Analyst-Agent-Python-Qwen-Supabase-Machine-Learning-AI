from pathlib import Path
import sys

from sqlalchemy import text


# ============================================================
# PROJECT PATH
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))


from src.database.connection import engine


# ============================================================
# DATABASE TABLE
# ============================================================

TABLE_NAME = "business_sales"


# ============================================================
# HELPER
# ============================================================

def execute_query(query, params=None):

    with engine.connect() as connection:

        result = connection.execute(
            query,
            params or {}
        )

        return result.fetchall()


# ============================================================
# 1. MONTH-OVER-MONTH GROWTH
# ============================================================

def get_monthly_growth():

    query = text(f"""
        WITH monthly AS (

            SELECT

                year_month,

                SUM(gross_sales) AS sales,

                SUM(ad_spend) AS ad_spend,

                SUM(ad_revenue) AS ad_revenue,

                SUM(unit_ordered) AS units

            FROM {TABLE_NAME}

            GROUP BY year_month

        ),

        with_previous AS (

            SELECT

                year_month,
                sales,
                ad_spend,
                ad_revenue,
                units,

                LAG(sales)
                    OVER (ORDER BY year_month)
                    AS previous_sales,

                LAG(ad_spend)
                    OVER (ORDER BY year_month)
                    AS previous_ad_spend,

                LAG(ad_revenue)
                    OVER (ORDER BY year_month)
                    AS previous_ad_revenue

            FROM monthly

        )

        SELECT

            year_month,

            sales,

            ad_spend,

            ad_revenue,

            units,

            previous_sales,

            CASE
                WHEN previous_sales > 0
                THEN
                    (sales - previous_sales)
                    / previous_sales * 100
                ELSE NULL
            END AS sales_growth_pct,

            CASE
                WHEN previous_ad_spend > 0
                THEN
                    (ad_spend - previous_ad_spend)
                    / previous_ad_spend * 100
                ELSE NULL
            END AS ad_spend_growth_pct,

            CASE
                WHEN previous_ad_revenue > 0
                THEN
                    (ad_revenue - previous_ad_revenue)
                    / previous_ad_revenue * 100
                ELSE NULL
            END AS ad_revenue_growth_pct,

            CASE
                WHEN ad_spend > 0
                THEN ad_revenue / ad_spend
                ELSE NULL
            END AS roas

        FROM with_previous

        ORDER BY year_month;
    """)

    return execute_query(query)


# ============================================================
# 2. SKU PERFORMANCE SCORE
# ============================================================

def get_sku_performance(limit=20):

    query = text(f"""
        WITH sku_metrics AS (

            SELECT

                sku,

                SUM(gross_sales) AS sales,

                SUM(unit_ordered) AS units,

                SUM(ad_spend) AS ad_spend,

                SUM(ad_revenue) AS ad_revenue,

                SUM(organic_sale) AS organic_sales,

                SUM(fba_inv) AS fba_inventory,

                CASE
                    WHEN SUM(ad_spend) > 0
                    THEN SUM(ad_revenue) / SUM(ad_spend)
                    ELSE NULL
                END AS roas,

                CASE
                    WHEN SUM(ad_revenue) > 0
                    THEN
                        SUM(ad_spend)
                        / SUM(ad_revenue) * 100
                    ELSE NULL
                END AS acos

            FROM {TABLE_NAME}

            GROUP BY sku

        )

        SELECT

            sku,

            sales,

            units,

            ad_spend,

            ad_revenue,

            organic_sales,

            fba_inventory,

            roas,

            acos,

            CASE

                WHEN sales >= 1000000
                     AND roas >= 4
                THEN 'STAR'

                WHEN sales >= 500000
                     AND roas >= 3
                THEN 'STRONG'

                WHEN sales >= 100000
                     AND roas < 2
                THEN 'HIGH_REVENUE_LOW_ROAS'

                WHEN ad_spend > 0
                     AND ad_revenue = 0
                THEN 'ADVERTISING_RISK'

                WHEN sales = 0
                     AND ad_spend > 0
                THEN 'ZERO_SALES_AD_SPEND'

                ELSE 'NORMAL'

            END AS performance_category

        FROM sku_metrics

        ORDER BY sales DESC

        LIMIT :limit;
    """)

    return execute_query(
        query,
        {"limit": limit}
    )


# ============================================================
# 3. ADVERTISING WASTE
# ============================================================

def get_advertising_waste(limit=20):

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

            ad_orders,

            CASE

                WHEN gross_sales = 0
                     AND ad_spend > 0
                THEN 'ZERO_SALES'

                WHEN ad_revenue = 0
                     AND ad_spend > 0
                THEN 'ZERO_AD_REVENUE'

                WHEN ad_spend > 0
                     AND ad_revenue > 0
                     AND ad_spend / ad_revenue * 100 >= 100
                THEN 'HIGH_ACOS'

                WHEN ad_spend > 0
                     AND ad_revenue > 0
                     AND ad_revenue / ad_spend < 1
                THEN 'ROAS_BELOW_1'

                ELSE 'NORMAL'

            END AS waste_category

        FROM {TABLE_NAME}

        WHERE ad_spend > 0

        ORDER BY

            CASE

                WHEN gross_sales = 0
                     AND ad_spend > 0
                THEN 1

                WHEN ad_revenue = 0
                     AND ad_spend > 0
                THEN 2

                WHEN ad_spend > 0
                     AND ad_revenue > 0
                     AND ad_spend / ad_revenue * 100 >= 100
                THEN 3

                ELSE 4

            END,

            ad_spend DESC

        LIMIT :limit;
    """)

    return execute_query(
        query,
        {"limit": limit}
    )


# ============================================================
# 4. INVENTORY RISK
# ============================================================

def get_inventory_risk(limit=20):

    query = text(f"""
        WITH sku_inventory AS (

            SELECT

                sku,

                country,

                SUM(unit_ordered) AS units,

                SUM(gross_sales) AS sales,

                AVG(fba_inv) AS avg_fba_inventory,

                AVG(awd) AS avg_awd,

                AVG(moc_sellable) AS avg_moc_sellable

            FROM {TABLE_NAME}

            GROUP BY
                sku,
                country

        )

        SELECT

            sku,

            country,

            units,

            sales,

            avg_fba_inventory,

            avg_awd,

            avg_moc_sellable,

            CASE

                WHEN avg_fba_inventory <= 0
                     AND units > 0
                THEN 'CRITICAL'

                WHEN avg_fba_inventory < units * 0.25
                THEN 'HIGH'

                WHEN avg_fba_inventory < units * 0.50
                THEN 'MEDIUM'

                ELSE 'NORMAL'

            END AS inventory_risk

        FROM sku_inventory

        WHERE units > 0

        ORDER BY

            CASE

                WHEN avg_fba_inventory <= 0
                     AND units > 0
                THEN 1

                WHEN avg_fba_inventory < units * 0.25
                THEN 2

                WHEN avg_fba_inventory < units * 0.50
                THEN 3

                ELSE 4

            END,

            sales DESC

        LIMIT :limit;
    """)

    return execute_query(
        query,
        {"limit": limit}
    )


# ============================================================
# 5. COUNTRY PERFORMANCE
# ============================================================

def get_country_analysis():

    query = text(f"""
        WITH country_metrics AS (

            SELECT

                country,

                SUM(gross_sales) AS sales,

                SUM(unit_ordered) AS units,

                SUM(ad_spend) AS ad_spend,

                SUM(ad_revenue) AS ad_revenue,

                SUM(organic_sale) AS organic_sales

            FROM {TABLE_NAME}

            GROUP BY country

        )

        SELECT

            country,

            sales,

            units,

            ad_spend,

            ad_revenue,

            organic_sales,

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
            END AS organic_sales_pct,

            CASE

                WHEN ad_spend > 0
                     AND ad_revenue / ad_spend >= 4
                THEN 'HIGH_EFFICIENCY'

                WHEN ad_spend > 0
                     AND ad_revenue / ad_spend < 2
                THEN 'LOW_EFFICIENCY'

                ELSE 'NORMAL'

            END AS market_category

        FROM country_metrics

        ORDER BY sales DESC;
    """)

    return execute_query(query)


# ============================================================
# 6. MONTHLY ANOMALIES
# ============================================================

def get_monthly_anomalies():

    query = text(f"""
        WITH monthly AS (

            SELECT

                year_month,

                SUM(gross_sales) AS sales,

                SUM(ad_spend) AS ad_spend,

                SUM(ad_revenue) AS ad_revenue,

                CASE
                    WHEN SUM(ad_spend) > 0
                    THEN SUM(ad_revenue) / SUM(ad_spend)
                    ELSE NULL
                END AS roas

            FROM {TABLE_NAME}

            GROUP BY year_month

        ),

        statistics AS (

            SELECT

                AVG(sales) AS avg_sales,

                STDDEV_POP(sales) AS std_sales,

                AVG(ad_spend) AS avg_ad_spend,

                STDDEV_POP(ad_spend) AS std_ad_spend,

                AVG(roas) AS avg_roas,

                STDDEV_POP(roas) AS std_roas

            FROM monthly

        )

        SELECT

            m.year_month,

            m.sales,

            m.ad_spend,

            m.ad_revenue,

            m.roas,

            CASE

                WHEN s.std_sales > 0
                     AND ABS(
                         m.sales - s.avg_sales
                     ) / s.std_sales >= 2
                THEN 'SALES_ANOMALY'

                WHEN s.std_ad_spend > 0
                     AND ABS(
                         m.ad_spend - s.avg_ad_spend
                     ) / s.std_ad_spend >= 2
                THEN 'AD_SPEND_ANOMALY'

                WHEN s.std_roas > 0
                     AND ABS(
                         m.roas - s.avg_roas
                     ) / s.std_roas >= 2
                THEN 'ROAS_ANOMALY'

                ELSE 'NORMAL'

            END AS anomaly_type

        FROM monthly m

        CROSS JOIN statistics s

        ORDER BY m.year_month;
    """)

    return execute_query(query)


# ============================================================
# 7. BUSINESS OPPORTUNITIES
# ============================================================

def get_business_opportunities(limit=20):

    query = text(f"""
        SELECT

            sku,

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
                THEN
                    SUM(organic_sale)
                    / SUM(gross_sales) * 100

                ELSE NULL

            END AS organic_sales_pct,

            CASE

                WHEN SUM(ad_spend) > 0
                     AND SUM(ad_revenue) / SUM(ad_spend) >= 4
                     AND SUM(gross_sales) >= 100000
                THEN 'SCALE_ADVERTISING'

                WHEN SUM(gross_sales) >= 100000
                     AND SUM(ad_spend) = 0
                THEN 'LOW_ADVERTISING_COVERAGE'

                WHEN SUM(gross_sales) >= 100000
                     AND SUM(organic_sale)
                         / NULLIF(SUM(gross_sales), 0) >= 0.60
                THEN 'STRONG_ORGANIC'

                ELSE 'NORMAL'

            END AS opportunity

        FROM {TABLE_NAME}

        GROUP BY sku

        HAVING SUM(gross_sales) > 0

        ORDER BY

            CASE

                WHEN SUM(ad_spend) > 0
                     AND SUM(ad_revenue) / SUM(ad_spend) >= 4
                     AND SUM(gross_sales) >= 100000
                THEN 1

                WHEN SUM(gross_sales) >= 100000
                     AND SUM(ad_spend) = 0
                THEN 2

                WHEN SUM(gross_sales) >= 100000
                     AND SUM(organic_sale)
                         / NULLIF(SUM(gross_sales), 0) >= 0.60
                THEN 3

                ELSE 4

            END,

            sales DESC

        LIMIT :limit;
    """)

    return execute_query(
        query,
        {"limit": limit}
    )


# ============================================================
# 8. EXECUTIVE SUMMARY
# ============================================================

def get_executive_summary():

    query = text(f"""
        SELECT

            SUM(gross_sales) AS sales,

            SUM(ad_spend) AS ad_spend,

            SUM(ad_revenue) AS ad_revenue,

            SUM(organic_sale) AS organic_sales,

            SUM(unit_ordered) AS units,

            CASE
                WHEN SUM(ad_spend) > 0
                THEN SUM(ad_revenue) / SUM(ad_spend)
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

    result = execute_query(query)

    return result[0]


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 90)
    print("             AI BUSINESS ANALYST - ADVANCED ANALYTICS")
    print("=" * 90)


    # ========================================================
    # EXECUTIVE SUMMARY
    # ========================================================

    print()
    print("1. EXECUTIVE BUSINESS SUMMARY")
    print("-" * 90)

    summary = get_executive_summary()

    print(f"Total Sales       : ${summary.sales:,.2f}")
    print(f"Total Units       : {summary.units:,.0f}")
    print(f"Ad Spend          : ${summary.ad_spend:,.2f}")
    print(f"Ad Revenue        : ${summary.ad_revenue:,.2f}")
    print(f"Organic Sales     : ${summary.organic_sales:,.2f}")

    if summary.roas is not None:
        print(f"Overall ROAS      : {summary.roas:.2f}x")
    else:
        print("Overall ROAS      : N/A")

    if summary.tacos is not None:
        print(f"Overall TACOS     : {summary.tacos:.2f}%")
    else:
        print("Overall TACOS     : N/A")

    if summary.organic_pct is not None:
        print(f"Organic Sales %   : {summary.organic_pct:.2f}%")
    else:
        print("Organic Sales %   : N/A")


    # ========================================================
    # MONTHLY GROWTH
    # ========================================================

    print()
    print("2. MONTHLY GROWTH")
    print("-" * 90)

    monthly = get_monthly_growth()

    for row in monthly:

        sales_growth = (
            f"{row.sales_growth_pct:+.2f}%"
            if row.sales_growth_pct is not None
            else "N/A"
        )

        ad_growth = (
            f"{row.ad_spend_growth_pct:+.2f}%"
            if row.ad_spend_growth_pct is not None
            else "N/A"
        )

        roas = (
            f"{row.roas:.2f}x"
            if row.roas is not None
            else "N/A"
        )

        print(
            f"{row.year_month} | "
            f"Sales=${row.sales:,.2f} | "
            f"Sales Growth={sales_growth} | "
            f"Ad Spend Growth={ad_growth} | "
            f"ROAS={roas}"
        )


    # ========================================================
    # SKU PERFORMANCE
    # ========================================================

    print()
    print("3. SKU PERFORMANCE")
    print("-" * 90)

    sku_data = get_sku_performance(20)

    for row in sku_data:

        roas = (
            f"{row.roas:.2f}x"
            if row.roas is not None
            else "N/A"
        )

        print(
            f"{row.sku} | "
            f"Sales=${row.sales:,.2f} | "
            f"Units={row.units:,.0f} | "
            f"Ad Spend=${row.ad_spend:,.2f} | "
            f"ROAS={roas} | "
            f"Category={row.performance_category}"
        )


    # ========================================================
    # ADVERTISING WASTE
    # ========================================================

    print()
    print("4. ADVERTISING WASTE / RISK")
    print("-" * 90)

    waste = get_advertising_waste(20)

    for row in waste:

        print(
            f"{row.sku} | "
            f"{row.country} | "
            f"{row.year_month} | "
            f"Sales=${row.gross_sales:,.2f} | "
            f"Ad Spend=${row.ad_spend:,.2f} | "
            f"Ad Revenue=${row.ad_revenue:,.2f} | "
            f"Risk={row.waste_category}"
        )


    # ========================================================
    # INVENTORY RISK
    # ========================================================

    print()
    print("5. INVENTORY RISK")
    print("-" * 90)

    inventory = get_inventory_risk(20)

    for row in inventory:

        print(
            f"{row.sku} | "
            f"{row.country} | "
            f"Units={row.units:,.0f} | "
            f"Sales=${row.sales:,.2f} | "
            f"FBA Inventory={row.avg_fba_inventory:,.2f} | "
            f"Risk={row.inventory_risk}"
        )


    # ========================================================
    # COUNTRY ANALYSIS
    # ========================================================

    print()
    print("6. COUNTRY ANALYSIS")
    print("-" * 90)

    countries = get_country_analysis()

    for row in countries:

        roas = (
            f"{row.roas:.2f}x"
            if row.roas is not None
            else "N/A"
        )

        print(
            f"{row.country} | "
            f"Sales=${row.sales:,.2f} | "
            f"Ad Spend=${row.ad_spend:,.2f} | "
            f"ROAS={roas} | "
            f"TACOS={row.tacos:.2f}% | "
            f"Organic={row.organic_sales_pct:.2f}% | "
            f"Category={row.market_category}"
        )


    # ========================================================
    # MONTHLY ANOMALIES
    # ========================================================

    print()
    print("7. MONTHLY ANOMALIES")
    print("-" * 90)

    anomalies = get_monthly_anomalies()

    for row in anomalies:

        roas = (
            f"{row.roas:.2f}x"
            if row.roas is not None
            else "N/A"
        )

        print(
            f"{row.year_month} | "
            f"Sales=${row.sales:,.2f} | "
            f"Ad Spend=${row.ad_spend:,.2f} | "
            f"ROAS={roas} | "
            f"Anomaly={row.anomaly_type}"
        )


    # ========================================================
    # BUSINESS OPPORTUNITIES
    # ========================================================

    print()
    print("8. BUSINESS OPPORTUNITIES")
    print("-" * 90)

    opportunities = get_business_opportunities(20)

    for row in opportunities:

        roas = (
            f"{row.roas:.2f}x"
            if row.roas is not None
            else "N/A"
        )

        organic_pct = (
            f"{row.organic_sales_pct:.2f}%"
            if row.organic_sales_pct is not None
            else "N/A"
        )

        print(
            f"{row.sku} | "
            f"Sales=${row.sales:,.2f} | "
            f"ROAS={roas} | "
            f"Organic={organic_pct} | "
            f"Opportunity={row.opportunity}"
        )


    # ========================================================
    # COMPLETE
    # ========================================================

    print()
    print("=" * 90)
    print("             ADVANCED ANALYTICS COMPLETED")
    print("=" * 90)
    print()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()