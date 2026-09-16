from __future__ import annotations

from typing import Any, Dict, List

from src.agent.analysis_reasoner import plan_analysis
from src.agent.parameter_extractor import extract_parameters

from src.agent.tools import (
    get_monthly_analysis,
    get_country_analysis,
    get_product_ranking,
    get_trend_analysis,
    get_comparison_analysis,
    get_advertising_analysis,
    get_inventory_analysis,
    get_quality_analysis,
)

from src.agent.sql_agent import answer_dynamic_question


# ============================================================
# TRUSTED OPERATION REGISTRY
# ============================================================

OPERATION_REGISTRY = {

    "monthly_performance":
        get_monthly_analysis,

    "country_performance":
        get_country_analysis,

    "product_ranking":
        get_product_ranking,

    "trend_analysis":
        get_trend_analysis,

    "comparison_analysis":
        get_comparison_analysis,

    "advertising_risks":
        get_advertising_analysis,

    "inventory_risks":
        get_inventory_analysis,

    "data_quality":
        get_quality_analysis,
}


# ============================================================
# EXTRACT PARAMETERS FROM ORIGINAL QUESTION
# ============================================================

def get_question_parameters(
    question: str,
) -> Dict[str, Any]:

    try:
        params = extract_parameters(
            question
        )
    except Exception:
        params = {}

    if not isinstance(
        params,
        dict,
    ):
        params = {}

    return params


# ============================================================
# BUILD PARAMETERS FOR TRUSTED OPERATION
# ============================================================

def build_operation_parameters(
    operation: str,
    question_parameters: Dict[str, Any],
) -> Dict[str, Any]:

    operation = operation.lower().strip()

    country = question_parameters.get(
        "country"
    )

    year = question_parameters.get(
        "year"
    )

    month = question_parameters.get(
        "month"
    )

    limit = question_parameters.get(
        "limit"
    )

    # --------------------------------------------------------
    # TREND
    # --------------------------------------------------------

    if operation == "trend_analysis":

        parameters = {}

        if country:
            parameters["country"] = country

        if year is not None:
            parameters["year"] = year

        return parameters

    # --------------------------------------------------------
    # PRODUCT RANKING
    # --------------------------------------------------------

    if operation == "product_ranking":

        parameters = {
            "limit": limit or 10
        }

        if country:
            parameters["country"] = country

        if year is not None:
            parameters["year"] = year

        if month:
            parameters["month"] = month

        return parameters

    # --------------------------------------------------------
    # TOP-LEVEL COUNTRY PERFORMANCE
    # --------------------------------------------------------

    if operation == "country_performance":

        return {}

    # --------------------------------------------------------
    # MONTHLY PERFORMANCE
    # --------------------------------------------------------

    if operation == "monthly_performance":

        return {}

    # --------------------------------------------------------
    # ADVERTISING RISKS
    # --------------------------------------------------------

    if operation == "advertising_risks":

        return {
            "limit": limit or 20
        }

    # --------------------------------------------------------
    # INVENTORY RISKS
    # --------------------------------------------------------

    if operation == "inventory_risks":

        return {
            "limit": limit or 20
        }

    # --------------------------------------------------------
    # DATA QUALITY
    # --------------------------------------------------------

    if operation == "data_quality":

        return {}

    # --------------------------------------------------------
    # COMPARISON
    # --------------------------------------------------------

    if operation == "comparison_analysis":

        return {
            "country1": question_parameters.get(
                "country1"
            ),
            "country2": question_parameters.get(
                "country2"
            ),
            "year": year,
            "month": month,
        }

    return {}


# ============================================================
# BUILD CONTEXT FOR DYNAMIC SQL
# ============================================================

def build_dynamic_sql_context(
    previous_results: List[Dict[str, Any]],
) -> str:

    if not previous_results:
        return ""

    context_parts = []

    for index, result in enumerate(
        previous_results,
        start=1,
    ):

        formatted = result.get(
            "formatted",
            "",
        )

        if formatted:

            context_parts.append(
                f"ANALYSIS STEP {index}\n"
                f"{formatted}"
            )

    return "\n\n".join(
        context_parts
    )


# ============================================================
# EXECUTE TRUSTED OPERATION
# ============================================================

def execute_trusted_operation(
    operation: str,
    parameters: Dict[str, Any],
) -> Dict[str, Any]:

    operation = operation.lower().strip()

    if operation not in OPERATION_REGISTRY:

        raise ValueError(
            f"Unsupported trusted operation: {operation}"
        )

    tool = OPERATION_REGISTRY[
        operation
    ]

    return tool(
        **parameters
    )


# ============================================================
# EXECUTE ANALYSIS PLAN
# ============================================================

