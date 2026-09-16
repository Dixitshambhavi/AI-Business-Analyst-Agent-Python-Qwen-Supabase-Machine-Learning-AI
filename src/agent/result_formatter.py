from typing import Any


# ============================================================
# NUMBER FORMATTING
# ============================================================

def format_currency(
    value: Any,
    decimals: int = 2
) -> str:
    """
    Format a numeric value as currency.

    We preserve the project's existing display convention ($)
    rather than asking the LLM to infer currency.
    """

    if value is None:
        return "N/A"

    try:
        number = float(value)
    except (TypeError, ValueError):
        return "N/A"

    return f"${number:,.{decimals}f}"


def format_number(
    value: Any,
    decimals: int = 0
) -> str:
    """
    Format a numeric value safely.
    """

    if value is None:
        return "N/A"

    try:
        number = float(value)
    except (TypeError, ValueError):
        return "N/A"

    return f"{number:,.{decimals}f}"


def format_ratio(
    value: Any
) -> str:
    """
    Format ratio such as ROAS.
    """

    if value is None:
        return "N/A"

    try:
        number = float(value)
    except (TypeError, ValueError):
        return "N/A"

    return f"{number:.2f}x"


def format_percentage(
    value: Any
) -> str:
    """
    Format percentage values.
    """

    if value is None:
        return "N/A"

    try:
        number = float(value)
    except (TypeError, ValueError):
        return "N/A"

    return f"{number:.2f}%"


# ============================================================
# PRODUCT RANKING FORMATTER
# ============================================================

def format_product_ranking(
    result: dict,
    title: str = "Product Ranking"
) -> str:
    """
    Deterministically format product-ranking results.

    The values come directly from the trusted Python tool.
    """

    if not isinstance(result, dict):

        raise ValueError(
            "Product ranking result must be a dictionary."
        )

    data = result.get(
        "data",
        []
    )

    if not isinstance(data, list):

        raise ValueError(
            "Product ranking data must be a list."
        )

    if not data:

        return (
            f"{title}\n\n"
            "No matching products were found."
        )

    lines = [
        title,
        ""
    ]

    for index, product in enumerate(
        data,
        start=1
    ):

        sku = product.get(
            "sku",
            "UNKNOWN"
        )

        sales = format_currency(
            product.get("sales")
        )

        units = format_number(
            product.get("units")
        )

        ad_spend = format_currency(
            product.get("ad_spend")
        )

        ad_revenue = format_currency(
            product.get("ad_revenue")
        )

        roas = format_ratio(
            product.get("roas")
        )

        lines.append(
            f"{index}. {sku} | "
            f"Sales: {sales} | "
            f"Units: {units} | "
            f"Ad Spend: {ad_spend} | "
            f"Ad Revenue: {ad_revenue} | "
            f"ROAS: {roas}"
        )

    return "\n".join(lines)


# ============================================================
# EXECUTIVE KPI FORMATTER
# ============================================================

def format_executive_kpis(
    result: dict
) -> str:
    """
    Format executive KPI results.
    """

    if not isinstance(result, dict):

        raise ValueError(
            "Executive KPI result must be a dictionary."
        )

    data = result.get(
        "data",
        {}
    )

    if not isinstance(data, dict):

        raise ValueError(
            "Executive KPI data must be a dictionary."
        )

    lines = [
        "Executive Business KPIs",
        "",
        f"Rows: {format_number(data.get('rows'))}",
        f"Unique SKUs: {format_number(data.get('unique_skus'))}",
        f"Countries: {format_number(data.get('countries'))}",
        f"First Month: {data.get('first_month', 'N/A')}",
        f"Last Month: {data.get('last_month', 'N/A')}",
        f"Units: {format_number(data.get('units'))}",
        f"Sales: {format_currency(data.get('sales'))}",
        f"Ad Spend: {format_currency(data.get('ad_spend'))}",
        f"Ad Revenue: {format_currency(data.get('ad_revenue'))}",
        f"Organic Sales: {format_currency(data.get('organic_sales'))}",
        f"ROAS: {format_ratio(data.get('roas'))}",
        f"TACOS: {format_percentage(data.get('tacos'))}",
        f"Organic Sales %: {format_percentage(data.get('organic_pct'))}",
    ]

    return "\n".join(lines)


