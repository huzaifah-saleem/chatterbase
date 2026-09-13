"""Agent orchestrator: decomposes a request into steps, dispatches each to a
sub-agent, and persists results as generic UI blocks via plan_store.py.

First slice - exactly two agent_types, both of which wrap capabilities
Chatterbase already has rather than rebuilding them:
  - "data": wraps chat_handler.process_chat_request() (the existing MCP
    tool-calling loop) and adapts its output into blocks.
  - "dashboard": asks the LLM for a chart spec and pins it via
    dashboard_store.pin_chart() (the existing pin-a-chart capability).

Deliberately NOT built on a graph-execution framework (LangGraph etc.) yet -
this proves the plan/approve/execute shape with plain functions + JSON
files first; the API surface (plan/approve/reject) is what would stay
stable if the engine underneath is swapped out later.
"""
import json
import re

import plan_store
import dashboard_store
from chat_handler import process_chat_request
from llm_providers import LLMProvider
from prompts import get_planning_prompt, get_chart_spec_prompt

VALID_AGENT_TYPES = ("data", "dashboard")


def _extract_json(raw):
    """Models are told not to wrap JSON in a markdown fence, but often do
    anyway - try direct parsing first, then fall back to pulling the first
    fenced block out, before giving up with a clear error."""
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Model response was not valid JSON: {raw[:300]}")


def plan_request(user_request):
    """Call the planning LLM and return normalized steps (not yet persisted -
    the caller persists via plan_store.create_plan)."""
    raw = LLMProvider.call(get_planning_prompt(), user_request)
    parsed = _extract_json(raw)
    if not isinstance(parsed, list) or not parsed:
        raise ValueError(f"Planner did not return a non-empty step list: {raw[:300]}")

    steps = []
    for i, item in enumerate(parsed[:5]):  # hard cap, mirrors the "1 to 5 steps" prompt rule
        agent_type = item.get("agent_type")
        if agent_type not in VALID_AGENT_TYPES:
            agent_type = "data"
        description = item.get("description", "").strip()
        if not description:
            continue
        steps.append({"id": f"step-{i+1}", "description": description, "agent_type": agent_type})

    if not steps:
        raise ValueError(f"Planner returned no usable steps: {raw[:300]}")
    return steps


def _table_block_from_mcp_result(mcp_result):
    """Best-effort: if a tool's raw result content is JSON shaped like a list
    of row-objects, render it as a table block too, alongside the LLM's own
    prose summary. Silently skipped if the content isn't shaped that way -
    the text block still carries the answer either way."""
    if not mcp_result or not mcp_result.get("content"):
        return None
    for text in mcp_result["content"]:
        try:
            parsed = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
            columns = list(parsed[0].keys())
            rows = [[row.get(c, "") for c in columns] for row in parsed[:50]]
            return {"type": "table", "columns": columns, "rows": rows}
    return None


def run_data_agent(step_description):
    """Reuses the existing MCP tool-calling loop unchanged - process_chat_request
    already does exactly "take a message, use tools if needed, return a plain-
    English answer". This just adapts its return shape into generic blocks."""
    result = process_chat_request(step_description, history=[])

    blocks = []
    if result.get("error"):
        blocks.append({"type": "text", "content": f"Error: {result['error']}"})
        return blocks

    if result.get("response"):
        blocks.append({"type": "text", "content": result["response"]})

    table_block = _table_block_from_mcp_result(result.get("mcp_result"))
    if table_block:
        blocks.append(table_block)

    return blocks


def run_dashboard_agent(step_description, context_text=""):
    """Asks the LLM for one chart spec (same shape the existing ```chart
    convention already uses) given the prior steps' text output as context,
    then pins it via dashboard_store - reusing the exact pin-a-chart
    capability the chat UI's "Pin to dashboard" button already calls."""
    user_message = step_description
    if context_text:
        user_message += f"\n\nData to visualize:\n{context_text}"

    raw = LLMProvider.call(get_chart_spec_prompt(), user_message)
    chart = _extract_json(raw)

    if not isinstance(chart, dict) or chart.get("error"):
        reason = chart.get("error") if isinstance(chart, dict) else "Model did not return a chart spec."
        return [{"type": "text", "content": f"Couldn't build a chart: {reason}"}]

    chart_type = chart.get("type") or "bar"
    title = chart.get("title") or "Chart"
    labels = chart.get("labels") or []
    data = chart.get("data") or []
    colors = chart.get("colors")

    dashboards = dashboard_store.list_dashboards()
    dashboard_id = dashboards[0]["id"] if dashboards else dashboard_store.create_dashboard("Agent Dashboard")["id"]
    dashboard_store.pin_chart(dashboard_id, title, chart_type, labels, data, colors)

    return [
        {"type": "text", "content": f"Pinned \"{title}\" to the dashboard."},
        {"type": "chart", "chart": {"type": chart_type, "title": title, "labels": labels, "data": data, "colors": colors}},
    ]


def execute_step(plan_id, step, context_text=""):
    if step["agent_type"] == "dashboard":
        blocks = run_dashboard_agent(step["description"], context_text)
    else:
        blocks = run_data_agent(step["description"])
    plan_store.append_result(plan_id, step["id"], blocks)
    return blocks


def execute_plan(plan_id):
    """Runs every step in order, synchronously. Each "data" step's text
    output is accumulated and handed to subsequent "dashboard" steps as
    context, so a chart step can use the numbers a prior step just looked up
    without re-deriving them."""
    plan = plan_store.get_plan(plan_id)
    if plan is None:
        raise FileNotFoundError(f"Plan {plan_id} not found")

    context_parts = []
    for step in plan["steps"]:
        blocks = execute_step(plan_id, step, context_text="\n".join(context_parts))
        for b in blocks:
            if b["type"] == "text":
                context_parts.append(b["content"])

    return plan_store.set_status(plan_id, "done")
