from __future__ import annotations

import json
from typing import Any, Dict, List

from src.agent.llm import generate_response


# ============================================================
# AVAILABLE ANALYSIS OPERATIONS
# ============================================================

AVAILABLE_OPERATIONS = [
    "monthly_performance",
    "country_performance",
    "product_ranking",
    "trend_analysis",
    "comparison_analysis",
    "driver_analysis",
    "advertising_risks",
    "inventory_risks",
    "data_quality",
    "dynamic_sql",
]


# ============================================================
# BUILD REASONING PROMPT
# ============================================================

def build_reasoning_prompt(
    question: str,
) -> str:

    operations = json.dumps(
        AVAILABLE_OPERATIONS,
        indent=2,
    )

    return f"""
You are the reasoning planner for a local AI Business Analyst.

Your task is to decompose a complex business question into
the smallest set of analytical operations required to answer it.

USER QUESTION:
{question}

AVAILABLE OPERATIONS:
{operations}

RULES:

1. Return JSON only.
2. Do not calculate business metrics.
3. Do not invent data.
4. Use only operations from the available list.
5. Use the minimum number of steps required.
6. Never use comparison_analysis unless the user explicitly asks
   to compare two countries.
7. For "why did sales change/decline/increase" questions:
   use trend_analysis or monthly_performance when overall period
   comparison or trend context is required.
   When the question asks what drove the change, which SKUs,
   countries, or segments contributed to the change, use
   driver_analysis.
   Use dynamic_sql only when additional analysis is required.
8. For "which country performed best" questions:
   use country_performance first, then dynamic_sql only if
   additional explanation is required.
9. For product-specific performance questions:
   use product_ranking first.
10. For advertising-related questions:
    use advertising_risks or dynamic_sql.
11. For inventory-related questions:
    use inventory_risks.
12. Use data_quality only when the question asks about data quality
    or when data reliability must explicitly be checked.
13. Preserve country, year, month, and SKU filters from the user.
14. Every step must directly contribute to answering the question.
15. Do not add unrelated operations.
16. Return no more than 4 steps.
17. Every step must have:
    - operation
    - purpose


EXAMPLES:

Question:
"Why did sales decline in May 2026?"

Good plan:
{{
  "steps": [
    {{
      "operation": "trend_analysis",
      "purpose": "Analyze monthly sales, units, advertising spend, ad revenue, ROAS and TACOS around May 2026."
    }},
    {{
      "operation": "dynamic_sql",
      "purpose": "Identify the products or countries contributing most to the May sales decline."
    }}
  ]
}}

Question:
"What drove the sales decline in May 2026?"

Good plan:
{{
  "steps": [
    {{
      "operation": "driver_analysis",
      "purpose": "Identify the biggest SKU and country contributors to the April-to-May 2026 sales decline."
    }}
  ]
}}

Question:
"Which SKUs contributed most to the sales decline in May 2026?"

Good plan:
{{
  "steps": [
    {{
      "operation": "driver_analysis",
      "purpose": "Rank the SKUs contributing most to the April-to-May 2026 sales decline."
    }}
  ]
}}

Question:
"Which country performed best in 2026 and why?"

Good plan:
{{
  "steps": [
    {{
      "operation": "country_performance",
      "purpose": "Compare sales, units, ad spend, ad revenue, ROAS and TACOS across countries for 2026."
    }},
    {{
      "operation": "dynamic_sql",
      "purpose": "Analyze the metrics explaining why the strongest country performed better."
    }}
  ]
}}


Question:
"Which SKUs have high advertising spend but weak sales?"

Good plan:
{{
  "steps": [
    {{
      "operation": "advertising_risks",
      "purpose": "Identify products and periods with advertising efficiency risks."
    }}
  ]
}}

Question:
"Show me the sales trend for 2026."

Good plan:
{{
  "steps": [
    {{
      "operation": "trend_analysis",
      "purpose": "Retrieve trusted monthly sales and supporting business trends for 2026."
    }}
  ]
}}


OUTPUT FORMAT:

{{
  "steps": [
    {{
      "operation": "trend_analysis",
      "purpose": "Retrieve monthly sales and advertising trends."
    }},
    {{
      "operation": "dynamic_sql",
      "purpose": "Investigate the metric contributing most to the change."
    }}
  ]
}}
"""


# ============================================================
# EXTRACT JSON
# ============================================================

def extract_json(
    response: str,
) -> Dict[str, Any]:

    if not response:
        raise ValueError(
            "Reasoning planner returned an empty response."
        )

    text = str(
        response
    ).strip()

    # Remove markdown code fences
    if text.startswith("```"):

        lines = text.splitlines()

        if lines:
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    try:
        parsed = json.loads(text)

    except json.JSONDecodeError:

        raise ValueError(
            "Reasoning planner did not return valid JSON."
        )

    if not isinstance(parsed, dict):

        raise ValueError(
            "Reasoning plan must be a JSON object."
        )

    return parsed


# ============================================================
# VALIDATE PLAN
# ============================================================

def validate_reasoning_plan(
    plan: Dict[str, Any],
) -> Dict[str, Any]:

    steps = plan.get(
        "steps"
    )

    if not isinstance(
        steps,
        list,
    ):

        raise ValueError(
            "Reasoning plan must contain a 'steps' list."
        )

    if not steps:

        raise ValueError(
            "Reasoning plan cannot be empty."
        )

    # Maximum 4 steps
    if len(steps) > 4:

        raise ValueError(
            "Reasoning plan cannot contain more than 4 steps."
        )

    validated_steps: List[Dict[str, str]] = []

    for step in steps:

        if not isinstance(
            step,
            dict,
        ):

            raise ValueError(
                "Each reasoning step must be an object."
            )

        operation = str(
            step.get(
                "operation",
                "",
            )
        ).strip()

        purpose = str(
            step.get(
                "purpose",
                "",
            )
        ).strip()

        if operation not in AVAILABLE_OPERATIONS:

            raise ValueError(
                f"Unsupported reasoning operation: {operation}"
            )

        if not purpose:

            raise ValueError(
                "Every reasoning step must contain a purpose."
            )

        validated_steps.append(
            {
                "operation": operation,
                "purpose": purpose,
            }
        )

    return {
        "steps": validated_steps
    }