# ============================================================
# COUNTRY FORMATTER
# ============================================================

def format_country_performance(
    result: dict
) -> str:
    """
    Format country-performance results.
    """

    data = result.get(
        "data",
        []
    )

    if not data:

        return (
            "Country Performance\n\n"
            "No matching country data was found."
        )

    lines = [
        "Country Performance",
        ""
    ]

    for index, country in enumerate(
        data,
        start=1
    ):

        country_code = country.get(
            "country",
            "UNKNOWN"
        )

        sales = format_currency(
            country.get("sales")
        )

        units = format_number(
            country.get("units")
        )

        ad_spend = format_currency(
            country.get("ad_spend")
        )

        ad_revenue = format_currency(
            country.get("ad_revenue")
        )

        roas = format_ratio(
            country.get("roas")
        )

        tacos = format_percentage(
            country.get("tacos")
        )

        lines.append(
            f"{index}. {country_code} | "
            f"Sales: {sales} | "
            f"Units: {units} | "
            f"Ad Spend: {ad_spend} | "
            f"Ad Revenue: {ad_revenue} | "
            f"ROAS: {roas} | "
            f"TACOS: {tacos}"
        )

    return "\n".join(lines)


# ============================================================
# INVENTORY RISK FORMATTER
# ============================================================

def format_inventory_risks(
    result: dict,
    title: str = "Inventory Risk Analysis"
) -> str:
    """
    Format inventory-risk results.
    """

    if not isinstance(result, dict):

        raise ValueError(
            "Inventory result must be a dictionary."
        )

    data = result.get(
        "data",
        []
    )

    if not data:

        return (
            f"{title}\n\n"
            "No inventory-risk records were found."
        )

    lines = [
        title,
        ""
    ]

    for index, item in enumerate(
        data,
        start=1
    ):

        sku = item.get(
            "sku",
            "UNKNOWN"
        )

        country = item.get(
            "country",
            "UNKNOWN"
        )

        sales = format_currency(
            item.get("sales")
        )

        units = format_number(
            item.get("units")
        )

        fba_inventory = format_number(
            item.get("fba_inventory")
        )

        awd_inventory = format_number(
            item.get("awd_inventory")
        )

        risk = item.get(
            "risk",
            "UNKNOWN"
        )

        lines.append(
            f"{index}. {sku} | "
            f"Country: {country} | "
            f"Sales: {sales} | "
            f"Units: {units} | "
            f"FBA: {fba_inventory} | "
            f"AWD: {awd_inventory} | "
            f"Risk: {risk}"
        )

    return "\n".join(lines)


# ============================================================
# MONTHLY PERFORMANCE FORMATTER
# ============================================================

def format_monthly_performance(
    result: dict
) -> str:
    """
    Format monthly performance results.
    """

    data = result.get(
        "data",
        []
    )

    if not data:

        return (
            "Monthly Performance\n\n"
            "No monthly records were found."
        )

    lines = [
        "Monthly Performance",
        ""
    ]

    for index, month in enumerate(
        data,
        start=1
    ):

        month_name = month.get(
            "month",
            "UNKNOWN"
        )

        sales = format_currency(
            month.get("sales")
        )

        ad_spend = format_currency(
            month.get("ad_spend")
        )

        ad_revenue = format_currency(
            month.get("ad_revenue")
        )

        units = format_number(
            month.get("units")
        )

        roas = format_ratio(
            month.get("roas")
        )

        growth = format_percentage(
            month.get("sales_growth_pct")
        )

        lines.append(
            f"{index}. {month_name} | "
            f"Sales: {sales} | "
            f"Units: {units} | "
            f"Ad Spend: {ad_spend} | "
            f"Ad Revenue: {ad_revenue} | "
            f"ROAS: {roas} | "
            f"Sales Growth: {growth}"
        )

    return "\n".join(lines)


