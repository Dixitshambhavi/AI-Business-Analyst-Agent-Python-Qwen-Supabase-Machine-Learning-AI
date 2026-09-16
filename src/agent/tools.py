from pathlib import Path
import sys


# ============================================================
# PROJECT PATH
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))


# ============================================================
# BUSINESS INTELLIGENCE IMPORTS
# ============================================================

from src.tools.business_intelligence import (
    executive_kpis,
    monthly_performance,
    trend_analysis,
    top_products,
    product_ranking,
    advertising_risks,
    inventory_risks,
    inventory_risks_for_skus,
    country_performance,
    comparison_analysis as bi_comparison_analysis,
    data_quality,
)

from src.tools.driver_analysis import driver_analysis
from src.tools.forecasting import forecast_sales


# ============================================================
# TOOL 1 — EXECUTIVE BUSINESS ANALYSIS
# ============================================================

def get_executive_analysis():

    return {
        "tool": "executive_analysis",
        "description": "Returns overall business KPIs.",
        "data": executive_kpis(),
    }


# ============================================================
# TOOL 2 — MONTHLY PERFORMANCE
# ============================================================

def get_monthly_analysis():

    return {
        "tool": "monthly_performance",
        "description": (
            "Returns monthly sales, advertising "
            "and ROAS performance."
        ),
        "data": monthly_performance(),
    }


# ============================================================
# TOOL 2B — TREND ANALYSIS
# ============================================================

def get_trend_analysis(
    country=None,
    year=None,
):

    result = trend_analysis(
        country=country,
        year=year,
    )

    return {
        "tool": "trend_analysis",
        "description": (
            "Returns business trends including "
            "sales growth, units, ad spend, ad revenue, "
            "ROAS and TACOS."
        ),
        "parameters": {
            "country": country,
            "year": year,
        },
        "data": result,
    }


# ============================================================
# TOOL 3 — TOP PRODUCTS
# ============================================================

def get_top_products(limit=10):

    return {
        "tool": "top_products",
        "description": (
            f"Returns the top {limit} products by sales."
        ),
        "parameters": {
            "limit": limit,
        },
        "data": top_products(limit),
    }


# ============================================================
# TOOL 3B — PARAMETERIZED PRODUCT RANKING
# ============================================================

def get_product_ranking(
    country=None,
    year=None,
    month=None,
    limit=10,
):

    return {
        "tool": "product_ranking",
        "description": (
            "Returns products ranked by gross sales "
            "with optional country, year and month filters."
        ),
        "parameters": {
            "country": country,
            "year": year,
            "month": month,
            "limit": limit,
        },
        "data": product_ranking(
            country=country,
            year=year,
            month=month,
            limit=limit,
        ),
    }


# ============================================================
# TOOL 4 — ADVERTISING RISKS
# ============================================================

def get_advertising_analysis(limit=20):

    return {
        "tool": "advertising_risks",
        "description": (
            "Identifies products and periods with "
            "advertising efficiency risks."
        ),
        "parameters": {
            "limit": limit,
        },
        "data": advertising_risks(limit),
    }


# ============================================================
# TOOL 5 — INVENTORY RISKS
# ============================================================

def get_inventory_analysis(limit=20):

    return {
        "tool": "inventory_risks",
        "description": (
            "Identifies products with inventory risk."
        ),
        "parameters": {
            "limit": limit,
        },
        "data": inventory_risks(limit),
    }


# ============================================================
# TOOL 5B — INVENTORY RISK FOR SPECIFIC SKUS
# ============================================================

