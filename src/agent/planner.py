"""
Planner for the AI Business Analyst Agent.

Responsibilities
----------------
1. Extract deterministic parameters from the user's question.
2. Route questions to trusted business capabilities.
3. Enforce parameter rules before execution.
4. Use the local LLM only as a fallback for questions that are not
   confidently routable by deterministic rules.
5. Add dependencies such as PRODUCT_RANKING -> INVENTORY_RISKS_FOR_SKUS.
6. Support country-vs-country comparison through COMPARISON_ANALYSIS.

The planner does NOT calculate business metrics itself.
Those calculations remain inside trusted business_intelligence.py tools.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from src.agent.capabilities import CAPABILITIES
from src.agent.parameter_extractor import extract_parameters


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

ALLOWED_COUNTRY_CODES = {"IN", "US", "DE", "UK", "CA", "AE"}
ALLOWED_CAPABILITIES = set(CAPABILITIES.keys()) | {"DYNAMIC_SQL"}

# Deterministic routing priorities.
# More specific capabilities are checked before broader ones.
ROUTING_RULES = [
    (
        "COMPARISON_ANALYSIS",
        [
            "compare",
            "comparison",
            "versus",
            "vs",
            "vs.",
            "difference between",
            "which is better",
        ],
    ),

    (
        "TREND_ANALYSIS",
        [
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
        ],
    ),
    (
        "SALES_FORECAST",
        [
            "forecast",
            "forecast sales",
            "sales forecast",
            "sales forecasting",
            "predict sales",
            "predicted sales",
            "future sales",
            "future revenue",
            "next month sales",
            "next 3 months",
            "next 6 months",
            "next 12 months",
        ],
    ),
    (
        "DATA_QUALITY",
        [
            "data quality",
            "quality check",
            "quality status",
            "data issue",
            "data issues",
            "anomal",
            "missing data",
            "duplicate data",
            "duplicates",
        ],
    ),
    (
        "INVENTORY_RISKS",
        [
            "inventory risk",
            "inventory risks",
            "stock risk",
            "stock risks",
            "low inventory",
            "low stock",
            "out of stock",
            "fba risk",
            "inventory",
            "stock",
        ],
    ),
    (
        "ADVERTISING_RISKS",
        [
            "advertising risk",
            "advertising risks",
            "ad risk",
            "ad risks",
            "ads risk",
            "acos risk",
            "tacos risk",
            "high acos",
            "high tacos",
            "poor roas",
            "bad roas",
            "ad efficiency",
            "advertising efficiency",
        ],
    ),
    (
        "MONTHLY_PERFORMANCE",
        [
            "monthly performance",
            "monthly sales",
            "monthly roas",
            "monthly tacos",
            "monthly acos",
            "by month",
            "per month",
            "month wise",
            "month-wise",
            "monthly",
        ],
    ),
    (
        "COUNTRY_PERFORMANCE",
        [
            "country performance",
            "by country",
            "country wise",
            "country-wise",
            "per country",
            "countries",
            "which country",
            "country sales",
            "country roas",
            "country tacos",
            "country acos",
        ],
    ),
    (
        "PRODUCT_RANKING",
        [
            "top sku",
            "top skus",
            "top product",
            "top products",
            "best sku",
            "best skus",
            "best product",
            "best products",
            "highest sales sku",
            "highest selling sku",
            "highest selling products",
            "rank sku",
            "rank skus",
            "rank products",
            "product ranking",
            "sku ranking",
            "product performance",
            "sku performance",
        ],
    ),
    (
        "EXECUTIVE_KPI",
        [
            "executive kpi",
            "executive kpis",
            "overall kpi",
            "overall kpis",
            "business kpi",
            "business kpis",
            "overall business",
            "business overview",
            "business summary",
            "overall performance",
            "overall sales",
            "total sales",
            "total revenue",
            "total spend",
            "total ad spend",
            "roas",
            "tacos",
            "how is the business",
            "how are we doing",
        ],
    ),
]


# ---------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------

def _normalize_text(text: str) -> str:
    """Normalize whitespace, casing, and common business-query typos."""

    normalized = re.sub(
        r"\s+",
        " ",
        (text or "").strip().lower()
    )

    # Common typo handling
    typo_replacements = {
        "trands": "trends",
        "trand": "trend",
        "groth": "growth",
        "perfomance": "performance",
        "anlysis": "analysis",
    }

    for typo, correction in typo_replacements.items():
        normalized = re.sub(
            rf"\b{re.escape(typo)}\b",
            correction,
            normalized,
        )

    return normalized


def _contains_phrase(text: str, phrase: str) -> bool:
    """
    Phrase-aware matching.

    Using word boundaries for short tokens avoids matching e.g. "us"
    inside unrelated words.
    """
    phrase = phrase.strip().lower()

    if not phrase:
        return False

    if " " in phrase or phrase in {"vs", "vs."}:
        return phrase in text

    return re.search(rf"\b{re.escape(phrase)}\b", text) is not None


def _has_any(text: str, phrases: List[str]) -> bool:
    return any(_contains_phrase(text, p) for p in phrases)


def _extract_forecast_horizon(question: str) -> int:
    """Extract the requested forecast horizon, defaulting to 3 months."""
    text = _normalize_text(question)

    match = re.search(r"\b(?:next|for)\s+(\d{1,2})\s+months?\b", text)
    if match:
        return max(1, min(int(match.group(1)), 12))

    number_words = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
    }

    match = re.search(
        r"\b(?:next|for)\s+(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+months?\b",
        text,
    )
    if match:
        return number_words[match.group(1)]

    if _contains_phrase(text, "next month"):
        return 1

    return 3


def _is_sales_change_question(question: str) -> bool:
    text = _normalize_text(question)
    patterns = [
        r"\bwhy did sales (?:change|increase|decrease|decline|drop|grow|rise)\b",
        r"\bwhy (?:did|has|have) sales changed\b",
        r"\bsales (?:change|changed|increase|decrease|decline|drop|growth) in\b",
        r"\bchange in sales\b",
        r"\bsales performance in .*\bwhy\b",
    ]
    return any(re.search(p, text) for p in patterns)


def _is_sales_forecast_question(question: str) -> bool:
    """
    Detect explicit requests for future sales forecasting.

    Forecast questions get priority over broader trend/monthly routing so
    that phrases such as "forecast sales trend" still use SALES_FORECAST.
    """
    text = _normalize_text(question)

    forecast_terms = [
        "forecast",
        "forecast sales",
        "sales forecast",
        "sales forecasting",
        "predict sales",
        "predicted sales",
        "future sales",
        "future revenue",
        "next month sales",
    ]

    sales_terms = [
        "sales",
        "revenue",
    ]

    return (
        _has_any(text, forecast_terms)
        and _has_any(text, sales_terms)
    )


def _is_product_ranking_question(question: str) -> bool:
    """
    Detect explicit product/SKU ranking questions deterministically.

    Supports both plain ranking phrases and numbered requests such as:
        - What are the top 5 SKUs by sales?
        - Show the top 10 products in India for 2026.
        - Which are the best selling SKUs?
        - Rank the products by sales.

    This function only identifies the capability. The numeric limit and
    optional filters continue to be extracted/validated by the existing
    parameter pipeline.
    """
    text = _normalize_text(question)

    # Important: phrases such as "top 5 skus" do not contain the exact
    # phrase "top skus", so explicitly support a number between top and
    # the entity being ranked.
    numbered_ranking = re.search(
        r"\btop\s+\d{1,3}\s+(?:skus?|products?)\b",
        text,
    )

    numbered_best_selling = re.search(
        r"\b(?:best|highest)\s+selling\s+(?:skus?|products?)\b",
        text,
    )

    ranking_terms = [
        "top sku",
        "top skus",
        "top product",
        "top products",
        "best sku",
        "best skus",
        "best product",
        "best products",
        "best selling sku",
        "best selling skus",
        "best selling product",
        "best selling products",
        "highest sales sku",
        "highest sales skus",
        "highest selling sku",
        "highest selling skus",
        "highest selling product",
        "highest selling products",
        "rank sku",
        "rank skus",
        "rank product",
        "rank products",
        "product ranking",
        "sku ranking",
    ]

    return bool(numbered_ranking or numbered_best_selling or _has_any(text, ranking_terms))


def _is_monthly_metrics_question(question: str) -> bool:
    """
    Detect questions that explicitly request month-by-month business metrics.

    These questions must take priority over ADVERTISING_RISKS when the
    question also contains phrases such as "ad efficiency" or
    "advertising efficiency".
    """
    text = _normalize_text(question)

    monthly_terms = [
        "monthly",
        "by month",
        "per month",
        "month wise",
        "month-wise",
        "month over month",
        "month-over-month",
    ]

    metric_terms = [
        "sales",
        "ad spend",
        "ad revenue",
        "roas",
        "tacos",
        "acos",
        "organic sales",
        "organic revenue",
    ]

    return (
        _has_any(text, monthly_terms)
        and _has_any(text, metric_terms)
    )


# ---------------------------------------------------------------------
# Deterministic routing
# ---------------------------------------------------------------------

def detect_capability(question: str) -> Optional[str]:
    """
    Determine the best deterministic capability for the question.

    Returns None when no capability has enough evidence.
    """
    text = _normalize_text(question)

    # ---------------------------------------------------------------
    # Sales forecasting gets highest deterministic priority.
    # This prevents forecast questions from being classified as a
    # broader trend or monthly-performance question.
    # ---------------------------------------------------------------
    if _is_sales_change_question(text):
        return "TREND_ANALYSIS"

    if _is_sales_forecast_question(text):
        return "SALES_FORECAST"

    # ---------------------------------------------------------------
    # Product/SKU ranking gets explicit deterministic priority.
    # This prevents simple ranking questions from reaching the LLM.
    # ---------------------------------------------------------------
    if _is_product_ranking_question(text):
        return "PRODUCT_RANKING"

    # ---------------------------------------------------------------
    # Monthly metrics questions get explicit priority.
    # This prevents phrases like "best advertising efficiency" from
    # incorrectly routing the question to ADVERTISING_RISKS.
    # ---------------------------------------------------------------
    if _is_monthly_metrics_question(text):
        return "MONTHLY_PERFORMANCE"

    for capability, keywords in ROUTING_RULES:
        if _has_any(text, keywords):
            return capability

    return None


# ---------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------

def _normalize_country(value: Any) -> Optional[str]:
    """Normalize country values to the country codes used by the DB."""
    if value is None:
        return None

    value = str(value).strip().upper()

    aliases = {
        "INDIA": "IN",
        "IN": "IN",
        "USA": "US",
        "US": "US",
        "U.S.A": "US",
        "U.S.": "US",
        "AMERICA": "US",
        "GERMANY": "DE",
        "DE": "DE",
        "UK": "UK",
        "U.K.": "UK",
        "BRITAIN": "UK",
        "CANADA": "CA",
        "CA": "CA",
        "UAE": "AE",
        "AE": "AE",
        "UNITED ARAB EMIRATES": "AE",
    }

    return aliases.get(value, value if value in ALLOWED_COUNTRY_CODES else None)


def _normalize_year(value: Any) -> Optional[int]:
    if value in (None, "", "none"):
        return None

    try:
        year = int(value)
    except (TypeError, ValueError):
        return None

    if 2000 <= year <= 2100:
        return year

    return None


def _normalize_month(value: Any) -> Optional[int]:
    if value in (None, "", "none"):
        return None

    # Accept:
    #   1..12
    #   "01".."12"
    #   "2026-01" -> January
    #   month names / abbreviations
    text = str(value).strip().lower()

    month_aliases = {
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

    if text in month_aliases:
        return month_aliases[text]

    if re.fullmatch(r"\d{4}-\d{1,2}", text):
        try:
            month = int(text.split("-")[1])
        except ValueError:
            return None

        return month if 1 <= month <= 12 else None

    try:
        month = int(text)
    except ValueError:
        return None

    return month if 1 <= month <= 12 else None


def validate_extracted_parameters(params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clean and validate parameters extracted from the question.

    Unknown/invalid optional values are converted to None rather than
    being passed into SQL tools.
    """
    cleaned = dict(params or {})

    country = _normalize_country(cleaned.get("country"))
    country1 = _normalize_country(cleaned.get("country1"))
    country2 = _normalize_country(cleaned.get("country2"))

    year = _normalize_year(cleaned.get("year"))
    month = _normalize_month(cleaned.get("month"))

    limit = cleaned.get("limit")
    if limit not in (None, ""):
        try:
            limit = int(limit)
            limit = max(1, min(limit, 100))
        except (TypeError, ValueError):
            limit = None

    months_ahead = cleaned.get("months_ahead")
    if months_ahead not in (None, ""):
        try:
            months_ahead = int(months_ahead)
            months_ahead = max(1, min(months_ahead, 12))
        except (TypeError, ValueError):
            months_ahead = None

    cleaned["country"] = country
    cleaned["country1"] = country1
    cleaned["country2"] = country2
    cleaned["year"] = year
    cleaned["month"] = month
    cleaned["limit"] = limit
    cleaned["months_ahead"] = months_ahead

    # Preserve a normalized countries list when available.
    countries = []
    raw_countries = cleaned.get("countries")

    if isinstance(raw_countries, (list, tuple)):
        for item in raw_countries:
            c = _normalize_country(item)
            if c and c not in countries:
                countries.append(c)

    for c in (country1, country2):
        if c and c not in countries:
            countries.append(c)

    if countries:
        cleaned["countries"] = countries
    else:
        cleaned.pop("countries", None)

    return cleaned