# ============================================================
# SALES FORECAST FORMATTER
# ============================================================
def format_sales_forecast(
    result: dict
) -> str:
    """
    Deterministically format trusted sales-forecast results.

    Supports:
        - country
        - year
        - selected model
        - model evaluation
        - forecast
        - historical sales
        - business explanation
    """

    if not isinstance(result, dict):
        raise ValueError(
            "Sales forecast result must be a dictionary."
        )

    data = result.get(
        "data",
        {}
    )

    if not isinstance(data, dict):
        raise ValueError(
            "Sales forecast data must be a dictionary."
        )

    forecast = data.get(
        "forecast",
        []
    )

    historical = data.get(
        "historical",
        []
    )

    # ========================================================
    # NO FORECAST
    # ========================================================

    if not forecast:

        message = data.get(
            "message",
            "No forecast records were returned."
        )

        return (
            "Sales Forecast\n\n"
            f"{message}"
        )

    lines = [
        "Sales Forecast",
        ""
    ]

    # ========================================================
    # SCOPE
    # ========================================================

    country = data.get(
        "country"
    )

    year = data.get(
        "year"
    )

    if country is not None:

        lines.append(
            f"Country: {country}"
        )

    else:

        lines.append(
            "Country: All Countries"
        )

    if year is not None:

        lines.append(
            f"Year Filter: {year}"
        )

    # ========================================================
    # MODEL
    # ========================================================

    model = data.get(
        "model"
    )

    months_ahead = data.get(
        "months_ahead"
    )

    historical_months = data.get(
        "historical_months"
    )

    last_historical_month = data.get(
        "last_historical_month"
    )

    if model is not None:

        lines.append(
            f"Selected Model: {model}"
        )

    if months_ahead is not None:

        lines.append(
            "Forecast Horizon: "
            f"{format_number(months_ahead)} months"
        )

    if historical_months is not None:

        lines.append(
            "Historical Months Used: "
            f"{format_number(historical_months)}"
        )

    if last_historical_month is not None:

        lines.append(
            f"Last Historical Month: "
            f"{last_historical_month}"
        )

    # ========================================================
    # MODEL EVALUATION
    # ========================================================

    evaluation = data.get(
        "evaluation",
        {}
    )

    if isinstance(
        evaluation,
        dict
    ):

        lines.append("")
        lines.append(
            "Model Evaluation"
        )
        lines.append("")

        selection_metric = evaluation.get(
            "selection_metric"
        )

        validation_months = evaluation.get(
            "validation_months"
        )

        evaluated = evaluation.get(
            "evaluated"
        )

        if evaluated is not None:

            lines.append(
                f"Evaluation Performed: "
                f"{evaluated}"
            )

        if selection_metric:

            lines.append(
                f"Selection Metric: "
                f"{selection_metric}"
            )

        if validation_months is not None:

            lines.append(
                f"Validation Months: "
                f"{format_number(validation_months)}"
            )

        metrics = evaluation.get(
            "metrics",
            []
        )

        if metrics:

            for index, metric in enumerate(
                metrics,
                start=1
            ):

                if not isinstance(
                    metric,
                    dict
                ):
                    continue

                metric_model = metric.get(
                    "model",
                    "UNKNOWN"
                )

                mae = format_currency(
                    metric.get("mae")
                )

                rmse = format_currency(
                    metric.get("rmse")
                )

                mape_value = metric.get(
                    "mape_pct"
                )

                mape = (
                    format_percentage(
                        mape_value
                    )
                    if mape_value is not None
                    else "N/A"
                )

                lines.append(
                    f"{index}. {metric_model} | "
                    f"MAE: {mae} | "
                    f"RMSE: {rmse} | "
                    f"MAPE: {mape}"
                )

    # ========================================================
    # SELECTED MODEL METRICS
    # ========================================================

    selected_metrics = data.get(
        "selected_model_metrics"
    )

    if isinstance(
        selected_metrics,
        dict
    ):

        lines.append("")
        lines.append(
            "Selected Model Metrics"
        )
        lines.append("")

        lines.append(
            f"Model: "
            f"{selected_metrics.get('model', 'N/A')}"
        )

        lines.append(
            f"MAE: "
            f"{format_currency(selected_metrics.get('mae'))}"
        )

        lines.append(
            f"RMSE: "
            f"{format_currency(selected_metrics.get('rmse'))}"
        )

        lines.append(
            f"MAPE: "
            f"{format_percentage(selected_metrics.get('mape_pct'))}"
            if selected_metrics.get("mape_pct") is not None
            else "MAPE: N/A"
        )

    # ========================================================
    # FORECAST
    # ========================================================

    lines.append("")
    lines.append(
        "Forecast"
    )
    lines.append("")

    for index, item in enumerate(
        forecast,
        start=1
    ):

        if not isinstance(
            item,
            dict
        ):
            continue

        month = item.get(
            "month",
            "UNKNOWN"
        )

        forecast_value = format_currency(
            item.get(
                "forecast_sales"
            )
        )

        lines.append(
            f"{index}. {month} | "
            f"Forecast Sales: {forecast_value}"
        )

    # ========================================================
    # BUSINESS INTERPRETATION
    # ========================================================

    explanation = data.get(
        "business_explanation",
        {}
    )

    if isinstance(
        explanation,
        dict
    ):

        lines.append("")
        lines.append(
            "Business Interpretation"
        )
        lines.append("")

        direction = explanation.get(
            "forecast_direction"
        )

        latest_actual = explanation.get(
            "latest_actual_sales"
        )

        first_forecast = explanation.get(
            "first_forecast_sales"
        )

        average_forecast = explanation.get(
            "average_forecast_sales"
        )

        change_pct = explanation.get(
            "forecast_change_pct"
        )

        summary = explanation.get(
            "summary"
        )

        if direction is not None:

            lines.append(
                f"Forecast Direction: "
                f"{direction}"
            )

        if latest_actual is not None:

            lines.append(
                "Latest Actual Sales: "
                f"{format_currency(latest_actual)}"
            )

        if first_forecast is not None:

            lines.append(
                "First Forecast Sales: "
                f"{format_currency(first_forecast)}"
            )

        if average_forecast is not None:

            lines.append(
                "Average Forecast Sales: "
                f"{format_currency(average_forecast)}"
            )

        if change_pct is not None:

            lines.append(
                "First Forecast vs Latest Actual: "
                f"{format_percentage(change_pct)}"
            )

        if summary:

            lines.append("")
            lines.append(
                f"Summary: {summary}"
            )

    # ========================================================
    # HISTORICAL SALES
    # ========================================================

    if historical:

        lines.append("")
        lines.append(
            "Historical Sales"
        )
        lines.append("")

        for index, item in enumerate(
            historical,
            start=1
        ):

            if not isinstance(
                item,
                dict
            ):
                continue

            month = item.get(
                "month",
                "UNKNOWN"
            )

            sales = format_currency(
                item.get("sales")
            )

            lines.append(
                f"{index}. {month} | "
                f"Sales: {sales}"
            )

    return "\n".join(lines)
