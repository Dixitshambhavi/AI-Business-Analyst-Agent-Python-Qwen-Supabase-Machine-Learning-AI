from typing import Any

from src.agent.tools import execute_tool


# ============================================================
# CAPABILITY → TOOL MAPPING
# ============================================================

CAPABILITY_TOOL_MAP = {

    "EXECUTIVE_KPI":
        "executive_analysis",

    "PRODUCT_RANKING":
        "product_ranking",

    "TOP_PRODUCTS":
        "top_products",

    "MONTHLY_PERFORMANCE":
        "monthly_performance",

    "SALES_FORECAST":
        "sales_forecast",

    "COUNTRY_PERFORMANCE":
        "country_performance",

    "ADVERTISING_RISKS":
        "advertising_risks",

    "INVENTORY_RISKS":
        "inventory_risks",

    "INVENTORY_RISKS_FOR_SKUS":
        "inventory_risks_for_skus",

    "DATA_QUALITY":
        "data_quality",
}


# ============================================================
# SAFE PARAMETER VALIDATION
# ============================================================

def validate_parameters(
    capability: str,
    parameters: dict[str, Any]
) -> dict[str, Any]:
    """
    Validate and normalize parameters before a trusted tool
    is executed.

    The LLM does not directly control the database.
    """

    if parameters is None:
        parameters = {}

    if not isinstance(parameters, dict):
        raise ValueError(
            "Tool parameters must be a JSON object."
        )

    # --------------------------------------------------------
    # TOP PRODUCTS
    # --------------------------------------------------------

        # --------------------------------------------------------
    # TOP PRODUCTS
    # --------------------------------------------------------

    if capability == "TOP_PRODUCTS":

        limit = parameters.get(
            "limit",
            10
        )

        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 10

        # Safe bounds
        limit = max(1, min(limit, 100))

        return {
            "limit": limit
        }


    # --------------------------------------------------------
    # PRODUCT RANKING
    # --------------------------------------------------------

    if capability == "PRODUCT_RANKING":

        country = parameters.get(
            "country"
        )

        year = parameters.get(
            "year"
        )

        month = parameters.get(
            "month"
        )

        limit = parameters.get(
            "limit",
            10
        )

        # ----------------------------------------------------
        # Validate limit
        # ----------------------------------------------------

        try:
            limit = int(limit)
        except (TypeError, ValueError):

            limit = 10

        limit = max(
            1,
            min(limit, 100)
        )

        # ----------------------------------------------------
        # Validate country
        # ----------------------------------------------------

        if country is not None:

            country = str(
                country
            ).strip().upper()

            allowed_countries = {
                "IN",
                "US",
                "DE",
                "UK",
                "CA",
                "AE",
            }

            if country not in allowed_countries:

                raise ValueError(
                    f"Unsupported country code: {country}"
                )

        # ----------------------------------------------------
        # Validate year
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Validate month
        # ----------------------------------------------------

        if month is not None:

            month = str(
                month
            ).strip()

            import re

            if not re.match(
                r"^\d{4}-\d{2}$",
                month
            ):

                raise ValueError(
                    "Month must use YYYY-MM format."
                )

            month_number = int(
                month.split("-")[1]
            )

            if month_number < 1 or month_number > 12:

                raise ValueError(
                    "Month must be between 01 and 12."
                )

        return {
            "country": country,
            "year": year,
            "month": month,
            "limit": limit,
        }

 
    # --------------------------------------------------------
