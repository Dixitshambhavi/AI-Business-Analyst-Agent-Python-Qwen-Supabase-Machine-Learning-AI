from typing import Any, Dict, List, Optional, Tuple

from src.agent.planner import plan_question
from src.agent.query_executor import execute_plan
from src.agent.result_formatter import format_execution_results
from src.agent.llm import generate_response
from src.agent.response_validator import validate_final_answer


# ============================================================
# VALIDATION RESULT NORMALIZER
# ============================================================

def normalize_validation_result(
    result: Any,
) -> Tuple[bool, List[str]]:
    """
    Normalize validate_final_answer() output.

    Supports:
        (True, [])
        (False, ["error"])
        {"valid": True, "errors": []}
        {"valid": False, "errors": [...]}
        True
        False
    """

    if isinstance(result, dict):
        valid = bool(result.get("valid", False))
        errors = result.get("errors", [])

        if errors is None:
            errors = []

        if not isinstance(errors, list):
            errors = [str(errors)]

        return valid, errors

    if isinstance(result, tuple):
        if len(result) >= 2:
            valid = bool(result[0])
            errors = result[1]

            if errors is None:
                errors = []

            if not isinstance(errors, list):
                errors = [str(errors)]

            return valid, errors

        if len(result) == 1:
            return bool(result[0]), []

    if isinstance(result, bool):
        return result, []

    return False, [
        f"Unexpected validation result type: "
        f"{type(result).__name__}"
    ]


# ============================================================
# GENERIC RECURSIVE SEARCH
# ============================================================

def recursive_collect(
    obj: Any,
) -> List[Dict[str, Any]]:
    """
    Recursively collect dictionaries from nested dict/list/tuple
    structures.

    This protects the agent from small structural differences
    between tool results.
    """

    found: List[Dict[str, Any]] = []

    if isinstance(obj, dict):

        found.append(obj)

        for value in obj.values():
            found.extend(recursive_collect(value))

    elif isinstance(obj, (list, tuple)):

        for item in obj:
            found.extend(recursive_collect(item))

    return found


# ============================================================
# EXTRACT SKU ROWS
# ============================================================

def extract_sku_rows(
    obj: Any,
) -> List[Dict[str, Any]]:
    """
    Find dictionaries containing an SKU field.
    """

    rows: List[Dict[str, Any]] = []

    for item in recursive_collect(obj):

        if "sku" in item:
            rows.append(item)

    return rows


# ============================================================
# EXTRACT TOP-RANKED SKUS
# ============================================================

def extract_top_ranked_skus(
    execution_result: Dict[str, Any],
) -> List[str]:
    """
    Extract SKUs from the first ranking result.

    This is used for questions such as:

        Which of the top 5 selling SKUs have inventory risk?
    """

    steps = execution_result.get("steps", [])

    if not isinstance(steps, list):
        return []

    # Prefer the first executed step because the planner for
    # dependent questions creates:
    #
    # STEP 1 = PRODUCT_RANKING
    # STEP 2 = INVENTORY_RISKS_FOR_SKUS

    for step in steps:

        if not isinstance(step, dict):
            continue

        capability = str(
            step.get("capability", "")
        ).upper()

        if capability not in {
            "PRODUCT_RANKING",
            "TOP_PRODUCTS",
        }:
            continue

        result = step.get("result")

        rows = extract_sku_rows(result)

        if not rows:
            continue

        skus: List[str] = []

        for row in rows:

            sku = row.get("sku")

            if sku is None:
                continue

            sku = str(sku).strip()

            if sku and sku not in skus:
                skus.append(sku)

        if skus:
            return skus

    return []


# ============================================================
# INVENTORY RISK PRIORITY
# ============================================================

RISK_PRIORITY = {
    "CRITICAL": 4,
    "HIGH": 3,
    "MEDIUM": 2,
    "NORMAL": 1,
}


def highest_risk(
    risks: List[str],
) -> str:
    """
    Return the highest risk level from a list of risk labels.
    """

    best = "NORMAL"
    best_score = 0

    for risk in risks:

        normalized = str(risk).strip().upper()

        score = RISK_PRIORITY.get(
            normalized,
            0,
        )

        if score > best_score:
            best_score = score
            best = normalized

    return best


# ============================================================
# EXTRACT INVENTORY ROWS
# ============================================================