def get_inventory_risks_for_skus(skus):

    if not skus:

        return {
            "tool": "inventory_risks_for_skus",
            "description": (
                "No SKUs were supplied for inventory analysis."
            ),
            "requested_skus": [],
            "data": [],
        }

    # --------------------------------------------------------
    # Clean SKU list
    # --------------------------------------------------------

    cleaned_skus = []

    for sku in skus:

        if sku is None:
            continue

        sku = str(sku).strip()

        if not sku:
            continue

        if sku not in cleaned_skus:
            cleaned_skus.append(sku)

    # --------------------------------------------------------
    # Maximum number of SKUs
    # --------------------------------------------------------

    if len(cleaned_skus) > 100:

        raise ValueError(
            "A maximum of 100 SKUs can be checked at once."
        )

    # --------------------------------------------------------
    # Execute trusted inventory logic
    # --------------------------------------------------------

    result = inventory_risks_for_skus(
        cleaned_skus
    )

    return {
        "tool": "inventory_risks_for_skus",
        "description": (
            "Returns inventory-risk information "
            "for the supplied SKUs only."
        ),
        "requested_skus": cleaned_skus,
        "data": result,
    }


# ============================================================
# TOOL 6 — COUNTRY PERFORMANCE
# ============================================================

def get_country_analysis():

    return {
        "tool": "country_performance",
        "description": (
            "Returns business performance by country."
        ),
        "data": country_performance(),
    }


# ============================================================
# TOOL 6B — COUNTRY COMPARISON
# ============================================================

def get_comparison_analysis(
    country1=None,
    country2=None,
    year=None,
    month=None,
):

    if not country1 or not country2:

        raise ValueError(
            "Comparison requires two countries."
        )

    result = bi_comparison_analysis(
        country1=country1,
        country2=country2,
        year=year,
        month=month,
    )

    return {
        "tool": "comparison_analysis",
        "description": (
            "Compares two countries using trusted "
            "sales, units, advertising, ROAS and TACOS metrics."
        ),
        "parameters": {
            "country1": country1,
            "country2": country2,
            "year": year,
            "month": month,
        },
        "data": result,
    }


# ============================================================
# TOOL 7 — DRIVER ANALYSIS
# ============================================================

def get_driver_analysis(
    month,
    country=None,
    limit=10,
):

    result = driver_analysis(
        month=month,
        country=country,
        limit=limit,
    )

    return {
        "tool": "driver_analysis",
        "description": (
            "Identifies the biggest SKU and country contributors "
            "to a month-over-month sales increase or decline."
        ),
        "parameters": {
            "month": month,
            "country": country,
            "limit": limit,
        },
        "data": result,
    }


# ============================================================
# TOOL 8 — SALES FORECAST
# ============================================================

def get_sales_forecast(
    months_ahead=3,
    country=None,
    year=None,
):
    """
    Returns trusted future monthly sales forecasts.

    Parameters are optional and come from the user's natural-
    language question.

    Examples:

        Forecast sales for India
        -> country="IN"

        Forecast sales for India for the next 6 months
        -> country="IN", months_ahead=6

        Forecast sales for India in 2026
        -> country="IN", year=2026

        Give me a sales forecast
        -> country=None, months_ahead=3

    The LLM does not calculate forecast values.
    """

    # --------------------------------------------------------
    # Normalize months_ahead
    # --------------------------------------------------------

    try:
        months_ahead = int(
            months_ahead
        )
    except (TypeError, ValueError):
        months_ahead = 3

    months_ahead = max(
        1,
        min(months_ahead, 12)
    )

    # --------------------------------------------------------
    # Normalize country
    # --------------------------------------------------------

    if country is not None:

        country = str(
            country
        ).strip().upper()

    # --------------------------------------------------------
    # Normalize year
    # --------------------------------------------------------

    if year is not None:

        try:
            year = int(year)
        except (TypeError, ValueError):
            year = None

    # --------------------------------------------------------
    # Execute trusted forecasting logic
    # --------------------------------------------------------

    result = forecast_sales(
        months_ahead=months_ahead,
        country=country,
        year=year,
    )

    return {
        "tool": "sales_forecast",

        "description": (
            "Returns historical monthly sales, "
            "automatic model evaluation, selected model, "
            "future forecasts and deterministic business "
            "interpretation."
        ),

        "parameters": {
            "months_ahead": months_ahead,
            "country": country,
            "year": year,
        },

        "data": result,
    }


