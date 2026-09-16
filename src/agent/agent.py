import json
from typing import Any

from src.agent.llm import generate_response
from src.agent.tools import execute_tool


# ============================================================
# TOOL DESCRIPTIONS
# ============================================================

TOOL_DESCRIPTIONS = {
    "executive_analysis": (
        "Overall business performance including sales, units, "
        "ad spend, ad revenue, ROAS and TACOS."
    ),
    "monthly_performance": (
        "Monthly business performance and trends."
    ),
    "top_products": (
        "Top products/SKUs ranked by sales."
    ),
    "advertising_risks": (
        "Products or campaigns with advertising efficiency risks."
    ),
    "inventory_risks": (
        "Products with inventory risk."
    ),
    "country_performance": (
        "Business performance by country."
    ),
    "data_quality": (
        "Data quality and anomaly summary."
    ),
}


# ============================================================
# SIMPLE TOOL ROUTER
# ============================================================

def choose_tool(question: str) -> str:

    q = question.lower()

    if any(word in q for word in [
        "overall",
        "business performance",
        "total sales",
        "total revenue",
        "how is the business",
        "tacos",
        "overall performance",
    ]):
        return "executive_analysis"

    if any(word in q for word in [
        "month",
        "monthly",
        "growth",
        "trend",
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
    ]):
        return "monthly_performance"

    if any(word in q for word in [
        "top product",
        "top products",
        "best product",
        "best products",
        "highest sales",
        "sku",
    ]):
        return "top_products"

    if any(word in q for word in [
        "advertising",
        "ad spend",
        "ad spend waste",
        "waste",
        "acos",
        "roas",
        "ads",
    ]):
        return "advertising_risks"

    if any(word in q for word in [
        "inventory",
        "stock",
        "out of stock",
        "inventory risk",
    ]):
        return "inventory_risks"

    if any(word in q for word in [
        "country",
        "countries",
        "region",
        "market",
    ]):
        return "country_performance"

    if any(word in q for word in [
        "data quality",
        "quality",
        "anomaly",
        "anomalies",
        "data issue",
    ]):
        return "data_quality"

    # Default
    return "executive_analysis"


# ============================================================
# TOOL EXECUTION
# ============================================================

def run_business_tool(
    tool_name: str,
    question: str
) -> Any:

    if tool_name == "top_products":
        return execute_tool(
            tool_name,
            limit=10
        )

    if tool_name == "advertising_risks":
        return execute_tool(
            tool_name,
            limit=20
        )

    if tool_name == "inventory_risks":
        return execute_tool(
            tool_name,
            limit=20
        )

    return execute_tool(tool_name)


# ============================================================
# ANSWER GENERATOR
# ============================================================

def answer_business_question(question: str) -> str:

    # --------------------------------------------
    # 1. Select tool
    # --------------------------------------------

    tool_name = choose_tool(question)

    print()
    print(f"Selected tool: {tool_name}")

    # --------------------------------------------
    # 2. Execute tool
    # --------------------------------------------

    result = run_business_tool(
        tool_name,
        question
    )

    # --------------------------------------------
    # 3. Convert result to JSON
    # --------------------------------------------

    result_text = json.dumps(
        result,
        indent=2,
        default=str
    )

    # --------------------------------------------
    # 4. Build prompt for local LLM
    # --------------------------------------------

    prompt = f"""
You are an AI Business Analyst.

The user asked:

{question}

You selected the business tool:

{tool_name}

The tool returned the following real business data:

{result_text}

Instructions:

1. Answer the user's question using ONLY the supplied tool result.
2. Do not invent numbers.
3. Clearly state important metrics.
4. Give a useful business interpretation.
5. Separate observed facts from recommendations.
6. If the data has anomalies or quality concerns, mention them when relevant.
7. Keep the answer professional and concise.
8. Use the actual SKU, country, month and metric values returned by the tool.
"""

    # --------------------------------------------
    # 5. Ask local Hugging Face model
    # --------------------------------------------

    response = generate_response(
        prompt,
        max_new_tokens=300
    )

    return response


# ============================================================
# INTERACTIVE AGENT
# ============================================================

def main():

    print("=" * 70)
    print("AI BUSINESS ANALYST AGENT")
    print("Local Hugging Face LLM")
    print("=" * 70)

    print()
    print("Ask questions about the business.")
    print("Type 'exit' to stop.")
    print()

    while True:

        question = input("You: ").strip()

        if not question:
            continue

        if question.lower() in {
            "exit",
            "quit",
            "q"
        }:
            print()
            print("Agent stopped.")
            break

        try:

            answer = answer_business_question(
                question
            )

            print()
            print("AI:")
            print(answer)
            print()

        except Exception as error:

            print()
            print("ERROR:")
            print(error)
            print()


if __name__ == "__main__":
    main()