# ============================================================
# ADVERTISING RISK FORMATTER
# ============================================================

def format_advertising_risks(
    result: dict
) -> str:
    """
    Format advertising-risk results.
    """

    data = result.get(
        "data",
        []
    )

    if not data:

        return (
            "Advertising Risk Analysis\n\n"
            "No advertising-risk records were found."
        )

    lines = [
        "Advertising Risk Analysis",
        ""
    ]

    for index, item in enumerate(
        data,
        start=1
    ):

        sku = item.get(
            "sku",
            "UNKNOWN"
        )

        country = item.get(
            "country",
            "UNKNOWN"
        )

        month = item.get(
            "month",
            "UNKNOWN"
        )

        gross_sales = format_currency(
            item.get("gross_sales")
        )

        ad_spend = format_currency(
            item.get("ad_spend")
        )

        ad_revenue = format_currency(
            item.get("ad_revenue")
        )

        risk = item.get(
            "risk",
            "UNKNOWN"
        )

        lines.append(
            f"{index}. {sku} | "
            f"Country: {country} | "
            f"Month: {month} | "
            f"Sales: {gross_sales} | "
            f"Ad Spend: {ad_spend} | "
            f"Ad Revenue: {ad_revenue} | "
            f"Risk: {risk}"
        )

    return "\n".join(lines)


# ============================================================
# DATA QUALITY FORMATTER
# ============================================================