# ============================================================
# TOOL 9 — DATA QUALITY
# ============================================================

def get_quality_analysis():

    return {
        "tool": "data_quality",
        "description": (
            "Returns data quality status distribution."
        ),
        "data": data_quality(),
    }


# ============================================================
# TOOL REGISTRY
# ============================================================

TOOL_REGISTRY = {

    "executive_analysis":
        get_executive_analysis,

    "monthly_performance":
        get_monthly_analysis,

    "trend_analysis":
        get_trend_analysis,

    "top_products":
        get_top_products,

    "product_ranking":
        get_product_ranking,

    "advertising_risks":
        get_advertising_analysis,

    "inventory_risks":
        get_inventory_analysis,

    "inventory_risks_for_skus":
        get_inventory_risks_for_skus,

    "country_performance":
        get_country_analysis,

    "comparison_analysis":
        get_comparison_analysis,

    "driver_analysis":
        get_driver_analysis,

    "sales_forecast":
        get_sales_forecast,

    "data_quality":
        get_quality_analysis,
}


# ============================================================
# TOOL EXECUTOR
# ============================================================

def execute_tool(
    tool_name,
    **kwargs,
):

    if tool_name not in TOOL_REGISTRY:

        raise ValueError(
            f"Unknown tool: {tool_name}"
        )

    tool = TOOL_REGISTRY[
        tool_name
    ]

    return tool(
        **kwargs
    )


# ============================================================
# HELPER — EXTRACT TOP PRODUCT SKUS
# ============================================================

def extract_skus_from_top_products(
    limit=5,
):
    """
    Returns SKU names from the trusted top_products tool.
    """

    result = get_top_products(
        limit=limit
    )

    products = result["data"]

    skus = [
        product["sku"]
        for product in products
        if product.get("sku")
    ]

    return skus


# ============================================================
# TEST
# ============================================================