def execute_analysis_plan(
    question: str,
    plan: Dict[str, Any],
) -> Dict[str, Any]:

    if not isinstance(
        plan,
        dict,
    ):

        raise ValueError(
            "Analysis plan must be a dictionary."
        )

    steps = plan.get(
        "steps"
    )

    if not isinstance(
        steps,
        list,
    ):

        raise ValueError(
            "Analysis plan must contain a steps list."
        )

    if not steps:

        raise ValueError(
            "Analysis plan contains no steps."
        )

    if len(steps) > 4:

        raise ValueError(
            "Maximum of 4 analysis steps allowed."
        )

    # --------------------------------------------------------
    # Extract original question parameters once
    # --------------------------------------------------------

    question_parameters = (
        get_question_parameters(
            question
        )
    )

    executed_steps: List[
        Dict[str, Any]
    ] = []

    # ========================================================
    # EXECUTE STEPS SEQUENTIALLY
    # ========================================================

    for index, step in enumerate(
        steps,
        start=1,
    ):

        if not isinstance(
            step,
            dict,
        ):

            raise ValueError(
                f"Analysis step {index} must be a dictionary."
            )

        operation = str(
            step.get(
                "operation",
                "",
            )
        ).strip().lower()

        purpose = str(
            step.get(
                "purpose",
                "",
            )
        ).strip()

        print()
        print("=" * 70)

        print(
            f"ANALYSIS STEP {index}: "
            f"{operation}"
        )

        print(
            "=" * 70
        )

        print(
            f"Purpose: {purpose}"
        )

        # ----------------------------------------------------
        # DYNAMIC SQL
        # ----------------------------------------------------

        if operation == "dynamic_sql":

            previous_context = (
                build_dynamic_sql_context(
                    executed_steps
                )
            )

            if previous_context:

                enhanced_question = f"""
Original business question:

{question}

Original extracted parameters:

{question_parameters}

Previous verified analysis:

{previous_context}

Use the previous verified analysis as evidence.

Now perform the additional SQL analysis required to
answer the original business question.

Do not contradict the verified results.
Do not invent data.
"""

            else:

                enhanced_question = question

            result_text = (
                answer_dynamic_question(
                    enhanced_question
                )
            )

            executed_steps.append(
                {
                    "step": index,
                    "operation": operation,
                    "purpose": purpose,
                    "formatted": result_text,
                    "raw_result": {
                        "answer": result_text
                    },
                }
            )

            continue

        # ----------------------------------------------------
        # TRUSTED OPERATION
        # ----------------------------------------------------

        parameters = build_operation_parameters(
            operation,
            question_parameters,
        )

        print(
            f"Parameters: {parameters}"
        )

        result = execute_trusted_operation(
            operation,
            parameters,
        )

        # ----------------------------------------------------
        # Format trusted result
        # ----------------------------------------------------

        if not isinstance(
            result,
            dict,
        ):

            raise ValueError(
                f"Tool returned invalid result for {operation}."
            )

        # Import formatter here to preserve existing architecture
        from src.agent.result_formatter import (
            format_tool_result,
        )

        formatted = format_tool_result(
            result
        )

        print()
        print(
            "Verified result:"
        )

        print(
            formatted
        )

        executed_steps.append(
            {
                "step": index,
                "operation": operation,
                "purpose": purpose,
                "parameters": parameters,
                "formatted": formatted,
                "raw_result": result,
            }
        )

    # ========================================================
    # FINAL EXECUTION RESULT
    # ========================================================

    return {
        "question": question,
        "question_parameters": question_parameters,
        "plan": plan,
        "steps": executed_steps,
    }


# ============================================================
# RUN ANALYSIS
# ============================================================

def run_analysis(
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

    print()
    print("=" * 70)
    print(
        "MULTI-STEP BUSINESS ANALYSIS"
    )
    print("=" * 70)

    print()
    print("Question:")

    print(
        question
    )

    # --------------------------------------------------------
    # STEP 1 — REASONING PLAN
    # --------------------------------------------------------

    print()
    print(
        "Creating reasoning plan..."
    )

    plan = plan_analysis(
        question
    )

    print()
    print(
        "REASONING PLAN:"
    )

    for index, step in enumerate(
        plan["steps"],
        start=1,
    ):

        print(
            f"{index}. "
            f"{step['operation']} "
            f"→ "
            f"{step['purpose']}"
        )

    # --------------------------------------------------------
    # STEP 2 — EXECUTE PLAN
    # --------------------------------------------------------

    return execute_analysis_plan(
        question=question,
        plan=plan,
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    test_questions = [

        "Which country performed best in 2026 and why?",

        "Why did sales decline in May 2026?",

    ]

    for question in test_questions:

        try:

            result = run_analysis(
                question
            )

            print()
            print("=" * 70)
            print(
                "ANALYSIS COMPLETED"
            )
            print("=" * 70)

            for step in result["steps"]:

                print()
                print(
                    f"STEP {step['step']}: "
                    f"{step['operation']}"
                )

                print(
                    step["formatted"]
                )

        except Exception as error:

            print()
            print("=" * 70)
            print(
                "ANALYSIS ERROR"
            )
            print("=" * 70)

            print(
                type(error).__name__,
                str(error),
            )