def format_data_quality(
    result: dict
) -> str:
    """
    Format data-quality results.
    """

    data = result.get(
        "data",
        {}
    )

    if not data:

        return (
            "Data Quality\n\n"
            "No quality information was returned."
        )

    lines = [
        "Data Quality",
        ""
    ]

    for status, count in data.items():

        lines.append(
            f"{status}: {format_number(count)} rows"
        )

    return "\n".join(lines)

# ============================================================
# COMPARISON FORMATTER
# ============================================================

def format_comparison_analysis(
    result: dict
) -> str:
    """
    Format country comparison results deterministically.

    Expected trusted-tool result:
    {
        "tool": "comparison_analysis",
        "parameters": {...},
        "data": ...
    }

    This formatter does not calculate or invent metrics.
    """

    if not isinstance(result, dict):
        raise ValueError(
            "Comparison result must be a dictionary."
        )

    data = result.get("data", [])

    if not data:
        return (
            "Country Comparison\n\n"
            "No comparison data was found."
        )

    # --------------------------------------------------------
    # Case 1: list of country rows
    # --------------------------------------------------------

    if isinstance(data, list):

        lines = [
            "Country Comparison",
            ""
        ]

        for index, country in enumerate(
            data,
            start=1
        ):

            if not isinstance(country, dict):
                continue

            country_code = country.get(
                "country",
                "UNKNOWN"
            )

            sales = format_currency(
                country.get("sales")
            )

            units = format_number(
                country.get("units")
            )

            ad_spend = format_currency(
                country.get("ad_spend")
            )

            ad_revenue = format_currency(
                country.get("ad_revenue")
            )

            roas = format_ratio(
                country.get("roas")
            )

            tacos = format_percentage(
                country.get("tacos")
            )

            organic_sales = format_currency(
                country.get("organic_sales")
            )

            lines.append(
                f"{index}. {country_code} | "
                f"Sales: {sales} | "
                f"Units: {units} | "
                f"Ad Spend: {ad_spend} | "
                f"Ad Revenue: {ad_revenue} | "
                f"ROAS: {roas} | "
                f"TACOS: {tacos} | "
                f"Organic Sales: {organic_sales}"
            )

        return "\n".join(lines)

    # --------------------------------------------------------
    # Case 2: country1 / country2 dictionary
    # --------------------------------------------------------

    if isinstance(data, dict):

        country1 = data.get("country1")
        country2 = data.get("country2")

        if isinstance(country1, dict):
            country1 = country1

        if isinstance(country2, dict):
            country2 = country2

        rows = []

        if isinstance(country1, dict):
            rows.append(country1)

        if isinstance(country2, dict):
            rows.append(country2)

        if rows:
            return format_comparison_analysis({
                "tool": "comparison_analysis",
                "data": rows
            })

    raise ValueError(
        "Unsupported comparison-analysis data format."
    )

# ============================================================
# TREND ANALYSIS FORMATTER
# ============================================================