def main():

    print()
    print("=" * 90)
    print(
        "                 AI BUSINESS ANALYST - TOOL LAYER"
    )
    print("=" * 90)

    # --------------------------------------------------------
    # 1. EXECUTIVE TOOL
    # --------------------------------------------------------

    print()
    print("1. EXECUTIVE ANALYSIS TOOL")
    print("-" * 90)

    result = execute_tool(
        "executive_analysis"
    )

    data = result["data"]

    print(
        f"Sales    : ${data['sales']:,.2f}"
    )

    print(
        f"Ad Spend : ${data['ad_spend']:,.2f}"
    )

    print(
        f"ROAS     : {data['roas']:.2f}x"
        if data["roas"] is not None
        else "ROAS     : N/A"
    )

    # --------------------------------------------------------
    # 2. TOP PRODUCTS
    # --------------------------------------------------------

    print()
    print("2. TOP PRODUCTS TOOL")
    print("-" * 90)

    products = execute_tool(
        "top_products",
        limit=5,
    )

    for index, product in enumerate(
        products["data"],
        start=1,
    ):

        print(
            f"{index}. "
            f"{product['sku']} | "
            f"Sales=${product['sales']:,.2f}"
        )

    # --------------------------------------------------------
    # 3. PARAMETERIZED PRODUCT RANKING
    # --------------------------------------------------------

    print()
    print(
        "3. PARAMETERIZED PRODUCT RANKING"
    )
    print("-" * 90)

    ranking = execute_tool(
        "product_ranking",
        country="IN",
        year=2026,
        limit=5,
    )

    print(
        "Top 5 SKUs in India for 2026:"
    )

    for index, product in enumerate(
        ranking["data"],
        start=1,
    ):

        print(
            f"{index}. "
            f"{product['sku']} | "
            f"Sales=${product['sales']:,.2f}"
        )

    # --------------------------------------------------------
    # 4. DEPENDENT INVENTORY TOOL
    # --------------------------------------------------------

    print()
    print(
        "4. INVENTORY RISK FOR TOP 5 PRODUCTS"
    )
    print("-" * 90)

    top_5_skus = extract_skus_from_top_products(
        limit=5
    )

    print(
        "Top 5 SKUs:"
    )

    for sku in top_5_skus:

        print(
            f"  ✓ {sku}"
        )

    inventory_result = execute_tool(
        "inventory_risks_for_skus",
        skus=top_5_skus,
    )

    print()
    print(
        "Inventory results:"
    )

    if not inventory_result["data"]:

        print(
            "No inventory-risk records returned."
        )

    else:

        for item in inventory_result["data"]:

            print(
                f"{item['sku']} | "
                f"{item['country']} | "
                f"Sales=${item['sales']:,.2f} | "
                f"FBA={item['fba_inventory']:,.0f} | "
                f"Risk={item['risk']}"
            )

    # --------------------------------------------------------
    # 5. COUNTRY ANALYSIS
    # --------------------------------------------------------

    print()
    print("5. COUNTRY ANALYSIS TOOL")
    print("-" * 90)

    countries = execute_tool(
        "country_performance"
    )

    for country in countries["data"]:

        roas = (
            f"{country['roas']:.2f}x"
            if country["roas"] is not None
            else "N/A"
        )

        print(
            f"{country['country']} | "
            f"Sales=${country['sales']:,.2f} | "
            f"ROAS={roas}"
        )

    # --------------------------------------------------------
    # 6. COUNTRY COMPARISON
    # --------------------------------------------------------

    print()
    print("6. COUNTRY COMPARISON")
    print("-" * 90)

    comparison = execute_tool(
        "comparison_analysis",
        country1="IN",
        country2="US",
    )

    comparison_data = comparison["data"]

    first = comparison_data["country1"]
    second = comparison_data["country2"]

    print(
        f"{first['country']} | "
        f"Sales=${first['sales']:,.2f} | "
        f"ROAS={first['roas']:.2f}x"
        if first["roas"] is not None
        else
        f"{first['country']} | "
        f"Sales=${first['sales']:,.2f} | "
        f"ROAS=N/A"
    )

    print(
        f"{second['country']} | "
        f"Sales=${second['sales']:,.2f} | "
        f"ROAS={second['roas']:.2f}x"
        if second["roas"] is not None
        else
        f"{second['country']} | "
        f"Sales=${second['sales']:,.2f} | "
        f"ROAS=N/A"
    )

    print(
        f"Sales Difference="
        f"${comparison_data['sales_difference']:,.2f}"
    )

    print(
        f"Higher Sales Country="
        f"{comparison_data['higher_sales_country']}"
    )

    # --------------------------------------------------------
    # 7. SALES FORECAST
    # --------------------------------------------------------

    print()
    print("7. SALES FORECAST TOOL")
    print("-" * 90)

    forecast_result = execute_tool(
        "sales_forecast",
        months_ahead=3,
        country="IN",
        year=2026,
    )

    forecast_data = forecast_result["data"]

    print(
        f"Model: "
        f"{forecast_data.get('model', 'N/A')}"
    )

    print(
        f"Country: "
        f"{forecast_result['parameters'].get('country')}"
    )

    print(
        f"Year: "
        f"{forecast_result['parameters'].get('year')}"
    )

    print()
    print("Forecast:")

    for row in forecast_data.get(
        "forecast",
        []
    ):

        print(
            f"{row['month']} | "
            f"Forecast Sales="
            f"${row['forecast_sales']:,.2f}"
        )

    # --------------------------------------------------------
    # 8. AVAILABLE TOOLS
    # --------------------------------------------------------

    print()
    print("8. AVAILABLE AI TOOLS")
    print("-" * 90)

    for name in TOOL_REGISTRY:

        print(
            f"✓ {name}"
        )

    print()
    print("=" * 90)
    print(
        "                 TOOL LAYER READY"
    )
    print("=" * 90)
    print()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()