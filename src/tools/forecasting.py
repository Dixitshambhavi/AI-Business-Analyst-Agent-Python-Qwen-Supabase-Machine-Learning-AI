from pathlib import Path
import sys

import pandas as pd
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
# SUPPORTED COUNTRIES
# ============================================================

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
    Execute a trusted parameterized SQL query.
    """

    with engine.connect() as connection:

        result = connection.execute(
            query,
            params or {}
        )

        return result.fetchall()


# ============================================================
# NORMALIZE COUNTRY
# ============================================================

def normalize_country(country):
    """
    Convert common country names/codes to database country codes.

    Examples:
        India -> IN
        USA -> US
        Germany -> DE
        United Kingdom -> UK
        Canada -> CA
        UAE -> AE
    """

    if country is None:
        return None

    value = str(
        country
    ).strip().upper()

    aliases = {
        "INDIA": "IN",
        "IN": "IN",

        "USA": "US",
        "US": "US",
        "U.S.": "US",
        "U.S.A.": "US",
        "AMERICA": "US",

        "GERMANY": "DE",
        "DE": "DE",

        "UK": "UK",
        "U.K.": "UK",
        "UNITED KINGDOM": "UK",
        "BRITAIN": "UK",

        "CANADA": "CA",
        "CA": "CA",

        "UAE": "AE",
        "AE": "AE",
        "UNITED ARAB EMIRATES": "AE",
    }

    normalized = aliases.get(value)

    if normalized not in ALLOWED_COUNTRIES:
        return None

    return normalized


# ============================================================
# NORMALIZE YEAR
# ============================================================

def normalize_year(year):
    """
    Validate optional year.
    """

    if year is None:
        return None

    try:
        year = int(year)
    except (TypeError, ValueError):
        return None

    if 2000 <= year <= 2100:
        return year

    return None


# ============================================================
# METRICS
# ============================================================

def calculate_mae(actual, predicted):
    """
    Mean Absolute Error.
    """

    actual = pd.Series(
        actual,
        dtype=float
    )

    predicted = pd.Series(
        predicted,
        dtype=float
    )

    return float(
        (actual - predicted)
        .abs()
        .mean()
    )


def calculate_rmse(actual, predicted):
    """
    Root Mean Squared Error.
    """

    actual = pd.Series(
        actual,
        dtype=float
    )

    predicted = pd.Series(
        predicted,
        dtype=float
    )

    mse = (
        (actual - predicted) ** 2
    ).mean()

    return float(
        mse ** 0.5
    )


def calculate_mape(actual, predicted):
    """
    Mean Absolute Percentage Error.

    Zero actual values are excluded.
    """

    actual = pd.Series(
        actual,
        dtype=float
    )

    predicted = pd.Series(
        predicted,
        dtype=float
    )

    mask = actual != 0

    if mask.sum() == 0:
        return None

    mape = (
        (
            (
                actual[mask]
                - predicted[mask]
            ).abs()
            / actual[mask].abs()
        ).mean()
        * 100
    )

    return float(mape)


# ============================================================
# MODEL 1 — LAST VALUE
# ============================================================

def forecast_last_value(
    train_values,
    horizon
):
    """
    Use the latest actual value for all future periods.
    """

    values = pd.Series(
        train_values,
        dtype=float
    )

    if len(values) == 0:
        return [0.0] * horizon

    last_value = float(
        values.iloc[-1]
    )

    return [
        max(0.0, last_value)
        for _ in range(horizon)
    ]


# ============================================================
# MODEL 2 — MOVING AVERAGE
# ============================================================

def forecast_moving_average(
    train_values,
    horizon,
    window=3
):
    """
    Recursive moving-average forecast.
    """

    values = pd.Series(
        train_values,
        dtype=float
    ).tolist()

    if len(values) == 0:
        return [0.0] * horizon

    forecasts = []

    for _ in range(horizon):

        recent = values[-window:]

        prediction = float(
            sum(recent)
            / len(recent)
        )

        prediction = max(
            0.0,
            prediction
        )

        forecasts.append(
            prediction
        )

        values.append(
            prediction
        )

    return forecasts


# ============================================================
# MODEL 3 — LINEAR TREND
# ============================================================

def fit_linear_trend(
    train_values
):
    """
    Fit:

        sales = intercept + slope * time
    """

    values = pd.Series(
        train_values,
        dtype=float
    ).reset_index(drop=True)

    if len(values) < 2:

        return (
            0.0,
            float(
                values.iloc[-1]
                if len(values) > 0
                else 0.0
            )
        )

    x = pd.Series(
        range(len(values)),
        dtype=float
    )

    y = values.astype(
        float
    )

    denominator = (
        (x - x.mean()) ** 2
    ).sum()

    if denominator == 0:

        return (
            0.0,
            float(
                y.mean()
            )
        )

    slope = float(
        (
            (x - x.mean())
            * (y - y.mean())
        ).sum()
        / denominator
    )

    intercept = float(
        y.mean()
        - slope * x.mean()
    )

    return (
        slope,
        intercept
    )


def forecast_linear_trend(
    train_values,
    horizon
):
    """
    Generate future values from linear trend.
    """

    values = pd.Series(
        train_values,
        dtype=float
    ).reset_index(drop=True)

    if len(values) == 0:
        return [0.0] * horizon

    slope, intercept = (
        fit_linear_trend(
            values
        )
    )

    forecasts = []

    start_index = len(values)

    for step in range(
        horizon
    ):

        future_index = (
            start_index
            + step
        )

        prediction = (
            intercept
            + slope * future_index
        )

        prediction = max(
            0.0,
            float(prediction)
        )

        forecasts.append(
            prediction
        )

    return forecasts


# ============================================================
# MODEL 4 — EXPONENTIAL SMOOTHING
# ============================================================

def forecast_exponential_smoothing(
    train_values,
    horizon,
    alpha=0.4
):
    """
    Simple exponential smoothing.
    """

    values = pd.Series(
        train_values,
        dtype=float
    ).tolist()

    if len(values) == 0:
        return [0.0] * horizon

    alpha = max(
        0.01,
        min(float(alpha), 0.99)
    )

    level = float(
        values[0]
    )

    for actual in values[1:]:

        level = (
            alpha * float(actual)
            + (
                1 - alpha
            ) * level
        )

    level = max(
        0.0,
        float(level)
    )

    return [
        level
        for _ in range(horizon)
    ]


# ============================================================
# GENERIC MODEL FORECASTER
# ============================================================

def generate_model_forecast(
    model_name,
    train_values,
    horizon
):
    """
    Dispatch to the requested model.
    """

    if model_name == "last_value":

        return forecast_last_value(
            train_values,
            horizon
        )

    if model_name == "moving_average_3":

        return forecast_moving_average(
            train_values,
            horizon,
            window=3
        )

    if model_name == "linear_trend":

        return forecast_linear_trend(
            train_values,
            horizon
        )

    if model_name == "exponential_smoothing":

        return forecast_exponential_smoothing(
            train_values,
            horizon,
            alpha=0.4
        )

    raise ValueError(
        f"Unknown forecasting model: {model_name}"
    )


# ============================================================
# MODEL EVALUATION
# ============================================================

def evaluate_models(df):
    """
    Backtest candidate forecasting models.

    The most recent 3 months are used for validation when
    enough historical months are available.
    """

    total_months = len(
        df
    )

    if total_months >= 7:

        validation_months = 3

    elif total_months >= 5:

        validation_months = 2

    else:

        validation_months = 1

    train_months = (
        total_months
        - validation_months
    )

    if train_months < 2:

        return {
            "validation_months": validation_months,
            "evaluated": False,
            "selected_model": "linear_trend",
            "selection_metric": "MAE",
            "metrics": [],
            "message": (
                "Not enough historical months for "
                "reliable model evaluation."
            ),
        }

    train_df = df.iloc[
        :train_months
    ].copy()

    validation_df = df.iloc[
        train_months:
    ].copy()

    train_values = (
        train_df["sales"]
        .astype(float)
        .tolist()
    )

    actual_values = (
        validation_df["sales"]
        .astype(float)
        .tolist()
    )

    horizon = len(
        actual_values
    )

    candidate_models = [
        "last_value",
        "moving_average_3",
        "linear_trend",
        "exponential_smoothing",
    ]

    results = []

    for model_name in candidate_models:

        predicted_values = (
            generate_model_forecast(
                model_name,
                train_values,
                horizon
            )
        )

        mae = calculate_mae(
            actual_values,
            predicted_values
        )

        rmse = calculate_rmse(
            actual_values,
            predicted_values
        )

        mape = calculate_mape(
            actual_values,
            predicted_values
        )

        results.append({
            "model": model_name,
            "mae": round(
                mae,
                2
            ),
            "rmse": round(
                rmse,
                2
            ),
            "mape_pct": (
                round(
                    mape,
                    2
                )
                if mape is not None
                else None
            ),
        })

    # --------------------------------------------------------
    # AUTOMATIC MODEL SELECTION
    # --------------------------------------------------------
    # Primary: MAE
    # Tie-breakers: MAPE, RMSE

    sorted_results = sorted(
        results,
        key=lambda item: (
            item["mae"],
            item["mape_pct"]
            if item["mape_pct"] is not None
            else float("inf"),
            item["rmse"],
        )
    )

    selected_model = (
        sorted_results[0]["model"]
    )

    return {
        "validation_months": validation_months,
        "train_months": train_months,
        "evaluated": True,
        "selected_model": selected_model,
        "selection_metric": "MAE",
        "metrics": sorted_results,

        "training_start": (
            train_df["month"]
            .iloc[0]
            .strftime("%Y-%m-%d")
        ),

        "training_end": (
            train_df["month"]
            .iloc[-1]
            .strftime("%Y-%m-%d")
        ),

        "validation_start": (
            validation_df["month"]
            .iloc[0]
            .strftime("%Y-%m-%d")
        ),

        "validation_end": (
            validation_df["month"]
            .iloc[-1]
            .strftime("%Y-%m-%d")
        ),
    }


# ============================================================
# BUSINESS EXPLANATION
# ============================================================

def build_business_explanation(
    historical_df,
    forecast_rows,
    evaluation
):
    """
    Build deterministic business-facing facts.

    No additional business metrics are invented.
    """

    if historical_df.empty:

        return {
            "summary": (
                "No historical sales data is available "
                "for the forecast."
            ),
            "forecast_direction": "unknown",
            "latest_actual_sales": None,
            "first_forecast_sales": None,
            "average_forecast_sales": None,
            "forecast_change_pct": None,
        }

    latest_actual = float(
        historical_df["sales"].iloc[-1]
    )

    first_forecast = None

    if forecast_rows:

        first_forecast = float(
            forecast_rows[0][
                "forecast_sales"
            ]
        )

    average_forecast = None

    if forecast_rows:

        average_forecast = (
            sum(
                float(
                    row["forecast_sales"]
                )
                for row in forecast_rows
            )
            / len(forecast_rows)
        )

    if (
        first_forecast is None
        or latest_actual == 0
    ):

        forecast_direction = "unknown"
        forecast_change_pct = None

    else:

        forecast_change_pct = (
            (
                first_forecast
                - latest_actual
            )
            / abs(latest_actual)
        ) * 100

        if forecast_change_pct > 1:

            forecast_direction = "increasing"

        elif forecast_change_pct < -1:

            forecast_direction = "decreasing"

        else:

            forecast_direction = "stable"

    selected_model = evaluation.get(
        "selected_model",
        "linear_trend"
    )

    validation_months = evaluation.get(
        "validation_months"
    )

    summary = (
        f"Forecast sales are expected to be "
        f"{forecast_direction} relative to the latest "
        f"historical month. The selected forecasting "
        f"model is {selected_model}."
    )

    if validation_months:

        summary += (
            f" Model selection was based on backtesting "
            f"over the most recent {validation_months} "
            f"historical month(s)."
        )

    return {
        "summary": summary,

        "forecast_direction": (
            forecast_direction
        ),

        "latest_actual_sales": round(
            latest_actual,
            2
        ),

        "first_forecast_sales": (
            round(
                first_forecast,
                2
            )
            if first_forecast is not None
            else None
        ),

        "average_forecast_sales": (
            round(
                average_forecast,
                2
            )
            if average_forecast is not None
            else None
        ),

        "forecast_change_pct": (
            round(
                forecast_change_pct,
                2
            )
            if forecast_change_pct is not None
            else None
        ),
    }


# ============================================================
# SALES FORECAST
# ============================================================

def forecast_sales(
    months_ahead=3,
    country=None,
    year=None,
):
    """
    Forecast monthly gross sales.

    Parameters
    ----------
    months_ahead : int
        Future forecast horizon, from 1 to 12.

    country : str | None
        Optional country name/code.

    year : int | None
        Optional historical year filter.

    Examples
    --------
    forecast_sales(
        months_ahead=3,
        country="IN"
    )

    forecast_sales(
        months_ahead=6,
        country="US"
    )

    forecast_sales(
        months_ahead=3,
        country="India",
        year=2026
    )
    """

    # ========================================================
    # NORMALIZE PARAMETERS
    # ========================================================

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

    country = normalize_country(
        country
    )

    year = normalize_year(
        year
    )

    # ========================================================
    # BUILD FILTERED SQL
    # ========================================================

    where_clauses = []

    params = {}

    if country:

        where_clauses.append(
            "country = :country"
        )

        params["country"] = country

    if year is not None:

        where_clauses.append(
            "EXTRACT(YEAR FROM year_month) = :year"
        )

        params["year"] = year

    where_sql = ""

    if where_clauses:

        where_sql = (
            "WHERE "
            + " AND ".join(
                where_clauses
            )
        )

    query = text(
        f"""
        SELECT
            year_month,
            SUM(gross_sales) AS sales
        FROM {TABLE_NAME}
        {where_sql}
        GROUP BY year_month
        ORDER BY year_month;
        """
    )

    rows = fetch_all(
        query,
        params
    )

    # ========================================================
    # NO DATA
    # ========================================================

    if not rows:

        scope = []

        if country:

            scope.append(
                f"Country={country}"
            )

        if year is not None:

            scope.append(
                f"Year={year}"
            )

        scope_text = (
            ", ".join(scope)
            if scope
            else "all available data"
        )

        return {
            "model": None,
            "months_ahead": months_ahead,

            "country": country,
            "year": year,

            "historical_months": 0,

            "historical": [],
            "forecast": [],

            "evaluation": {
                "evaluated": False,
                "metrics": [],
                "selected_model": None,
            },

            "business_explanation": {
                "summary": (
                    f"No historical sales data was found "
                    f"for {scope_text}."
                ),
                "forecast_direction": "unknown",
                "latest_actual_sales": None,
                "first_forecast_sales": None,
                "average_forecast_sales": None,
                "forecast_change_pct": None,
            },

            "message": (
                f"No historical sales data was found "
                f"for {scope_text}."
            ),
        }

    # ========================================================
    # HISTORICAL DATA
    # ========================================================

    historical = []

    for row in rows:

        historical.append({
            "month": str(
                row.year_month
            ),

            "sales": float(
                row.sales or 0
            ),
        })

    # ========================================================
    # DATAFRAME
    # ========================================================

    df = pd.DataFrame(
        historical
    )

    df["month"] = pd.to_datetime(
        df["month"],
        errors="coerce"
    )

    df["sales"] = pd.to_numeric(
        df["sales"],
        errors="coerce"
    ).fillna(0)

    df = (
        df
        .dropna(
            subset=["month"]
        )
        .sort_values("month")
        .reset_index(drop=True)
    )

    # ========================================================
    # MINIMUM DATA CHECK
    # ========================================================

    if len(df) < 2:

        return {
            "model": "linear_trend",

            "months_ahead": months_ahead,

            "country": country,
            "year": year,

            "historical_months": len(df),

            "historical": [
                {
                    "month": (
                        row["month"]
                        .strftime("%Y-%m-%d")
                    ),
                    "sales": round(
                        float(row["sales"]),
                        2
                    ),
                }
                for _, row in df.iterrows()
            ],

            "forecast": [],

            "evaluation": {
                "evaluated": False,
                "metrics": [],
                "selected_model": "linear_trend",
            },

            "message": (
                "At least two historical months "
                "are required."
            ),

            "business_explanation": {
                "summary": (
                    "At least two historical months "
                    "are required before generating "
                    "a sales forecast."
                ),
                "forecast_direction": "unknown",
            },
        }

    # ========================================================
    # PHASE 3.2 — MODEL EVALUATION
    # ========================================================

    evaluation = evaluate_models(
        df
    )

    selected_model = evaluation.get(
        "selected_model",
        "linear_trend"
    )

    # ========================================================
    # TRAIN SELECTED MODEL ON FULL FILTERED HISTORY
    # ========================================================

    full_values = (
        df["sales"]
        .astype(float)
        .tolist()
    )

    predicted_values = (
        generate_model_forecast(
            selected_model,
            full_values,
            months_ahead
        )
    )

    # ========================================================
    # FUTURE MONTHS
    # ========================================================

    last_month = (
        df["month"].iloc[-1]
    )

    forecast_rows = []

    for step in range(
        1,
        months_ahead + 1
    ):

        future_month = (
            last_month
            + pd.DateOffset(
                months=step
            )
        )

        predicted_sales = max(
            0.0,
            float(
                predicted_values[
                    step - 1
                ]
            )
        )

        forecast_rows.append({
            "month": (
                future_month
                .strftime("%Y-%m-%d")
            ),

            "forecast_sales": round(
                predicted_sales,
                2
            ),
        })

    # ========================================================
    # TREND INFORMATION
    # ========================================================

    slope, intercept = (
        fit_linear_trend(
            full_values
        )
    )

    # ========================================================
    # PHASE 3.3 — BUSINESS EXPLANATION
    # ========================================================

    business_explanation = (
        build_business_explanation(
            historical_df=df,
            forecast_rows=forecast_rows,
            evaluation=evaluation,
        )
    )

    # ========================================================
    # SELECTED MODEL METRICS
    # ========================================================

    selected_metrics = None

    for metric in evaluation.get(
        "metrics",
        []
    ):

        if (
            metric.get("model")
            == selected_model
        ):

            selected_metrics = metric

            break

    # ========================================================
    # RETURN
    # ========================================================

    return {

        # ----------------------------------------------------
        # Scope
        # ----------------------------------------------------

        "country": country,

        "year": year,

        # ----------------------------------------------------
        # Forecast
        # ----------------------------------------------------

        "model": selected_model,

        "months_ahead": months_ahead,

        "historical_months": len(
            df
        ),

        "historical": [
            {
                "month": (
                    row["month"]
                    .strftime("%Y-%m-%d")
                ),

                "sales": round(
                    float(row["sales"]),
                    2
                ),
            }
            for _, row in df.iterrows()
        ],

        "forecast": forecast_rows,

        # ----------------------------------------------------
        # Trend metadata
        # ----------------------------------------------------

        "trend_slope": round(
            slope,
            2
        ),

        "trend_intercept": round(
            intercept,
            2
        ),

        "first_month": (
            df["month"]
            .iloc[0]
            .strftime("%Y-%m-%d")
        ),

        "last_historical_month": (
            last_month
            .strftime("%Y-%m-%d")
        ),

        # ----------------------------------------------------
        # Phase 3.2
        # ----------------------------------------------------

        "evaluation": evaluation,

        "selected_model_metrics": (
            selected_metrics
        ),

        # ----------------------------------------------------
        # Phase 3.3
        # ----------------------------------------------------

        "business_explanation": (
            business_explanation
        ),

        "forecast_direction": (
            business_explanation[
                "forecast_direction"
            ]
        ),

        "latest_actual_sales": (
            business_explanation[
                "latest_actual_sales"
            ]
        ),

        "first_forecast_sales": (
            business_explanation[
                "first_forecast_sales"
            ]
        ),

        "average_forecast_sales": (
            business_explanation[
                "average_forecast_sales"
            ]
        ),

        "forecast_change_pct": (
            business_explanation[
                "forecast_change_pct"
            ]
        ),
    }


# ============================================================
# TEST
# ============================================================

def main():

    print()
    print("=" * 90)
    print(
        "AI BUSINESS ANALYST - SALES FORECAST"
    )
    print("=" * 90)

    # ========================================================
    # TEST WITH INDIA
    # ========================================================

    result = forecast_sales(
        months_ahead=3,
        country="IN",
        year=2026,
    )

    print()
    print("FORECAST SCOPE")
    print("-" * 90)

    print(
        f"Country: "
        f"{result.get('country') or 'ALL'}"
    )

    print(
        f"Year: "
        f"{result.get('year') or 'ALL'}"
    )

    # ========================================================
    # SELECTED MODEL
    # ========================================================

    print()
    print("SELECTED MODEL")
    print("-" * 90)

    print(
        result.get(
            "model"
        )
    )

    # ========================================================
    # HISTORICAL
    # ========================================================

    print()
    print("HISTORICAL SALES")
    print("-" * 90)

    for row in result.get(
        "historical",
        []
    ):

        print(
            f"{row['month']} | "
            f"Sales=${row['sales']:,.2f}"
        )

    # ========================================================
    # MODEL EVALUATION
    # ========================================================

    evaluation = result.get(
        "evaluation",
        {}
    )

    print()
    print("MODEL EVALUATION")
    print("-" * 90)

    print(
        f"Evaluated: "
        f"{evaluation.get('evaluated')}"
    )

    print(
        f"Selection Metric: "
        f"{evaluation.get('selection_metric', 'N/A')}"
    )

    print(
        f"Validation Months: "
        f"{evaluation.get('validation_months', 'N/A')}"
    )

    for metric in evaluation.get(
        "metrics",
        []
    ):

        print(
            f"{metric['model']:<25}"
            f"MAE=${metric['mae']:,.2f} | "
            f"RMSE=${metric['rmse']:,.2f} | "
            f"MAPE="
            f"{metric['mape_pct']}"
            f"%"
            if metric["mape_pct"] is not None
            else
            f"{metric['model']:<25}"
            f"MAE=${metric['mae']:,.2f} | "
            f"RMSE=${metric['rmse']:,.2f} | "
            f"MAPE=N/A"
        )

    # ========================================================
    # FORECAST
    # ========================================================

    print()
    print("FORECAST")
    print("-" * 90)

    for row in result.get(
        "forecast",
        []
    ):

        print(
            f"{row['month']} | "
            f"Forecast Sales="
            f"${row['forecast_sales']:,.2f}"
        )

    # ========================================================
    # BUSINESS EXPLANATION
    # ========================================================

    explanation = result.get(
        "business_explanation",
        {}
    )

    print()
    print("BUSINESS EXPLANATION")
    print("-" * 90)

    print(
        explanation.get(
            "summary",
            "N/A"
        )
    )

    print(
        "Forecast Direction:",
        explanation.get(
            "forecast_direction",
            "N/A"
        )
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

    print(
        "Latest Actual Sales:",
        (
            f"${latest_actual:,.2f}"
            if latest_actual is not None
            else "N/A"
        )
    )

    print(
        "First Forecast Sales:",
        (
            f"${first_forecast:,.2f}"
            if first_forecast is not None
            else "N/A"
        )
    )

    print(
        "Average Forecast Sales:",
        (
            f"${average_forecast:,.2f}"
            if average_forecast is not None
            else "N/A"
        )
    )

    print(
        "First Forecast vs Latest Actual:",
        (
            f"{change_pct:+.2f}%"
            if change_pct is not None
            else "N/A"
        )
    )

    print()
    print("=" * 90)


if __name__ == "__main__":
    main()