def format_trend_analysis(
    result: dict
) -> str:
    """
    Format trusted business trend-analysis results.

    Expected tool result:
    {
        "tool": "trend_analysis",
        "parameters": {...},
        "data": {
            "summary": {...},
            "monthly": [...]
        }
    }

    No business metrics are calculated here.
    Values are taken directly from the trusted tool.
    """

    if not isinstance(result, dict):
        raise ValueError(
            "Trend analysis result must be a dictionary."
        )

    data = result.get(
        "data",
        {}
    )

    if not isinstance(data, dict):
        raise ValueError(
            "Trend analysis data must be a dictionary."
        )

    monthly = data.get(
        "monthly",
        []
    )

    summary = data.get(
        "summary",
        {}
    )

    if not monthly:
        return (
            "Trend Analysis\n\n"
            "No trend data was found."
        )

    lines = [
        "Trend Analysis",
        ""
    ]

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    if isinstance(summary, dict) and summary:

        first_month = summary.get(
            "first_month"
        )

        last_month = summary.get(
            "last_month"
        )

        total_sales = summary.get(
            "total_sales"
        )

        total_units = summary.get(
            "total_units"
        )

        total_ad_spend = summary.get(
            "total_ad_spend"
        )

        total_ad_revenue = summary.get(
            "total_ad_revenue"
        )

        overall_roas = summary.get(
            "overall_roas"
        )

        overall_tacos = summary.get(
            "overall_tacos"
        )

        best_month = summary.get(
            "best_sales_month"
        )

        worst_month = summary.get(
            "worst_sales_month"
        )

        if first_month is not None:
            lines.append(
                f"Period: {first_month} to {last_month}"
            )

        if total_sales is not None:
            lines.append(
                f"Total Sales: "
                f"{format_currency(total_sales)}"
            )

        if total_units is not None:
            lines.append(
                f"Total Units: "
                f"{format_number(total_units)}"
            )

        if total_ad_spend is not None:
            lines.append(
                f"Total Ad Spend: "
                f"{format_currency(total_ad_spend)}"
            )

        if total_ad_revenue is not None:
            lines.append(
                f"Total Ad Revenue: "
                f"{format_currency(total_ad_revenue)}"
            )

        if overall_roas is not None:
            lines.append(
                f"Overall ROAS: "
                f"{format_ratio(overall_roas)}"
            )

        if overall_tacos is not None:
            lines.append(
                f"Overall TACOS: "
                f"{format_percentage(overall_tacos)}"
            )

        if best_month is not None:
            lines.append(
                f"Best Sales Month: {best_month}"
            )

        if worst_month is not None:
            lines.append(
                f"Worst Sales Month: {worst_month}"
            )

        lines.append("")

    # --------------------------------------------------------
    # MONTHLY TREND
    # --------------------------------------------------------

    lines.append(
        "Monthly Trend"
    )

    lines.append("")

    for index, month in enumerate(
        monthly,
        start=1
    ):

        if not isinstance(month, dict):
            continue

        month_name = month.get(
            "month",
            "UNKNOWN"
        )

        sales = format_currency(
            month.get("sales")
        )

        units = format_number(
            month.get("units")
        )

        ad_spend = format_currency(
            month.get("ad_spend")
        )

        ad_revenue = format_currency(
            month.get("ad_revenue")
        )

        roas = format_ratio(
            month.get("roas")
        )

        tacos = format_percentage(
            month.get("tacos")
        )

        sales_growth = format_percentage(
            month.get("sales_growth_pct")
        )

        lines.append(
            f"{index}. {month_name} | "
            f"Sales: {sales} | "
            f"Units: {units} | "
            f"Ad Spend: {ad_spend} | "
            f"Ad Revenue: {ad_revenue} | "
            f"ROAS: {roas} | "
            f"TACOS: {tacos} | "
            f"Sales Growth: {sales_growth}"
        )

    return "\n".join(lines)

# ============================================================
# DRIVER ANALYSIS FORMATTER
# ============================================================