# SALES FORECAST
# --------------------------------------------------------

    if capability == "SALES_FORECAST":

        months_ahead = parameters.get(
            "months_ahead",
            3
        )

        try:
            months_ahead = int(months_ahead)
        except (TypeError, ValueError):
            months_ahead = 3

        months_ahead = max(
            1,
            min(months_ahead, 12)
        )

        country = parameters.get(
            "country"
        )

        if country is not None:

            country = str(
                country
            ).strip().upper()

            allowed_countries = {
                "IN",
                "US",
                "DE",
                "UK",
                "CA",
                "AE",
            }

            if country not in allowed_countries:
                raise ValueError(
                    f"Unsupported country code: {country}"
                )

        year = parameters.get(
            "year"
        )

        if year is not None:

            try:
                year = int(year)
            except (TypeError, ValueError):
                year = None

            if year is not None and (
                year < 2000
                or year > 2100
            ):
                raise ValueError(
                    "Year must be between 2000 and 2100."
                )

        return {
            "months_ahead": months_ahead,
            "country": country,
            "year": year,
        }

    # --------------------------------------------------------
    # ADVERTISING RISKS
    # --------------------------------------------------------

    if capability == "ADVERTISING_RISKS":

        limit = parameters.get(
            "limit",
            20
        )

        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 20

        limit = max(1, min(limit, 100))

        return {
            "limit": limit
        }

    # --------------------------------------------------------
    # INVENTORY RISKS
    # --------------------------------------------------------

    if capability == "INVENTORY_RISKS":

        limit = parameters.get(
            "limit",
            20
        )

        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 20

        limit = max(1, min(limit, 100))

        return {
            "limit": limit
        }

    # --------------------------------------------------------
    # DEPENDENT INVENTORY
    # --------------------------------------------------------

    if capability == "INVENTORY_RISKS_FOR_SKUS":

        skus = parameters.get(
            "skus"
        )

        # This is allowed because the Python orchestrator
        # can populate the SKUs from a previous tool result.
        if skus is None:
            return {
                "skus_from_step":
                    parameters.get("skus_from_step")
            }

        if not isinstance(skus, list):
            raise ValueError(
                "SKUs must be provided as a list."
            )

        cleaned = []

        for sku in skus:

            if sku is None:
                continue

            sku = str(sku).strip()

            if sku and sku not in cleaned:
                cleaned.append(sku)

        if not cleaned:
            raise ValueError(
                "No valid SKUs were provided."
            )

        if len(cleaned) > 100:
            raise ValueError(
                "Maximum of 100 SKUs allowed."
            )

        return {
            "skus": cleaned
        }

    # --------------------------------------------------------
    # TOOLS WITHOUT PARAMETERS
    # --------------------------------------------------------

    if capability in {
        "EXECUTIVE_KPI",
        "MONTHLY_PERFORMANCE",
        "COUNTRY_PERFORMANCE",
        "DATA_QUALITY",
    }:

        return {}

    raise ValueError(
        f"Unsupported capability: {capability}"
    )


# ============================================================
# EXTRACT SKUS FROM TOOL RESULT
# ============================================================

def extract_skus_from_result(
    result: dict[str, Any]
) -> list[str]:
    """
    Extract SKU identifiers from the result of top_products.
    """

    data = result.get(
        "data",
        []
    )

    if not isinstance(data, list):
        return []

    skus = []

    for row in data:

        if not isinstance(row, dict):
            continue

        sku = row.get("sku")

        if sku is None:
            continue

        sku = str(sku).strip()

        if sku and sku not in skus:
            skus.append(sku)

    return skus


# ============================================================
# EXECUTE ONE STEP
# ============================================================