# ---------------------------------------------------------------------
# Parameter extraction
# ---------------------------------------------------------------------

def safe_extract_parameters(question: str) -> Dict[str, Any]:
    """
    Run the project's parameter extractor and normalize the output.

    The extractor is expected to provide:
        country, country1, country2, countries, year, month, limit

    Forecast horizon is extracted deterministically here because it is
    specific to the forecasting capability and does not require the
    generic parameter extractor to understand forecast wording.

    This function remains defensive so the planner still works if an
    older extractor returns only the original fields.
    """
    try:
        raw = extract_parameters(question)
    except Exception:
        raw = {}

    if not isinstance(raw, dict):
        raw = {}

    raw["months_ahead"] = _extract_forecast_horizon(question)

    return validate_extracted_parameters(raw)


# ---------------------------------------------------------------------
# Comparison-specific parameter handling
# ---------------------------------------------------------------------

def _infer_comparison_countries(
    question: str,
    params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Make sure comparison questions have two countries.

    Primary source:
        parameter_extractor.extract_parameters()

    Fallback source:
        simple text matching for known country names/codes.

    No business values are inferred here.
    """
    updated = dict(params)

    country1 = updated.get("country1")
    country2 = updated.get("country2")

    countries = updated.get("countries")
    if isinstance(countries, (list, tuple)):
        normalized = []
        for item in countries:
            c = _normalize_country(item)
            if c and c not in normalized:
                normalized.append(c)

        if not country1 and normalized:
            country1 = normalized[0]

        if not country2 and len(normalized) >= 2:
            country2 = normalized[1]

    text = _normalize_text(question)

    # Country mention order is used only as a fallback.
    mention_patterns = [
        ("IN", [r"\bindia\b", r"\bin\b"]),
        ("US", [r"\busa\b", r"\bu\.s\.\b", r"\bu\.s\.a\b", r"\bus\b", r"\bamerica\b"]),
        ("DE", [r"\bgermany\b", r"\bde\b"]),
        ("UK", [r"\buk\b", r"\bu\.k\.\b", r"\bbritain\b"]),
        ("CA", [r"\bcanada\b", r"\bca\b"]),
        ("AE", [r"\buae\b", r"\bae\b"]),
    ]

    # Prefer full names first to avoid short-code ambiguity.
    ordered_mentions: List[str] = []

    full_name_patterns = [
        ("IN", r"\bindia\b"),
        ("US", r"\b(?:usa|u\.s\.a|u\.s\.|america)\b"),
        ("DE", r"\bgermany\b"),
        ("UK", r"\b(?:united kingdom|britain)\b"),
        ("CA", r"\bcanada\b"),
        ("AE", r"\b(?:uae|united arab emirates)\b"),
    ]

    positions = []
    for code, pattern in full_name_patterns:
        match = re.search(pattern, text)
        if match:
            positions.append((match.start(), code))

    for _, code in sorted(positions):
        if code not in ordered_mentions:
            ordered_mentions.append(code)

    if not country1 and ordered_mentions:
        country1 = ordered_mentions[0]

    if not country2 and len(ordered_mentions) >= 2:
        country2 = ordered_mentions[1]

    # Final fallback using extracted single country + another country
    # name/code in the question.
    if country1 and not country2:
        candidates = []
        for code, patterns in mention_patterns:
            if code == country1:
                continue

            if any(re.search(pattern, text) for pattern in patterns):
                candidates.append(code)

        for code in candidates:
            if code != country1:
                country2 = code
                break

    updated["country1"] = _normalize_country(country1)
    updated["country2"] = _normalize_country(country2)

    comparison_countries = []
    for c in (updated["country1"], updated["country2"]):
        if c and c not in comparison_countries:
            comparison_countries.append(c)

    updated["countries"] = comparison_countries

    return updated


# ---------------------------------------------------------------------
# Parameter enforcement by capability
# ---------------------------------------------------------------------

def enforce_parameters(
    capability: str,
    params: Dict[str, Any],
    question: str = "",
) -> Dict[str, Any]:
    """
    Return only parameters valid for the selected capability.

    This is the final guard immediately before execution.
    """
    capability = str(capability or "").strip().upper()

    if capability not in ALLOWED_CAPABILITIES:
        raise ValueError(f"Unsupported capability: {capability}")

    params = validate_extracted_parameters(params)
    text = _normalize_text(question)

    # ---------------------------------------------------------------
    # COMPARISON_ANALYSIS
    # ---------------------------------------------------------------
    if capability == "COMPARISON_ANALYSIS":
        params = _infer_comparison_countries(text, params)

        country1 = _normalize_country(params.get("country1"))
        country2 = _normalize_country(params.get("country2"))

        if not country1 or not country2:
            raise ValueError(
                "Comparison requires two countries. "
                "Example: 'Compare India and US.'"
            )

        if country1 == country2:
            raise ValueError(
                "Comparison requires two different countries."
            )

        result = {
            "country1": country1,
            "country2": country2,
        }

        year = _normalize_year(params.get("year"))
        month = _normalize_month(params.get("month"))

        if year is not None:
            result["year"] = year

        if month is not None:
            result["month"] = month

        return result
    
    # ---------------------------------------------------------------
    # TREND_ANALYSIS
    # ---------------------------------------------------------------
    if capability == "TREND_ANALYSIS":
        result: Dict[str, Any] = {}

        if params.get("country"):
            result["country"] = params["country"]

        if params.get("year") is not None:
            result["year"] = params["year"]

        if params.get("month") is not None:
            result["month"] = params["month"]

        return result

    # ---------------------------------------------------------------
    # COUNTRY_PERFORMANCE
    # ---------------------------------------------------------------
    if capability == "COUNTRY_PERFORMANCE":
        return {}

    # ---------------------------------------------------------------
    # EXECUTIVE_KPI
    # ---------------------------------------------------------------
    if capability == "EXECUTIVE_KPI":
        return {}

    # ---------------------------------------------------------------
    # MONTHLY_PERFORMANCE
    # ---------------------------------------------------------------
    if capability == "MONTHLY_PERFORMANCE":
        return {}

    # ---------------------------------------------------------------
    # SALES_FORECAST
    # ---------------------------------------------------------------
    if capability == "SALES_FORECAST":

        months_ahead = params.get("months_ahead")

        if months_ahead is None:
            months_ahead = _extract_forecast_horizon(text)

        try:
            months_ahead = int(months_ahead)
        except (TypeError, ValueError):
            months_ahead = 3

        months_ahead = max(
            1,
            min(months_ahead, 12)
        )

        result = {
            "months_ahead": months_ahead
        }

        # Optional country
        country = _normalize_country(
            params.get("country")
        )

        if country:
            result["country"] = country

        # Optional year
        year = _normalize_year(
            params.get("year")
        )

        if year is not None:
            result["year"] = year

        return result
    
    # ---------------------------------------------------------------
    # DATA_QUALITY
    # ---------------------------------------------------------------
    if capability == "DATA_QUALITY":
        return {}

    # ---------------------------------------------------------------
    # ADVERTISING_RISKS
    # ---------------------------------------------------------------
    if capability == "ADVERTISING_RISKS":
        limit = params.get("limit")
        return {"limit": limit or 20}

    # ---------------------------------------------------------------
    # INVENTORY_RISKS
    # ---------------------------------------------------------------
    if capability == "INVENTORY_RISKS":
        limit = params.get("limit")
        return {"limit": limit or 20}

    # ---------------------------------------------------------------
    # INVENTORY_RISKS_FOR_SKUS
    # ---------------------------------------------------------------
    if capability == "INVENTORY_RISKS_FOR_SKUS":
        skus = params.get("skus")

        if isinstance(skus, str):
            skus = [skus]

        if not isinstance(skus, list):
            skus = []

        cleaned_skus = []
        for sku in skus:
            sku = str(sku).strip()
            if sku and sku not in cleaned_skus:
                cleaned_skus.append(sku)

        if not cleaned_skus:
            raise ValueError(
                "INVENTORY_RISKS_FOR_SKUS requires an explicit SKU list "
                "or SKUs supplied by a dependency step."
            )

        return {"skus": cleaned_skus[:100]}

    # ---------------------------------------------------------------
    # TOP_PRODUCTS
    # ---------------------------------------------------------------
    if capability == "TOP_PRODUCTS":
        return {"limit": params.get("limit") or 10}

    # ---------------------------------------------------------------
    # PRODUCT_RANKING
    # ---------------------------------------------------------------
    if capability == "PRODUCT_RANKING":
        result: Dict[str, Any] = {
            "limit": params.get("limit") or 10
        }

        # Only pass explicitly extracted filters.
        if params.get("country"):
            result["country"] = params["country"]

        if params.get("year") is not None:
            result["year"] = params["year"]

        if params.get("month") is not None:
            result["month"] = params["month"]

        return result

    return {}


# ---------------------------------------------------------------------
# Deterministic dependency handling
# ---------------------------------------------------------------------

def add_dependencies(steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Add trusted dependent steps.

    Current dependency:
        PRODUCT_RANKING
            -> INVENTORY_RISKS_FOR_SKUS

    The executor will take SKUs from the PRODUCT_RANKING result and
    feed them to the dependent inventory tool.
    """
    if not steps:
        return steps

    final_steps: List[Dict[str, Any]] = []

    for step in steps:
        current = dict(step)
        capability = current.get("capability")

        final_steps.append(current)

        if capability == "PRODUCT_RANKING":
            dependency = {
                "capability": "INVENTORY_RISKS_FOR_SKUS",
                "parameters": {
                    "skus_from_step": len(final_steps)
                },
                "depends_on": len(final_steps) - 1,
                "reason": (
                    "Use the SKUs returned by product ranking to retrieve "
                    "trusted inventory risk for those same SKUs."
                ),
            }
            final_steps.append(dependency)

    return final_steps


# ---------------------------------------------------------------------
# LLM fallback planner
# ---------------------------------------------------------------------

def llm_plan_question(question: str) -> List[Dict[str, Any]]:
    """
    Ask the local LLM for a plan only when deterministic routing cannot
    confidently classify the question.

    This function intentionally does not send business data to an
    external hosted model. It relies on the project's local LLM layer.
    """
    try:
        from src.agent.llm import generate_response

        capability_names = sorted(ALLOWED_CAPABILITIES)

        prompt = f"""
You are a planning component for a business analytics agent.

Choose exactly one capability from this list:
{json.dumps(capability_names, indent=2)}

User question:
{question}

Rules:
1. Return JSON only.
2. Do not calculate any business metric.
3. Do not invent data.
4. For country-vs-country questions, choose COMPARISON_ANALYSIS.
5. For rankings of products/SKUs, choose PRODUCT_RANKING or TOP_PRODUCTS.
6. For inventory risk, choose INVENTORY_RISKS.
7. For advertising efficiency/risk, choose ADVERTISING_RISKS.
8. For monthly trends, choose MONTHLY_PERFORMANCE.
9. For sales forecasting or future sales prediction, choose SALES_FORECAST.
10. For country-level overall performance, choose COUNTRY_PERFORMANCE.
11. For broad business KPIs, choose EXECUTIVE_KPI.
12. For data problems, choose DATA_QUALITY.

Output format:
{{
  "capability": "CAPABILITY_NAME"
}}
"""

        raw = generate_response(prompt)

        # Strip accidental markdown fences.
        cleaned = str(raw).strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.I)
        cleaned = re.sub(r"\s*```$", "", cleaned)

        parsed = json.loads(cleaned)

        capability = str(parsed.get("capability", "")).strip().upper()

        if capability in ALLOWED_CAPABILITIES:
            return [
                {
                    "capability": capability,
                    "parameters": safe_extract_parameters(question),
                    "source": "llm_fallback",
                }
            ]

    except Exception:
        pass

    return []