def extract_inventory_rows(
    execution_result: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Extract trusted inventory-risk rows from execution output.
    """

    steps = execution_result.get("steps", [])

    if not isinstance(steps, list):
        return []

    inventory_rows: List[Dict[str, Any]] = []

    for step in steps:

        if not isinstance(step, dict):
            continue

        capability = str(
            step.get("capability", "")
        ).upper()

        if capability != "INVENTORY_RISKS_FOR_SKUS":
            continue

        result = step.get("result")

        for row in recursive_collect(result):

            if (
                "sku" in row
                and "risk" in row
            ):
                inventory_rows.append(row)

    return inventory_rows


# ============================================================
# DEDUPLICATE INVENTORY ROWS
# ============================================================

def deduplicate_inventory_rows(
    rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    unique: List[Dict[str, Any]] = []
    seen = set()

    for row in rows:

        sku = str(
            row.get("sku", "")
        ).strip()

        country = str(
            row.get("country", "")
        ).strip()

        risk = str(
            row.get("risk", "")
        ).strip().upper()

        key = (
            sku,
            country,
            risk,
        )

        if key not in seen:

            seen.add(key)
            unique.append(row)

    return unique


# ============================================================
# COMBINE INVENTORY RISKS BY SKU
# ============================================================

def combine_inventory_by_sku(
    rows: List[Dict[str, Any]],
    ranked_skus: List[str],
) -> List[Dict[str, Any]]:
    """
    Convert country-level inventory results into one SKU-level
    result.

    Example:

        CBP9RO50 IN  -> CRITICAL
        CBP9RO50 AE  -> CRITICAL
        CBP9RO50 UK  -> NORMAL

    becomes:

        CBP9RO50 -> CRITICAL

    The highest risk across countries is retained.
    """

    rows = deduplicate_inventory_rows(rows)

    grouped: Dict[str, List[Dict[str, Any]]] = {}

    for row in rows:

        sku = str(
            row.get("sku", "")
        ).strip()

        if not sku:
            continue

        grouped.setdefault(
            sku,
            [],
        ).append(row)

    results: List[Dict[str, Any]] = []

    # Preserve the original product ranking order.
    for sku in ranked_skus:

        sku_rows = grouped.get(
            sku,
            [],
        )

        if not sku_rows:
            continue

        risks = [
            str(row.get("risk", ""))
            for row in sku_rows
        ]

        combined_risk = highest_risk(risks)

        # Pick the row representing the highest risk.
        selected_row = max(
            sku_rows,
            key=lambda row: RISK_PRIORITY.get(
                str(
                    row.get("risk", "")
                ).strip().upper(),
                0,
            ),
        )

        result = dict(selected_row)

        result["risk"] = combined_risk

        results.append(result)

    return results


# ============================================================
# FORMAT INVENTORY ANSWER
# ============================================================

def format_inventory_risk_answer(
    question: str,
    execution_result: Dict[str, Any],
) -> Optional[str]:
    """
    Deterministically answer inventory-risk questions.

    No LLM is used for the actual risk classification.
    """

    question_lower = question.lower()

    if "inventory" not in question_lower:
        return None

    if "risk" not in question_lower:
        return None

    inventory_rows = extract_inventory_rows(
        execution_result
    )

    if not inventory_rows:
        return None

    ranked_skus = extract_top_ranked_skus(
        execution_result
    )

    # If this is a dependent top-products question,
    # restrict to those exact ranked SKUs.
    if ranked_skus:

        inventory_rows = [
            row
            for row in inventory_rows
            if str(
                row.get("sku", "")
            ).strip() in ranked_skus
        ]

        combined_rows = combine_inventory_by_sku(
            inventory_rows,
            ranked_skus,
        )

    else:

        combined_rows = deduplicate_inventory_rows(
            inventory_rows
        )

    if not combined_rows:
        return None

    lines: List[str] = []

    lines.append(
        "Based on the verified inventory analysis:"
    )

    lines.append("")

    for index, row in enumerate(
        combined_rows,
        start=1,
    ):

        sku = row.get(
            "sku",
            "N/A",
        )

        sales = row.get(
            "sales"
        )

        units = row.get(
            "units"
        )

        fba = row.get(
            "fba_inventory",
            row.get("fba_inv"),
        )

        awd = row.get(
            "awd_inventory",
            row.get("awd"),
        )

        risk = str(
            row.get(
                "risk",
                "N/A",
            )
        ).upper()

        lines.append(
            f"{index}. {sku}"
        )

        if sales is not None:

            try:
                lines.append(
                    f"   Sales: "
                    f"${float(sales):,.2f}"
                )

            except (
                TypeError,
                ValueError,
            ):
                lines.append(
                    f"   Sales: {sales}"
                )

        if units is not None:

            try:
                lines.append(
                    f"   Units: "
                    f"{int(float(units)):,}"
                )

            except (
                TypeError,
                ValueError,
            ):
                lines.append(
                    f"   Units: {units}"
                )

        if fba is not None:

            try:
                lines.append(
                    f"   FBA Inventory: "
                    f"{int(float(fba)):,}"
                )

            except (
                TypeError,
                ValueError,
            ):
                lines.append(
                    f"   FBA Inventory: {fba}"
                )

        if awd is not None:

            try:
                lines.append(
                    f"   AWD Inventory: "
                    f"{int(float(awd)):,}"
                )

            except (
                TypeError,
                ValueError,
            ):
                lines.append(
                    f"   AWD Inventory: {awd}"
                )

        lines.append(
            f"   Inventory Risk: {risk}"
        )

        lines.append("")

    return "\n".join(lines).strip()



# ============================================================
# DETERMINISTIC TOP-PRODUCT + INVENTORY ANSWER
# ============================================================

def format_top_products_inventory_answer(
    question: str,
    execution_result: Dict[str, Any],
) -> Optional[str]:
    """
    Deterministically combine PRODUCT_RANKING and
    INVENTORY_RISKS_FOR_SKUS results.

    This avoids truncation or accidental omission when a multi-step
    answer contains several ranked SKU rows.
    """

    question_lower = question.lower()

    if "sku" not in question_lower and "product" not in question_lower:
        return None

    if "inventory" not in question_lower or "risk" not in question_lower:
        return None

    steps = execution_result.get("steps", [])

    if not isinstance(steps, list):
        return None

    ranking_result = None

    for step in steps:
        if not isinstance(step, dict):
            continue

        capability = str(
            step.get("capability", "")
        ).upper().strip()

        if capability in {"PRODUCT_RANKING", "TOP_PRODUCTS"}:
            ranking_result = step.get("result")
            break

    if ranking_result is None:
        return None

    ranking_rows = extract_sku_rows(ranking_result)

    if not ranking_rows:
        return None

    inventory_rows = extract_inventory_rows(execution_result)

    if not inventory_rows:
        return None

    ranked_skus: List[str] = []

    for row in ranking_rows:
        sku = row.get("sku")

        if sku is None:
            continue

        sku = str(sku).strip()

        if sku and sku not in ranked_skus:
            ranked_skus.append(sku)

    if not ranked_skus:
        return None

    inventory_rows = [
        row
        for row in inventory_rows
        if str(row.get("sku", "")).strip() in ranked_skus
    ]

    combined_inventory_rows = combine_inventory_by_sku(
        inventory_rows,
        ranked_skus,
    )

    inventory_by_sku = {
        str(row.get("sku", "")).strip(): row
        for row in combined_inventory_rows
    }

    lines: List[str] = []

    lines.append(
        "The top SKUs by sales and their verified inventory risks are:"
    )
    lines.append("")

    for index, ranking_row in enumerate(
        ranking_rows,
        start=1,
    ):
        sku = str(
            ranking_row.get("sku", "N/A")
        ).strip()

        if not sku:
            continue

        sales = ranking_row.get("sales")
        units = ranking_row.get("units")

        inventory_row = inventory_by_sku.get(sku, {})

        risk = str(
            inventory_row.get("risk", "N/A")
        ).upper()

        lines.append(
            f"{index}. {sku}"
        )

        if sales is not None:
            try:
                lines.append(
                    f"   Sales: ${float(sales):,.2f}"
                )
            except (TypeError, ValueError):
                lines.append(
                    f"   Sales: {sales}"
                )

        if units is not None:
            try:
                lines.append(
                    f"   Units: {int(float(units)):,}"
                )
            except (TypeError, ValueError):
                lines.append(
                    f"   Units: {units}"
                )

        lines.append(
            f"   Inventory Risk: {risk}"
        )

        if inventory_row:
            country = inventory_row.get("country")

            if country not in (None, ""):
                lines.append(
                    f"   Inventory Country: {country}"
                )

            fba = inventory_row.get(
                "fba_inventory",
                inventory_row.get("fba_inv"),
            )

            awd = inventory_row.get(
                "awd_inventory",
                inventory_row.get("awd"),
            )

            if fba is not None:
                try:
                    lines.append(
                        f"   FBA Inventory: {int(float(fba)):,}"
                    )
                except (TypeError, ValueError):
                    lines.append(
                        f"   FBA Inventory: {fba}"
                    )

            if awd is not None:
                try:
                    lines.append(
                        f"   AWD Inventory: {int(float(awd)):,}"
                    )
                except (TypeError, ValueError):
                    lines.append(
                        f"   AWD Inventory: {awd}"
                    )

        lines.append("")

    return "\n".join(lines).strip()

# ============================================================
# GROUNDED LLM ANSWER
# ============================================================

def generate_grounded_answer(
    question: str,
    verified_facts: str,
) -> str:
    """
    Generate a natural-language answer using ONLY verified
    tool output.
    """

    prompt = f"""
You are an AI Business Analyst.

Answer the user's question using ONLY the VERIFIED FACTS below.

STRICT RULES:

1. Never invent numbers.
2. Never invent SKUs.
3. Never invent countries.
4. Never invent dates.
5. Never invent inventory risk classifications.
6. Never infer facts not present in VERIFIED FACTS.
7. Preserve exact numbers.
8. Preserve exact SKU names.
9. Preserve ranking order when reporting rankings.
10. Do not discuss customer loyalty.
11. Do not discuss customer retention.
12. Do not discuss customer behavior unless it exists in the data.
13. Do not discuss margins or profitability unless explicitly
    supported by the data.
14. Do not discuss market penetration unless explicitly supported.
15. Do not add unsupported recommendations.
16. Keep the answer concise and business-focused.
17. Answer only what the user asked.
18. Distinguish correlation/association from causation.
19. Never claim that one metric caused another unless the verified
    facts explicitly establish causation.

USER QUESTION:
{question}

VERIFIED FACTS:
{verified_facts}

Now provide the final answer.
"""

    return generate_response(
        prompt
    )


# ============================================================
# PHASE 2.1 — FINAL ANSWER SYNTHESIZER
# ============================================================

def generate_synthesized_answer(
    question: str,
    verified_facts: str,
) -> str:
    """
    Combine multiple verified analysis steps into one coherent
    business-analyst answer.

    The LLM receives only trusted, already-executed results.
    It must explain how the results fit together without
    inventing facts or causation.
    """

    prompt = f"""
You are the final-answer layer of an AI Business Analyst Agent.

The Python/database layer has already executed the analysis.
The VERIFIED FACTS below are authoritative.

Your job is ONLY to synthesize those verified results into one
clear business answer to the user's question.

USER QUESTION:
{question}

VERIFIED FACTS:
{verified_facts}

============================================================
STRICT GROUNDING RULES
============================================================

1. Use ONLY the VERIFIED FACTS.
2. Never invent numbers, countries, SKUs, dates, metrics, or events.
3. Preserve numerical values from the verified facts.
4. Do not change the meaning of any metric.
5. Do not invent a cause when the data only shows an association.
6. Clearly distinguish observed performance from causal explanation.
7. Do not mention information that is absent from the verified facts.
8. Do not discuss customer behavior, loyalty, retention, market share,
   market penetration, margins, or profitability unless explicitly
   present in the verified facts.
9. Do not add recommendations unless the evidence directly supports one.
10. When multiple analysis steps answer different parts of the question,
    combine them instead of repeating the steps separately.
11. Do not write "Step 1", "Step 2", "Step 3", or internal tool names.
12. Do not reproduce long raw tables unless the user explicitly asked
    for the table.
13. Prefer the most decision-relevant verified metrics.
14. Keep the answer concise and business-focused.

============================================================
ANSWER STRUCTURE
============================================================

Use this structure when appropriate:

Key finding:
State the direct answer first.

Supporting evidence:
Use the most important verified numbers or rankings that support it.

Business interpretation:
Explain what the verified metrics indicate. Do not claim causation
unless causation is explicitly supported.

Recommendation:
Only include this section when a recommendation is directly supported
by the verified facts. Otherwise omit it.

Return ONLY the business answer.
"""

    return generate_response(
        prompt,
        max_new_tokens=450,
    )


# ============================================================
# REGENERATE LLM ANSWER
# ============================================================

def regenerate_grounded_answer(
    question: str,
    verified_facts: str,
    previous_answer: str,
    validation_errors: List[str],
) -> str:

    prompt = f"""
You are correcting an AI Business Analyst answer.

USER QUESTION:
{question}

VERIFIED FACTS:
{verified_facts}

PREVIOUS ANSWER:
{previous_answer}

VALIDATION ERRORS:
{validation_errors}

Generate a corrected answer.

RULES:

1. Use ONLY VERIFIED FACTS.
2. Do not invent information.
3. Preserve exact numbers.
4. Preserve exact SKU names.
5. Preserve ranking order when reporting rankings.
6. Do not invent risk classifications.
7. Do not remove verified information needed to answer the question.
8. Do not add unsupported business claims.
9. Do not claim causation unless explicitly supported.
10. Do not discuss customer behavior unless present in the facts.
11. When multiple analysis results exist, synthesize them into one answer.
12. Do not mention internal tool names or step numbers.
13. Be concise.
14. Return only the corrected business answer.
"""

    return generate_response(
        prompt
    )


# ============================================================
# NORMAL / SYNTHESIZED VALIDATED ANSWER
# ============================================================

def extract_verified_result_section(
    verified_facts: str,
    execution_result: Dict[str, Any],
) -> str:
    """
    Return the verified result text without asking the LLM
    to rewrite structured/tabular data.

    This prevents truncation, number changes, SKU changes,
    and accidental hallucinations for structured outputs.
    """

    if not verified_facts:
        return verified_facts

    lines = verified_facts.splitlines()

    # Find RESULT blocks.
    result_positions = []

    for i, line in enumerate(lines):
        if line.strip().startswith("RESULT "):
            result_positions.append(i)

    if not result_positions:
        return verified_facts.strip()

    # Determine the capabilities that were executed.
    capabilities = []

    for step in execution_result.get("steps", []):
        if isinstance(step, dict):
            capability = str(
                step.get("capability", "")
            ).upper().strip()

            if capability:
                capabilities.append(capability)

    # --------------------------------------------------------
    # Inventory: prefer the last RESULT block because the
    # dependent inventory step follows the product ranking step.
    # --------------------------------------------------------

    if "INVENTORY_RISKS_FOR_SKUS" in capabilities:
        start = result_positions[-1]

        section_lines = lines[start:]

        return "\n".join(section_lines).strip()

    # --------------------------------------------------------
    # Single structured result: return the complete verified
    # result. This is preferable to asking a small local LLM
    # to reproduce a long table.
    # --------------------------------------------------------

    start = result_positions[0]

    section_lines = lines[start:]

    return "\n".join(section_lines).strip()


def _get_executed_capabilities(
    execution_result: Dict[str, Any],
) -> List[str]:
    """
    Return executed capabilities in their original step order.
    Duplicate capabilities are removed.
    """

    capabilities: List[str] = []
    seen = set()

    for step in execution_result.get("steps", []):

        if not isinstance(step, dict):
            continue

        capability = str(
            step.get(
                "capability",
                ""
            )
        ).upper().strip()

        if capability and capability not in seen:
            seen.add(capability)
            capabilities.append(capability)

    return capabilities


def generate_validated_answer(
    question: str,
    execution_result: Dict[str, Any],
    max_attempts: int = 3,
) -> str:

    # ========================================================
    # VERIFIED DATA
    # ========================================================

    verified_facts = format_execution_results(
        execution_result
    )

    print("\n" + "=" * 70)
    print("VERIFIED FACTS")
    print("=" * 70)
    print(verified_facts)
    print("=" * 70)

    # ========================================================
    # CAPABILITY ANALYSIS
    # ========================================================

    structured_capabilities = {
        "EXECUTIVE_KPI",
        "MONTHLY_PERFORMANCE",
        "TOP_PRODUCTS",
        "PRODUCT_RANKING",
        "COUNTRY_PERFORMANCE",
        "COMPARISON_ANALYSIS",
        "TREND_ANALYSIS",
        "ADVERTISING_RISKS",
        "INVENTORY_RISKS",
        "INVENTORY_RISKS_FOR_SKUS",
        "DATA_QUALITY",
        "DRIVER_ANALYSIS",
        "DYNAMIC_SQL",
    }

    executed_capabilities = _get_executed_capabilities(
        execution_result
    )

    executed_capability_set = set(
        executed_capabilities
    )

    # ========================================================
    # DETERMINISTIC DEPENDENT STRUCTURED ANSWER
    # ========================================================
    #
    # PRODUCT_RANKING -> INVENTORY_RISKS_FOR_SKUS is a fully
    # structured trusted-tool workflow. The Python layer already
    # contains every required value, so do not send these rows
    # back through the small local LLM where a long ranked answer
    # can be truncated.
    # ========================================================

    if (
        "PRODUCT_RANKING" in executed_capability_set
        and "INVENTORY_RISKS_FOR_SKUS" in executed_capability_set
    ):
        deterministic_answer = format_top_products_inventory_answer(
            question,
            execution_result,
        )

        if deterministic_answer:
            print(
                "\n✓ Deterministic dependent answer returned "
                "from trusted results."
            )

            return deterministic_answer

    # ========================================================
    # PHASE 2.1 — MULTI-STEP SYNTHESIS
    # ========================================================
    #
    # When more than one trusted analysis step was executed,
    # do NOT simply concatenate raw result blocks.
    #
    # Instead:
    #
    #   Trusted results
    #        ↓
    #   Local Qwen synthesis
    #        ↓
    #   Validator
    #        ↓
    #   Final business answer
    #
    # This keeps structured single-tool outputs unchanged while
    # making multi-step questions read like one analyst response.
    # ========================================================

    if (
        len(executed_capabilities) > 1
        and executed_capability_set.issubset(
            structured_capabilities
        )
    ):

        print(
            "\n✓ Multi-step result detected."
        )

        print(
            "Generating synthesized business answer..."
        )

        answer = generate_synthesized_answer(
            question,
            verified_facts,
        )

        for attempt in range(
            1,
            max_attempts + 1
        ):

            print(
                f"\nSynthesis validation attempt "
                f"{attempt}/{max_attempts}"
            )

            raw_validation = validate_final_answer(
                answer,
                execution_result,
            )

            valid, errors = normalize_validation_result(
                raw_validation
            )

            if valid:

                print(
                    "✓ Synthesized answer validation passed"
                )

                return answer

            print(
                "✗ Synthesized answer validation failed"
            )

            for error in errors:
                print(
                    f"  - {error}"
                )

            if attempt < max_attempts:

                print(
                    "Regenerating synthesized answer..."
                )

                answer = regenerate_grounded_answer(
                    question,
                    verified_facts,
                    answer,
                    errors,
                )

        # ----------------------------------------------------
        # Safe fallback for multi-step answers
        # ----------------------------------------------------

        print(
            "\n⚠ Synthesis validation failed after "
            "maximum attempts."
        )

        print(
            "Returning verified facts instead of "
            "unvalidated synthesized content."
        )

        return verified_facts

    # ========================================================
    # SINGLE STRUCTURED BUSINESS RESULT
    # ========================================================
    #
    # These results are already calculated by trusted Python
    # tools. Do not send them back through Qwen for rewriting.
    #
    # This preserves:
    #   - long tables
    #   - exact numbers
    #   - exact SKU names
    #   - ranking order
    #   - complete rows
    # ========================================================

    if (
        len(executed_capabilities) == 1
        and executed_capability_set.issubset(
            structured_capabilities
        )
    ):

        print(
            "\n✓ Structured answer returned directly "
            "from trusted tool output."
        )

        return extract_verified_result_section(
            verified_facts,
            execution_result,
        )

    # ========================================================
    # NORMAL LLM PATH
    # ========================================================

    answer = generate_grounded_answer(
        question,
        verified_facts,
    )

    for attempt in range(
        1,
        max_attempts + 1
    ):

        print(
            f"\nAnswer validation attempt "
            f"{attempt}/{max_attempts}"
        )

        raw_validation = validate_final_answer(
            answer,
            execution_result,
        )

        valid, errors = normalize_validation_result(
            raw_validation
        )

        if valid:

            print(
                "✓ Final answer validation passed"
            )

            return answer

        print(
            "✗ Final answer validation failed"
        )

        for error in errors:
            print(
                f"  - {error}"
            )

        if attempt < max_attempts:

            print(
                "Regenerating answer..."
            )

            answer = regenerate_grounded_answer(
                question,
                verified_facts,
                answer,
                errors,
            )

    # ========================================================
    # SAFE FALLBACK
    # ========================================================

    print(
        "\n⚠ Validation failed after maximum attempts."
    )

    print(
        "Returning verified facts instead of "
        "unvalidated generated content."
    )

    return verified_facts


# ============================================================
# MAIN QUESTION PIPELINE
# ============================================================

def answer_question(
    question: str,
) -> str:

    print("\n" + "=" * 70)
    print("USER QUESTION")
    print("=" * 70)
    print(question)

    # --------------------------------------------------------
    # STEP 1: PLAN
    # --------------------------------------------------------

    print("\nPlanning...")

    plan = plan_question(
        question
    )

    print("\nPLAN")
    print(plan)

    # --------------------------------------------------------
    # STEP 2: EXECUTE TRUSTED TOOLS
    # --------------------------------------------------------

    print("\nExecuting trusted tools...")

    execution_result = execute_plan(
        plan
    )

    print("\nEXECUTION COMPLETE")

    # --------------------------------------------------------
    # STEP 3: GENERATE VERIFIED ANSWER
    # --------------------------------------------------------

    answer = generate_validated_answer(
        question,
        execution_result,
    )

    # --------------------------------------------------------
    # STEP 4: DISPLAY
    # --------------------------------------------------------

    print("\n" + "=" * 70)
    print("AI BUSINESS ANSWER")
    print("=" * 70)

    print(answer)

    print("=" * 70)

    return answer


# ============================================================
# INTERACTIVE MODE
# ============================================================

if __name__ == "__main__":

    print("=" * 70)
    print("AI BUSINESS ANALYST AGENT")
    print("=" * 70)

    print(
        "Type your business question."
    )

    print(
        "Type 'exit' to quit."
    )

    print()

    while True:

        question = input(
            "You: "
        ).strip()

        if not question:
            continue

        if question.lower() in {
            "exit",
            "quit",
        }:

            print(
                "Goodbye."
            )

            break

        try:

            answer_question(
                question
            )

        except Exception as exc:

            print("\nERROR:")
            print(
                type(exc).__name__,
                str(exc),
            )

            
# # # ============================================================
# # # ENTRY POINT
# # # ============================================================

# # if __name__ == "__main__":
# #     main()
# import json
# from typing import Any

# from src.agent.llm import generate_response
# from src.agent.planner import plan_question
# from src.agent.query_executor import execute_plan
# from src.agent.response_validator import validate_final_answer


# # ============================================================
# # FINAL ANSWER PROMPT
# # ============================================================

# def build_answer_prompt(
#     question: str,
#     execution_result: dict[str, Any]
# ) -> str:
#     """
#     Build a strict grounding prompt for the local LLM.
#     """

#     results_text = json.dumps(
#         execution_result,
#         indent=2,
#         default=str
#     )

#     return f"""
# You are a highly reliable AI Business Analyst.

# The model is running LOCALLY.

# USER QUESTION:
# {question}

# AUTHORITATIVE EXECUTION RESULTS:
# {results_text}

# ============================================================
# STRICT RULES
# ============================================================

# 1. The execution results are the ONLY source of business facts.
# 2. Never invent numbers.
# 3. Never invent SKUs.
# 4. Never invent countries.
# 5. Never invent months.
# 6. Never invent inventory classifications.
# 7. Never invent ROAS, ACOS or TACOS.
# 8. Never invent customer behavior.
# 9. Never invent margins or profitability.
# 10. Never claim causation unless the data directly supports it.
# 11. Never add facts that are not present in the execution results.
# 12. Preserve numerical values exactly.
# 13. Do not change the meaning of any metric.
# 14. Answer exactly what the user asked.
# 15. If the available results do not contain enough information,
#     explicitly say so.
# 16. Recommendations must be based only on returned evidence.

# ============================================================
# IMPORTANT
# ============================================================

# The Python/database execution layer is the source of truth.

# You are responsible only for explaining the verified results.

# ============================================================
# OUTPUT
# ============================================================

# Provide:

# Key findings:
# - The most relevant verified findings.

# Business interpretation:
# - Explain what the returned data means.

# Recommendation:
# - Provide only evidence-based recommendations.
# """


# # ============================================================
# # GENERATE ANSWER
# # ============================================================

# def generate_answer(
#     question: str,
#     execution_result: dict[str, Any]
# ) -> str:

#     prompt = build_answer_prompt(
#         question,
#         execution_result
#     )

#     return generate_response(
#         prompt,
#         max_new_tokens=450
#     )


# # ============================================================
# # REPAIR / REGENERATE ANSWER
# # ============================================================

# def regenerate_answer(
#     question: str,
#     execution_result: dict[str, Any],
#     validation_errors: list[str]
# ) -> str:
#     """
#     Ask the local LLM to regenerate its answer after the
#     validator detects unsupported content.
#     """

#     results_text = json.dumps(
#         execution_result,
#         indent=2,
#         default=str
#     )

#     errors_text = "\n".join(
#         f"- {error}"
#         for error in validation_errors
#     )

#     prompt = f"""
# You are a strict AI Business Analyst.

# USER QUESTION:
# {question}

# AUTHORITATIVE DATA:
# {results_text}

# YOUR PREVIOUS ANSWER FAILED VALIDATION.

# VALIDATION ERRORS:
# {errors_text}

# You must regenerate the answer.

# RULES:

# 1. Use ONLY the authoritative data above.
# 2. Do not invent any number.
# 3. Do not invent any SKU.
# 4. Do not invent any country.
# 5. Do not invent any month.
# 6. Do not invent any business metric.
# 7. Do not mention unsupported concepts such as:
#    - customer loyalty
#    - customer engagement
#    - market penetration
#    - market share
#    - profit margin
#    - gross margin
#    - high-margin products
#    unless explicitly present in the data.
# 8. Preserve exact numeric values.
# 9. Answer exactly the user's question.
# 10. If information is unavailable, explicitly say so.
# 11. Keep the response concise.

# Return only the corrected business answer.
# """

#     return generate_response(
#         prompt,
#         max_new_tokens=450
#     )


# # ============================================================
# # VALIDATED ANSWER PIPELINE
# # ============================================================

# def generate_validated_answer(
#     question: str,
#     execution_result: dict[str, Any],
#     max_retries: int = 2
# ) -> str:
#     """
#     Generate an answer and validate it.

#     If validation fails, regenerate the answer.
#     """

#     answer = generate_answer(
#         question,
#         execution_result
#     )

#     for attempt in range(
#         max_retries + 1
#     ):

#         valid, errors = validate_final_answer(
#             answer,
#             execution_result
#         )

#         print()
#         print(
#             f"Answer validation attempt "
#             f"{attempt + 1}/{max_retries + 1}"
#         )

#         if valid:

#             print(
#                 "✓ Final answer validation passed"
#             )

#             return answer

#         print(
#             "✗ Final answer validation failed"
#         )

#         for error in errors:

#             print(
#                 f"  - {error}"
#             )

#         if attempt >= max_retries:

#             raise ValueError(
#                 "Unable to generate a validated answer "
#                 f"after {max_retries + 1} attempts.\n"
#                 + "\n".join(errors)
#             )

#         print(
#             "Regenerating answer..."
#         )

#         answer = regenerate_answer(
#             question,
#             execution_result,
#             errors
#         )

#     raise RuntimeError(
#         "Unexpected answer-validation state."
#     )


# # ============================================================
# # COMPLETE MULTI-STEP AGENT
# # ============================================================

# def answer_question(
#     question: str
# ) -> str:
#     """
#     Complete AI Business Analyst workflow:

#     User
#       ↓
#     Local Qwen planner
#       ↓
#     Structured plan
#       ↓
#     Python execution
#       ↓
#     Trusted tools
#       ↓
#     Supabase
#       ↓
#     Verified results
#       ↓
#     Local Qwen explanation
#       ↓
#     Validator
#       ↓
#     Final answer
#     """

#     if not question or not question.strip():

#         raise ValueError(
#             "Question cannot be empty."
#         )

#     question = question.strip()

#     print()
#     print("=" * 70)
#     print("AI BUSINESS ANALYST")
#     print("=" * 70)

#     # ========================================================
#     # STEP 1 — PLANNING
#     # ========================================================

#     print()
#     print("Step 1: Planning question...")

#     plan = plan_question(
#         question
#     )

#     print()
#     print("Generated plan:")

#     print(
#         json.dumps(
#             plan,
#             indent=2
#         )
#     )

#     # ========================================================
#     # STEP 2 — EXECUTE
#     # ========================================================

#     print()
#     print("Step 2: Executing trusted tools...")

#     execution_result = execute_plan(
#         plan
#     )

#     print()
#     print("✓ Tool execution completed")

#     # ========================================================
#     # STEP 3 — ANSWER + VALIDATION
#     # ========================================================

#     print()
#     print("Step 3: Generating validated answer...")

#     answer = generate_validated_answer(
#         question,
#         execution_result
#     )

#     return answer


# # ============================================================
# # INTERACTIVE MAIN
# # ============================================================

# def main():

#     print()
#     print("=" * 70)
#     print("AI BUSINESS ANALYST AGENT")
#     print("Local Hugging Face Qwen + Supabase")
#     print("=" * 70)

#     print()
#     print("Ask any business question supported by the data.")
#     print("Type 'exit' to stop.")

#     while True:

#         print()

#         question = input(
#             "Ask a business question: "
#         ).strip()

#         if question.lower() in {
#             "exit",
#             "quit",
#             "q"
#         }:

#             print()
#             print("Agent stopped.")

#             break

#         if not question:

#             print(
#                 "Please enter a question."
#             )

#             continue

#         try:

#             answer = answer_question(
#                 question
#             )

#             print()
#             print("=" * 70)
#             print("AI BUSINESS ANSWER")
#             print("=" * 70)
#             print(answer)
#             print()

#         except Exception as error:

#             print()
#             print("=" * 70)
#             print("ERROR")
#             print("=" * 70)
#             print(error)
#             print()


# # ============================================================
# # ENTRY POINT
# # ============================================================

# if __name__ == "__main__":
#     main()
            
# # # ============================================================
# # # ENTRY POINT
# # # ============================================================

# # if __name__ == "__main__":
# #     main()
# import json
# from typing import Any

# from src.agent.llm import generate_response
# from src.agent.planner import plan_question
# from src.agent.query_executor import execute_plan
# from src.agent.response_validator import validate_final_answer


# # ============================================================
# # FINAL ANSWER PROMPT
# # ============================================================

# def build_answer_prompt(
#     question: str,
#     execution_result: dict[str, Any]
# ) -> str:
#     """
#     Build a strict grounding prompt for the local LLM.
#     """

#     results_text = json.dumps(
#         execution_result,
#         indent=2,
#         default=str
#     )

#     return f"""
# You are a highly reliable AI Business Analyst.

# The model is running LOCALLY.

# USER QUESTION:
# {question}

# AUTHORITATIVE EXECUTION RESULTS:
# {results_text}

# ============================================================
# STRICT RULES
# ============================================================

# 1. The execution results are the ONLY source of business facts.
# 2. Never invent numbers.
# 3. Never invent SKUs.
# 4. Never invent countries.
# 5. Never invent months.
# 6. Never invent inventory classifications.
# 7. Never invent ROAS, ACOS or TACOS.
# 8. Never invent customer behavior.
# 9. Never invent margins or profitability.
# 10. Never claim causation unless the data directly supports it.
# 11. Never add facts that are not present in the execution results.
# 12. Preserve numerical values exactly.
# 13. Do not change the meaning of any metric.
# 14. Answer exactly what the user asked.
# 15. If the available results do not contain enough information,
#     explicitly say so.
# 16. Recommendations must be based only on returned evidence.

# ============================================================
# IMPORTANT
# ============================================================

# The Python/database execution layer is the source of truth.

# You are responsible only for explaining the verified results.

# ============================================================
# OUTPUT
# ============================================================

# Provide:

# Key findings:
# - The most relevant verified findings.

# Business interpretation:
# - Explain what the returned data means.

# Recommendation:
# - Provide only evidence-based recommendations.
# """


# # ============================================================
# # GENERATE ANSWER
# # ============================================================

# def generate_answer(
#     question: str,
#     execution_result: dict[str, Any]
# ) -> str:

#     prompt = build_answer_prompt(
#         question,
#         execution_result
#     )

#     return generate_response(
#         prompt,
#         max_new_tokens=450
#     )


# # ============================================================
# # REPAIR / REGENERATE ANSWER
# # ============================================================

# def regenerate_answer(
#     question: str,
#     execution_result: dict[str, Any],
#     validation_errors: list[str]
# ) -> str:
#     """
#     Ask the local LLM to regenerate its answer after the
#     validator detects unsupported content.
#     """

#     results_text = json.dumps(
#         execution_result,
#         indent=2,
#         default=str
#     )

#     errors_text = "\n".join(
#         f"- {error}"
#         for error in validation_errors
#     )

#     prompt = f"""
# You are a strict AI Business Analyst.

# USER QUESTION:
# {question}

# AUTHORITATIVE DATA:
# {results_text}

# YOUR PREVIOUS ANSWER FAILED VALIDATION.

# VALIDATION ERRORS:
# {errors_text}

# You must regenerate the answer.

# RULES:

# 1. Use ONLY the authoritative data above.
# 2. Do not invent any number.
# 3. Do not invent any SKU.
# 4. Do not invent any country.
# 5. Do not invent any month.
# 6. Do not invent any business metric.
# 7. Do not mention unsupported concepts such as:
#    - customer loyalty
#    - customer engagement
#    - market penetration
#    - market share
#    - profit margin
#    - gross margin
#    - high-margin products
#    unless explicitly present in the data.
# 8. Preserve exact numeric values.
# 9. Answer exactly the user's question.
# 10. If information is unavailable, explicitly say so.
# 11. Keep the response concise.

# Return only the corrected business answer.
# """

#     return generate_response(
#         prompt,
#         max_new_tokens=450
#     )


# # ============================================================
# # VALIDATED ANSWER PIPELINE
# # ============================================================

# def generate_validated_answer(
#     question: str,
#     execution_result: dict[str, Any],
#     max_retries: int = 2
# ) -> str:
#     """
#     Generate an answer and validate it.

#     If validation fails, regenerate the answer.
#     """

#     answer = generate_answer(
#         question,
#         execution_result
#     )

#     for attempt in range(
#         max_retries + 1
#     ):

#         valid, errors = validate_final_answer(
#             answer,
#             execution_result
#         )

#         print()
#         print(
#             f"Answer validation attempt "
#             f"{attempt + 1}/{max_retries + 1}"
#         )

#         if valid:

#             print(
#                 "✓ Final answer validation passed"
#             )

#             return answer

#         print(
#             "✗ Final answer validation failed"
#         )

#         for error in errors:

#             print(
#                 f"  - {error}"
#             )

#         if attempt >= max_retries:

#             raise ValueError(
#                 "Unable to generate a validated answer "
#                 f"after {max_retries + 1} attempts.\n"
#                 + "\n".join(errors)
#             )

#         print(
#             "Regenerating answer..."
#         )

#         answer = regenerate_answer(
#             question,
#             execution_result,
#             errors
#         )

#     raise RuntimeError(
#         "Unexpected answer-validation state."
#     )


# # ============================================================
# # COMPLETE MULTI-STEP AGENT
# # ============================================================

# def answer_question(
#     question: str
# ) -> str:
#     """
#     Complete AI Business Analyst workflow:

#     User
#       ↓
#     Local Qwen planner
#       ↓
#     Structured plan
#       ↓
#     Python execution
#       ↓
#     Trusted tools
#       ↓
#     Supabase
#       ↓
#     Verified results
#       ↓
#     Local Qwen explanation
#       ↓
#     Validator
#       ↓
#     Final answer
#     """

#     if not question or not question.strip():

#         raise ValueError(
#             "Question cannot be empty."
#         )

#     question = question.strip()

#     print()
#     print("=" * 70)
#     print("AI BUSINESS ANALYST")
#     print("=" * 70)

#     # ========================================================
#     # STEP 1 — PLANNING
#     # ========================================================

#     print()
#     print("Step 1: Planning question...")

#     plan = plan_question(
#         question
#     )

#     print()
#     print("Generated plan:")

#     print(
#         json.dumps(
#             plan,
#             indent=2
#         )
#     )

#     # ========================================================
#     # STEP 2 — EXECUTE
#     # ========================================================

#     print()
#     print("Step 2: Executing trusted tools...")

#     execution_result = execute_plan(
#         plan
#     )

#     print()
#     print("✓ Tool execution completed")

#     # ========================================================
#     # STEP 3 — ANSWER + VALIDATION
#     # ========================================================

#     print()
#     print("Step 3: Generating validated answer...")

#     answer = generate_validated_answer(
#         question,
#         execution_result
#     )

#     return answer


# # ============================================================
# # INTERACTIVE MAIN
# # ============================================================

# def main():

#     print()
#     print("=" * 70)
#     print("AI BUSINESS ANALYST AGENT")
#     print("Local Hugging Face Qwen + Supabase")
#     print("=" * 70)

#     print()
#     print("Ask any business question supported by the data.")
#     print("Type 'exit' to stop.")

#     while True:

#         print()

#         question = input(
#             "Ask a business question: "
#         ).strip()

#         if question.lower() in {
#             "exit",
#             "quit",
#             "q"
#         }:

#             print()
#             print("Agent stopped.")

#             break

#         if not question:

#             print(
#                 "Please enter a question."
#             )

#             continue

#         try:

#             answer = answer_question(
#                 question
#             )

#             print()
#             print("=" * 70)
#             print("AI BUSINESS ANSWER")
#             print("=" * 70)
#             print(answer)
#             print()

#         except Exception as error:

#             print()
#             print("=" * 70)
#             print("ERROR")
#             print("=" * 70)
#             print(error)
#             print()


# # ============================================================
# # ENTRY POINT
# # ============================================================

# if __name__ == "__main__":
#     main()