# ============================================================
# DETERMINISTIC REASONING OVERRIDES
# ============================================================

def apply_reasoning_overrides(
    question: str,
) -> Dict[str, Any]:

    q = question.lower().strip()

    # --------------------------------------------------------
    # DRIVER ANALYSIS
    # --------------------------------------------------------

    driver_keywords = [
        "what drove",
        "what drive",
        "sales drivers",
        "sales driver",
        "contributed most",
        "contributed to the decline",
        "contributed to the increase",
        "biggest contributor",
        "biggest contributors",
        "main contributor",
        "main contributors",
        "top contributors",
        "which skus contributed",
        "which sku contributed",
        "which countries contributed",
        "which country contributed",
    ]

    if any(
        keyword in q
        for keyword in driver_keywords
    ):
        return {
            "steps": [
                {
                    "operation": "driver_analysis",
                    "purpose": (
                        "Identify the biggest SKU and country "
                        "contributors to the requested "
                        "month-over-month sales change."
                    ),
                }
            ]
        }


    # --------------------------------------------------------
    # ADVERTISING PERFORMANCE / RISK
    # --------------------------------------------------------

    advertising_keywords = [
        "high advertising spend",
        "high ad spend",
        "weak sales",
        "poor ad performance",
        "advertising risk",
        "advertising risks",
        "ad risk",
        "ad risks",
        "low roas",
        "high acos",
        "no ad revenue",
        "inefficient advertising",
        "inefficient ads",
    ]

    if any(
        keyword in q
        for keyword in advertising_keywords
    ):
        return {
            "steps": [
                {
                    "operation": "advertising_risks",
                    "purpose": (
                        "Identify products and periods with "
                        "advertising efficiency risks using "
                        "trusted advertising metrics."
                    ),
                }
            ]
        }


    # --------------------------------------------------------
    # COUNTRY PERFORMANCE
    # --------------------------------------------------------

    if (
        "which country performed best" in q
        or "best country" in q
        or "top country" in q
    ):

        return {
            "steps": [
                {
                    "operation": "country_performance",
                    "purpose": (
                        "Compare country-level sales, units, "
                        "advertising spend, ad revenue, ROAS and TACOS."
                    ),
                },
                {
                    "operation": "dynamic_sql",
                    "purpose": (
                        "Investigate the metrics that explain "
                        "why the strongest country performed better."
                    ),
                },
            ]
        }

    # --------------------------------------------------------
    # SALES CHANGE / DECLINE
    # --------------------------------------------------------

    if (
        "why did sales decline" in q
        or "why did sales decrease" in q
        or "why did sales increase" in q
        or "why did sales change" in q
    ):

        return {
            "steps": [
                {
                    "operation": "trend_analysis",
                    "purpose": (
                        "Analyze monthly sales and supporting "
                        "business metrics around the requested period."
                    ),
                },
                {
                    "operation": "driver_analysis",
                    "purpose": (
                        "Identify the biggest SKU and country "
                        "contributors to the requested "
                        "month-over-month sales change."
                    ),
                },
            ]
        }

    # --------------------------------------------------------
    # SALES TREND
    # --------------------------------------------------------

    if (
        "show me the sales trend" in q
        or "show sales trend" in q
        or "sales trend" in q
        or "sales trends" in q
        or "show the sales trend" in q
    ):
        return {
            "steps": [
                {
                    "operation": "trend_analysis",
                    "purpose": (
                        "Retrieve trusted monthly sales, units, "
                        "advertising, ROAS and TACOS trends "
                        "for the requested period."
                    ),
                }
            ]
        }


    return {}


# ============================================================
# MAIN REASONING PLANNER
# ============================================================

def plan_analysis(
    question: str,
) -> Dict[str, Any]:

    if not isinstance(
        question,
        str,
    ) or not question.strip():

        raise ValueError(
            "Question cannot be empty."
        )

    question = question.strip()

    # --------------------------------------------------------
    # Deterministic reasoning override
    # --------------------------------------------------------

    override = apply_reasoning_overrides(
        question
    )

    if override:

        validated_plan = validate_reasoning_plan(
            override
        )

        return {
            "question": question,
            "steps": validated_plan["steps"],
        }

    # --------------------------------------------------------
    # LLM reasoning fallback
    # --------------------------------------------------------

    prompt = build_reasoning_prompt(
        question
    )

    response = generate_response(
        prompt,
        max_new_tokens=400,
    )

    raw_plan = extract_json(
        response
    )

    validated_plan = validate_reasoning_plan(
        raw_plan
    )

    return {
        "question": question.strip(),
        "steps": validated_plan["steps"],
    }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    test_questions = [

        "Why did sales decline in May 2026?",

        "Which country performed best in 2026 and why?",

        "Which SKUs have high advertising spend but weak sales?",

        "Show me the sales trend for 2026.",
    ]

    print()
    print("=" * 70)
    print("ANALYSIS REASONING PLANNER")
    print("=" * 70)

    for question in test_questions:

        print()
        print("-" * 70)
        print(
            f"QUESTION: {question}"
        )

        try:

            plan = plan_analysis(
                question
            )

            print()
            print(
                json.dumps(
                    plan,
                    indent=2,
                )
            )

        except Exception as error:

            print()
            print(
                "ERROR:",
                error,
            )