# ---------------------------------------------------------------------
# Tool-name helper
# ---------------------------------------------------------------------

def _tool_name(capability: str) -> str:
    """Return the executor tool name for a capability.

    DYNAMIC_SQL is executed by the dynamic SQL agent but is intentionally
    not a trusted business capability in the CAPABILITIES registry because
    it is an analysis fallback rather than a deterministic BI tool.
    """
    capability = str(capability or "").strip().upper()

    if capability == "DYNAMIC_SQL":
        return "dynamic_sql"

    return CAPABILITIES[capability]["tool"]


# ---------------------------------------------------------------------
# Main planner
# ---------------------------------------------------------------------

def plan_question(question: str) -> Dict[str, Any]:
    """
    Build an executable plan for one user question.

    Returned shape:
    {
        "question": "...",
        "steps": [
            {
                "step": 1,
                "capability": "COMPARISON_ANALYSIS",
                "tool": "comparison_analysis",
                "parameters": {
                    "country1": "IN",
                    "country2": "US"
                },
                "source": "deterministic"
            }
        ]
    }
    """
    if not isinstance(question, str) or not question.strip():
        raise ValueError("Question cannot be empty.")

    normalized_question = question.strip()
    extracted = safe_extract_parameters(normalized_question)

    # ---------------------------------------------------------------
    # 1. Deterministic routing
    # ---------------------------------------------------------------
    capability = detect_capability(normalized_question)

    # ---------------------------------------------------------------
    # 2. Deterministic sales forecasting
    # ---------------------------------------------------------------
    if capability == "SALES_FORECAST":
        forecast_parameters = enforce_parameters(
            "SALES_FORECAST",
            extracted,
            normalized_question,
        )

        step = {
            "step": 1,
            "capability": "SALES_FORECAST",
            "tool": CAPABILITIES["SALES_FORECAST"]["tool"],
            "parameters": forecast_parameters,
            "source": "deterministic",
        }

        return {
            "question": normalized_question,
            "steps": [step],
        }

    # ---------------------------------------------------------------
    # 3. LLM fallback only when deterministic routing fails
    # ---------------------------------------------------------------
    if capability is None:
        llm_steps = llm_plan_question(normalized_question)

        if llm_steps:
            steps = []
            for raw_step in llm_steps:
                raw_capability = str(
                    raw_step.get("capability", "")
                ).upper()

                if raw_capability not in ALLOWED_CAPABILITIES:
                    continue

                raw_params = dict(extracted)

                # Preserve explicit parameters returned by the LLM plan,
                # but normalize them before use.
                llm_params = raw_step.get("parameters")
                if isinstance(llm_params, dict):
                    raw_params.update(llm_params)

                try:
                    final_params = enforce_parameters(
                        raw_capability,
                        raw_params,
                        normalized_question,
                    )
                except ValueError:
                    continue

                steps.append(
                    {
                        "capability": raw_capability,
                        "parameters": final_params,
                        "source": "llm_fallback",
                    }
                )

            if steps:
                steps = add_dependencies(steps)
                return {
                    "question": normalized_question,
                    "steps": [
                        {
                            "step": i + 1,
                            **step,
                            "tool": _tool_name(step["capability"]),
                        }
                        for i, step in enumerate(steps)
                    ],
                }

        raise ValueError(
            "I could not confidently map this question to a supported "
            "business analytics capability."
        )

    # ---------------------------------------------------------------
    # 3. Complex multi-step business questions
    # ---------------------------------------------------------------
    # These questions require a trusted structured result plus a second
    # analytical pass. Keep this deterministic so a small local model
    # cannot accidentally drop the explanation step.
    text = _normalize_text(normalized_question)

    country_best_why = (
        ("which country performed best" in text
         or "best country" in text
         or "top country" in text)
        and "why" in text
    )

    if country_best_why:
        steps: List[Dict[str, Any]] = [
            {
                "capability": "COUNTRY_PERFORMANCE",
                "parameters": enforce_parameters(
                    "COUNTRY_PERFORMANCE",
                    extracted,
                    normalized_question,
                ),
                "source": "deterministic",
                "reason": (
                    "Establish the verified country-level performance ranking."
                ),
            },
            {
                "capability": "DYNAMIC_SQL",
                "parameters": {},
                "source": "deterministic",
                "reason": (
                    "Analyze supporting metrics explaining the strongest country's performance."
                ),
            },
        ]

        return {
            "question": normalized_question,
            "steps": [
                {
                    "step": i + 1,
                    **step,
                    "tool": _tool_name(step["capability"]),
                }
                for i, step in enumerate(steps)
            ],
        }

    # ---------------------------------------------------------------
    # 4. Explicit comparison always wins.
    # ---------------------------------------------------------------
    if capability == "COMPARISON_ANALYSIS":
        comparison_params = enforce_parameters(
            "COMPARISON_ANALYSIS",
            extracted,
            normalized_question,
        )

        step = {
            "step": 1,
            "capability": "COMPARISON_ANALYSIS",
            "tool": CAPABILITIES["COMPARISON_ANALYSIS"]["tool"],
            "parameters": comparison_params,
            "source": "deterministic",
        }

        return {
            "question": normalized_question,
            "steps": [step],
        }

    # ---------------------------------------------------------------
    # 4. Product ranking + inventory dependency
    # ---------------------------------------------------------------
    params_for_capability = dict(extracted)

    # PRODUCT_RANKING is the deterministic capability for SKU/product
    # ranking questions, including optional country/year/month filters.
    final_parameters = enforce_parameters(
        capability,
        params_for_capability,
        normalized_question,
    )

    steps: List[Dict[str, Any]] = [
        {
            "capability": capability,
            "parameters": final_parameters,
            "source": "deterministic",
        }
    ]

    steps = add_dependencies(steps)

    return {
        "question": normalized_question,
        "steps": [
            {
                "step": i + 1,
                **step,
                "tool": _tool_name(step["capability"]),
            }
            for i, step in enumerate(steps)
        ],
    }