def format_driver_analysis(
    result: dict
) -> str:
    """
    Deterministically format trusted driver-analysis results.

    Expected structure:

        result["data"] = {
            "month": ...,
            "previous_month": ...,
            "summary": {...},
            "sku_drivers": {...},
            "country_drivers": {...}
        }

    No business metrics are calculated here.
    Values come directly from the trusted driver-analysis tool.
    """

    if not isinstance(result, dict):
        raise ValueError(
            "Driver analysis result must be a dictionary."
        )

    data = result.get(
        "data",
        {}
    )

    if not isinstance(data, dict):
        raise ValueError(
            "Driver analysis data must be a dictionary."
        )

    summary = data.get(
        "summary",
        {}
    )

    if not isinstance(summary, dict):
        summary = {}

    current_month = data.get(
        "month",
        summary.get("current_month", "UNKNOWN")
    )

    previous_month = data.get(
        "previous_month",
        summary.get("previous_month", "UNKNOWN")
    )

    country_filter = data.get(
        "country"
    )

    lines = [
        "Sales Driver Analysis",
        ""
    ]

    lines.append(
        f"Comparison: "
        f"{previous_month} -> {current_month}"
    )

    if country_filter:
        lines.append(
            f"Country Filter: {country_filter}"
        )

    previous = summary.get(
        "previous",
        {}
    )

    current = summary.get(
        "current",
        {}
    )

    if not isinstance(previous, dict):
        previous = {}

    if not isinstance(current, dict):
        current = {}

    previous_sales = previous.get(
        "sales"
    )

    current_sales = current.get(
        "sales"
    )

    sales_change = summary.get(
        "sales_change"
    )

    sales_change_pct = summary.get(
        "sales_change_pct"
    )

    lines.append(
        f"Previous Sales: "
        f"{format_currency(previous_sales)}"
    )

    lines.append(
        f"Current Sales: "
        f"{format_currency(current_sales)}"
    )

    lines.append(
        f"Sales Change: "
        f"{format_currency(sales_change)}"
    )

    lines.append(
        f"Sales Change %: "
        f"{format_percentage(sales_change_pct)}"
    )

    lines.append("")
    lines.append("Top SKU Drivers")
    lines.append("")

    sku_section = data.get(
        "sku_drivers",
        {}
    )

    if not isinstance(sku_section, dict):
        sku_section = {}

    sku_drivers = sku_section.get(
        "drivers",
        []
    )

    if not sku_drivers:
        lines.append(
            "No SKU driver records were found."
        )
    else:

        for index, item in enumerate(
            sku_drivers[:10],
            start=1
        ):

            if not isinstance(item, dict):
                continue

            sku = item.get(
                "sku",
                "UNKNOWN"
            )

            sales_change_value = item.get(
                "sales_change"
            )

            sales_change_pct_value = item.get(
                "sales_change_pct"
            )

            contribution = item.get(
                "contribution_pct"
            )

            units_change = item.get(
                "units_change"
            )

            lines.append(
                f"{index}. {sku} | "
                f"Sales Change: "
                f"{format_currency(sales_change_value)} | "
                f"Change %: "
                f"{format_percentage(sales_change_pct_value)} | "
                f"Contribution: "
                f"{format_percentage(contribution)} | "
                f"Units Change: "
                f"{format_number(units_change)}"
            )

    country_section = data.get(
        "country_drivers"
    )

    if country_section is not None:

        lines.append("")
        lines.append("Top Country Drivers")
        lines.append("")

        if not isinstance(
            country_section,
            dict
        ):
            country_section = {}

        country_drivers = country_section.get(
            "drivers",
            []
        )

        if not country_drivers:
            lines.append(
                "No country driver records were found."
            )
        else:

            for index, item in enumerate(
                country_drivers[:10],
                start=1
            ):

                if not isinstance(item, dict):
                    continue

                country = item.get(
                    "country",
                    "UNKNOWN"
                )

                sales_change_value = item.get(
                    "sales_change"
                )

                sales_change_pct_value = item.get(
                    "sales_change_pct"
                )

                contribution = item.get(
                    "contribution_pct"
                )

                units_change = item.get(
                    "units_change"
                )

                lines.append(
                    f"{index}. {country} | "
                    f"Sales Change: "
                    f"{format_currency(sales_change_value)} | "
                    f"Change %: "
                    f"{format_percentage(sales_change_pct_value)} | "
                    f"Contribution: "
                    f"{format_percentage(contribution)} | "
                    f"Units Change: "
                    f"{format_number(units_change)}"
                )

    lines.append("")
    lines.append(
        "Note: Contribution percentages describe each "
        "segment's contribution to the observed total "
        "month-over-month sales change. They do not "
        "establish causation."
    )

    return "\n".join(lines)


# ============================================================
# AUTO FORMAT TOOL RESULT
# ============================================================

