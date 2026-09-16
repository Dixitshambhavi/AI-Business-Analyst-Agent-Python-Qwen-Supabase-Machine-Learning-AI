# ============================================================
# TRUSTED BUSINESS CAPABILITIES
# ============================================================

CAPABILITIES = {

    "EXECUTIVE_KPI": {
        "description": "Overall business KPIs",
        "tool": "executive_analysis",
    },

    "PRODUCT_RANKING": {
        "description": (
            "Rank products/SKUs by gross sales with optional "
            "country, year, and month filters."
        ),
        "tool": "product_ranking",
    },

    "TOP_PRODUCTS": {
        "description": (
            "Top products/SKUs by gross sales without filters."
        ),
        "tool": "top_products",
    },

    "MONTHLY_PERFORMANCE": {
        "description": (
            "Sales and advertising performance by month"
        ),
        "tool": "monthly_performance",
    },

    "SALES_FORECAST": {
        "description": (
            "Forecast future monthly sales using trusted "
            "historical monthly sales data."
        ),
        "tool": "sales_forecast",
    },

    "COUNTRY_PERFORMANCE": {
        "description": (
            "Sales and advertising performance by country"
        ),
        "tool": "country_performance",
    },

    "COMPARISON_ANALYSIS": {
        "description": (
            "Compare two countries or business dimensions "
            "using trusted sales, units, ad spend, ad revenue, "
            "ROAS, and TACOS calculations."
        ),
        "tool": "comparison_analysis",
    },

    "TREND_ANALYSIS": {
        "description": (
            "Analyze business trends over time including "
            "sales growth, units, ad spend, ad revenue, ROAS, "
            "TACOS, best/worst months, and major changes."
        ),
        "tool": "trend_analysis",
    },

    "ADVERTISING_RISKS": {
        "description": "Advertising efficiency risks",
        "tool": "advertising_risks",
    },

    "INVENTORY_RISKS": {
        "description": "Inventory risk using trusted business rules",
        "tool": "inventory_risks",
    },

    "INVENTORY_RISKS_FOR_SKUS": {
        "description": (
            "Inventory risk for a specific list of SKUs"
        ),
        "tool": "inventory_risks_for_skus",
    },

    "DATA_QUALITY": {
        "description": "Data quality status and anomalies",
        "tool": "data_quality",
    },
}


# ============================================================
# TRUSTED METRIC DEFINITIONS
# ============================================================

METRIC_DEFINITIONS = {

    "sales": "SUM(gross_sales)",

    "units": "SUM(unit_ordered)",

    "ad_spend": "SUM(ad_spend)",

    "ad_revenue": "SUM(ad_revenue)",

    "organic_sales": "SUM(organic_sale)",

    "roas": (
        "SUM(ad_revenue) / "
        "NULLIF(SUM(ad_spend), 0)"
    ),

    "tacos": (
        "SUM(ad_spend) / "
        "NULLIF(SUM(gross_sales), 0) * 100"
    ),
}