def execute_step(
    step: dict[str, Any],
    previous_results: list[dict[str, Any]]
) -> dict[str, Any]:
    """
    Execute a single trusted capability.

    previous_results allows dependent tool calls.
    """

    if not isinstance(step, dict):

        raise ValueError(
            "Each plan step must be a JSON object."
        )

    capability = str(
        step.get(
            "capability",
            ""
        )
    ).strip().upper()

    # ------------------------------------------------------------
    # DYNAMIC SQL
    # ------------------------------------------------------------
    # DYNAMIC_SQL is an analysis agent, not a normal entry in the
    # CAPABILITY_TOOL_MAP. It must therefore be handled before the
    # normal capability lookup.
    if capability == "DYNAMIC_SQL":
        original_question = str(
            step.get(
                "_original_question",
                ""
            )
        ).strip()

        if not original_question:
            raise ValueError(
                "DYNAMIC_SQL requires the original business question."
            )

        previous_context_parts = []

        for index, previous in enumerate(
            previous_results,
            start=1
        ):
            if not isinstance(previous, dict):
                continue

            formatted = previous.get(
                "formatted",
                ""
            )

            if formatted:
                previous_context_parts.append(
                    f"ANALYSIS STEP {index}\n{formatted}"
                )

        previous_context = "\n\n".join(
            previous_context_parts
        )

        if previous_context:
            enhanced_question = f"""
Original business question:

{original_question}

Previous verified analysis:

{previous_context}

Use the previous verified analysis as authoritative evidence.
Do not contradict it.
Do not invent data.

Now perform the additional SQL analysis required to answer
the original business question.
"""
        else:
            enhanced_question = original_question

        from src.agent.sql_agent import answer_dynamic_question

        result_text = answer_dynamic_question(
            enhanced_question
        )

        return {
            "step": step.get("step"),
            "capability": "DYNAMIC_SQL",
            "tool": "dynamic_sql",
            "parameters": {},
            "formatted": result_text,
            "raw_result": {
                "answer": result_text
            }
        }

    if capability not in CAPABILITY_TOOL_MAP:

        raise ValueError(
            f"Unknown capability: {capability}"
        )

    raw_parameters = step.get(
        "parameters",
        {}
    )

    parameters = validate_parameters(
        capability,
        raw_parameters
    )

    tool_name = CAPABILITY_TOOL_MAP[
        capability
    ]

    # ========================================================
    # DEPENDENT TOOL
    # ========================================================

    if capability == "INVENTORY_RISKS_FOR_SKUS":

        # ----------------------------------------------------
        # Explicit SKU list
        # ----------------------------------------------------

        if "skus" in parameters:

            skus = parameters["skus"]

        # ----------------------------------------------------
        # SKUs from previous step
        # ----------------------------------------------------

        else:

            source_step = parameters.get(
                "skus_from_step"
            )

            if source_step is None:
                raise ValueError(
                    "INVENTORY_RISKS_FOR_SKUS requires either "
                    "'skus' or 'skus_from_step'."
                )

            try:
                source_index = int(
                    source_step
                )
            except (TypeError, ValueError):

                raise ValueError(
                    "'skus_from_step' must be an integer."
                )

            # Planner uses 1-based step numbering.
            actual_index = source_index - 1

            if (
                actual_index < 0
                or actual_index >= len(previous_results)
            ):

                raise ValueError(
                    "Referenced previous step does not exist."
                )

            source_result = previous_results[
                actual_index
            ]

            skus = extract_skus_from_result(
                source_result
            )

            if not skus:

                raise ValueError(
                    "No SKUs could be extracted from "
                    "the previous step."
                )

        print()
        print(
            "Passing SKUs to inventory tool:"
        )

        for sku in skus:
            print(
                f"  → {sku}"
            )

        return execute_tool(
            tool_name,
            skus=skus
        )

    # ========================================================
    # NORMAL TOOLS
    # ========================================================

    return execute_tool(
        tool_name,
        **parameters
    )


# ============================================================
# EXECUTE COMPLETE PLAN
# ============================================================

def execute_plan(
    plan: dict[str, Any]
) -> dict[str, Any]:
    """
    Execute the complete structured plan sequentially.
    """

    if not isinstance(plan, dict):

        raise ValueError(
            "Plan must be a JSON object."
        )

    steps = plan.get(
        "steps"
    )

    if not isinstance(steps, list):

        raise ValueError(
            "Plan must contain a 'steps' list."
        )

    if not steps:

        raise ValueError(
            "Plan contains no steps."
        )

    if len(steps) > 10:

        raise ValueError(
            "A maximum of 10 steps is allowed."
        )

    results = []

    for index, step in enumerate(
        steps,
        start=1
    ):

        capability = step.get(
            "capability",
            "UNKNOWN"
        )

        print()
        print("=" * 60)
        print(
            f"EXECUTING STEP {index}: {capability}"
        )
        print("=" * 60)

        current_step = dict(step)

        if str(
            current_step.get(
                "capability",
                ""
            )
        ).strip().upper() == "DYNAMIC_SQL":
            current_step["_original_question"] = str(
                plan.get(
                    "question",
                    ""
                )
            ).strip()

        result = execute_step(
            current_step,
            results
        )

        results.append(
            result
        )

        print(
            f"✓ Step {index} completed"
        )

    return {
        "plan": plan,
        "results": results,
    }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    test_plan = {
        "steps": [
            {
                "capability": "TOP_PRODUCTS",
                "parameters": {
                    "limit": 5
                }
            },
            {
                "capability": "INVENTORY_RISKS_FOR_SKUS",
                "parameters": {
                    "skus_from_step": 1
                }
            },
            {
                "capability": "SALES_FORECAST",
                "parameters": {
                    "months_ahead": 3
                }
            }
        ]
    }

    print()
    print("=" * 70)
    print("TESTING QUERY EXECUTOR")
    print("=" * 70)

    result = execute_plan(
        test_plan
    )

    print()
    print("=" * 70)
    print("EXECUTOR TEST COMPLETED")
    print("=" * 70)

    print()
    print("Number of steps executed:")
    print(
        len(result["results"])
    )