def format_tool_result(
    result: dict
) -> str:
    """
    Automatically select the correct deterministic formatter
    based on the tool name.
    """

    if not isinstance(result, dict):

        raise ValueError(
            "Tool result must be a dictionary."
        )

    tool_name = result.get(
        "tool"
    )

    # --------------------------------------------------------
    # PRODUCT RANKING
    # --------------------------------------------------------

    if tool_name == "product_ranking":

        return format_product_ranking(
            result,
            title="Product Ranking"
        )

    # --------------------------------------------------------
    # TOP PRODUCTS
    # --------------------------------------------------------

    if tool_name == "top_products":

        return format_product_ranking(
            result,
            title="Top Products"
        )

    # --------------------------------------------------------
    # EXECUTIVE
    # --------------------------------------------------------

    if tool_name == "executive_analysis":

        return format_executive_kpis(
            result
        )

    # --------------------------------------------------------
    # MONTHLY
    # --------------------------------------------------------

    if tool_name == "monthly_performance":

        return format_monthly_performance(
            result
        )

    # --------------------------------------------------------
    # COUNTRY
    # --------------------------------------------------------

    if tool_name == "country_performance":

        return format_country_performance(
            result
        )
    
    # --------------------------------------------------------
    # COMPARISON
    # --------------------------------------------------------

    if tool_name == "comparison_analysis":

        return format_comparison_analysis(
            result
        )
    
    # --------------------------------------------------------
    # TREND ANALYSIS
    # --------------------------------------------------------

    if tool_name == "trend_analysis":

        return format_trend_analysis(
            result
        )
    # --------------------------------------------------------
    # DRIVER ANALYSIS
    # --------------------------------------------------------

    if tool_name == "driver_analysis":

        return format_driver_analysis(
            result
        )

    # --------------------------------------------------------
    # INVENTORY
    # --------------------------------------------------------

    if tool_name in {
        "inventory_risks",
        "inventory_risks_for_skus",
    }:

        return format_inventory_risks(
            result
        )

    # --------------------------------------------------------
    # SALES FORECAST
    # --------------------------------------------------------

    if tool_name == "sales_forecast":

        return format_sales_forecast(
            result
        )

    # --------------------------------------------------------
    # ADVERTISING
    # --------------------------------------------------------

    if tool_name == "advertising_risks":

        return format_advertising_risks(
            result
        )

    # --------------------------------------------------------
    # QUALITY
    # --------------------------------------------------------

    if tool_name == "data_quality":

        return format_data_quality(
            result
        )

    # --------------------------------------------------------
    # UNKNOWN TOOL
    # --------------------------------------------------------

    raise ValueError(
        f"No formatter exists for tool: {tool_name}"
    )


# ============================================================
# FORMAT ALL EXECUTION RESULTS
# ============================================================

def format_execution_results(
    execution_result: dict
) -> str:
    """
    Format all tool results deterministically.
    """

    if not isinstance(
        execution_result,
        dict
    ):

        raise ValueError(
            "Execution result must be a dictionary."
        )

    results = execution_result.get(
        "results",
        []
    )

    if isinstance(results, list):

        iterable = results

    elif isinstance(results, dict):

        iterable = list(
            results.values()
        )

    else:

        iterable = []

    if not iterable:

        return (
            "No tool results were returned."
        )

    sections = []

    for index, result in enumerate(
        iterable,
        start=1
    ):

        formatted = format_tool_result(
            result
        )

        sections.append(
            f"RESULT {index}\n"
            f"{formatted}"
        )

    return "\n\n".join(
        sections
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    test_result = {
        "tool": "sales_forecast",
        "parameters": {
            "months_ahead": 3,
        },
        "data": {
            "model": "linear_trend",
            "months_ahead": 3,
            "historical_months": 8,
            "historical": [
                {
                    "month": "2026-01-01",
                    "sales": 5980888.36,
                },
                {
                    "month": "2026-02-01",
                    "sales": 5796365.65,
                },
                {
                    "month": "2026-03-01",
                    "sales": 6790037.58,
                },
                {
                    "month": "2026-04-01",
                    "sales": 7353766.30,
                },
                {
                    "month": "2026-05-01",
                    "sales": 6586140.60,
                },
                {
                    "month": "2026-06-01",
                    "sales": 7476217.89,
                },
                {
                    "month": "2026-07-01",
                    "sales": 7552049.66,
                },
                {
                    "month": "2026-08-01",
                    "sales": 8304432.14,
                },
            ],
            "forecast": [
                {
                    "month": "2026-09-01",
                    "forecast_sales": 8390744.87,
                },
                {
                    "month": "2026-10-01",
                    "forecast_sales": 8704246.55,
                },
                {
                    "month": "2026-11-01",
                    "forecast_sales": 9017748.24,
                },
            ],
            "trend_slope": 313501.68,
            "first_month": "2026-01-01",
            "last_historical_month": "2026-08-01",
        },
    }

    print()
    print("=" * 70)
    print("RESULT FORMATTER TEST")
    print("=" * 70)

    print()

    print(
        format_tool_result(
            test_result
        )
    )

    print()
    print("=" * 70)
    print("FORMATTER TEST COMPLETED")
    print("=" * 70)