# ---------------------------------------------------------------------
# Debug helper
# ---------------------------------------------------------------------

def print_plan(plan: Dict[str, Any]) -> None:
    """Pretty-print a generated plan for debugging."""
    print("\n" + "=" * 70)
    print("PLANNER OUTPUT")
    print("=" * 70)
    print(f"Question: {plan.get('question', '')}")

    for step in plan.get("steps", []):
        print(
            f"\nStep {step.get('step')}: "
            f"{step.get('capability')} "
            f"-> {step.get('tool')}"
        )
        print("Parameters:", step.get("parameters", {}))
        print("Source:", step.get("source"))


# ---------------------------------------------------------------------
# Local tests
# ---------------------------------------------------------------------

def _test(question: str) -> None:
    """Run one planner test and print the result."""
    print(f"\nQUESTION: {question}")

    try:
        plan = plan_question(question)
        print_plan(plan)
    except Exception as exc:
        print("ERROR:", exc)


if __name__ == "__main__":
    print("\nAI BUSINESS ANALYST AGENT - PLANNER TESTS")

    test_questions = [
        "What are the top 5 SKUs by sales?",
        "Show the top 10 products in India for 2026.",
        "Show monthly performance.",
        "Show country performance.",
        "Which country has the highest sales?",
        "Show advertising risks.",
        "Show inventory risks.",
        "Show data quality.",
        "Give me the overall business KPIs.",
        "Compare India and US.",
        "Compare India and USA for 2026.",
        "Compare India and US in August 2026.",
        "Forecast sales for the next 3 months.",
        "Forecast sales for the next 3 months in India for 2026.",
        "What are the predicted sales for the next six months?",
        "Give me a sales forecast.",
        "Forecast the sales trend for the next 3 months.",
    ]

    for question in test_questions:
        _test(question)
