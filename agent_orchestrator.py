"""Agent orchestrator, phase 2: a real deepagents (LangGraph) graph with two
sub-agents - "data-agent" (MCP tools, via langchain_mcp_adapters) and
"dashboard-agent" (one pin_chart tool wrapping dashboard_store.pin_chart) -
dispatched through deepagents' built-in "task" tool.

Human-in-the-loop is native, not hand-rolled: interrupt_on={"task": True}
pauses the graph before every subagent dispatch, so approval is iterative -
one dispatch at a time, as the top-level model decides on it live - rather
than a single upfront plan. See HumanInTheLoopMiddleware in
langchain.agents.middleware.human_in_the_loop for the interrupt/resume
contract this relies on (verified directly against the installed package,
see the phase-2 plan for details): interrupt() surfaces as
result["__interrupt__"][0].value == {"action_requests": [{"name": "task",
"args": {"subagent_type", "description"}, ...}], "review_configs": [...]},
and resuming requires Command(resume={"decisions": [{"type": "approve"|
"reject"}, ...]}) - one decision per pending action_request, in order.

State (paused-mid-graph or complete) persists to data/agent_checkpoints.sqlite
via AsyncSqliteSaver, since Flask handles each HTTP request as a separate,
stateless call - a run started in one request is resumed in a later,
unrelated one by thread_id alone.

Everything here runs on one asyncio event loop per call (see _run_async),
not the sync API SqliteSaver/graph.invoke() would suggest: MCP tools (via
langchain_mcp_adapters) are async-only - the underlying MCP session is async,
same as mcp_client.py's - so a subagent that calls one requires the whole
graph run to go through .ainvoke(), which in turn needs an async checkpointer.
Discovered by actually running a live request against the real MCP server
(not just a scripted fake model), which is exactly the failure mode a
sync-only test would have missed - see the phase-2 plan's verification notes.
"""
import asyncio
import os
import subprocess
import sys
from typing import Optional

from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents.middleware import SummarizationMiddleware
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend

from config import Config
import mcp_registry
import dashboard_store
import agent_persona_store
import observability
from agent_model_bridge import get_chat_model
from prompts import get_data_agent_prompt, get_dashboard_agent_prompt, get_chat_agent_prompt, filter_relevant_tools

ORCHESTRATOR_SYSTEM_PROMPT = """You are the orchestrator for a multi-agent data platform. You have two sub-agent types available via the task tool:

- "data-agent": queries the connected database via tools, and can also run Python code for calculations or data transformations the database can't do directly. Use for anything that needs to look up, count, filter, verify, or compute data - also for plain conversation, which it handles gracefully. You yourself have no database or code-execution tools - always dispatch to data-agent for these, never answer from memory or claim you lack the capability.
- "dashboard-agent": turns already-known numbers into a chart and pins it to a dashboard. Use ONLY after a data-agent step has produced the numbers to chart, unless the user gave you the numbers directly.

RULES:
- Dispatch ONE sub-agent at a time and wait for its result before deciding the next step - never dispatch several in parallel.
- Each dispatch's "description" must be self-contained: the sub-agent sees only that description, not this conversation, so restate anything it needs to know.
- Ignore the filesystem tools (ls/read_file/write_file/edit_file/glob/grep) - they are not relevant to this platform.
- When every needed step is done, give the user a concise, plain-English final summary. Do not dispatch a sub-agent just to produce that summary yourself.
- If the request is pure conversation with nothing to look up or chart, dispatch one data-agent step with the user's message verbatim.
- NEVER end your final answer describing something you are about to do (e.g. "Let me try X" or "I will now..."). Either actually dispatch that next step via the task tool, or give the complete answer now - a stated intention is not a finished answer."""


def _data_dir():
    data_dir = os.path.join(os.getcwd(), Config.DATA_DIR)
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def _checkpoint_path():
    return os.path.join(_data_dir(), "agent_checkpoints.sqlite")


def _skills_root():
    path = os.path.join(_data_dir(), "agent_skills")
    os.makedirs(path, exist_ok=True)
    return path


def _run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


_mcp_tools_cache = {"tools": None, "expires_at": 0}
_MCP_TOOLS_CACHE_TTL = 60  # seconds


async def _get_mcp_tools():
    """LangChain BaseTools for every enabled MCP server, via the official
    langchain_mcp_adapters bridge - separate from mcp_client.py, which
    /api/chat still uses directly for its own hand-rolled tool-calling loop.

    Cached in-process (not via cache.py/Redis - a BaseTool holds live bound
    methods/callables, not JSON-serializable data) for 60s: this is the
    single biggest latency win available here, since every run/chat turn
    otherwise re-opens an MCP session and re-lists tools from scratch before
    the model even starts reasoning. Doesn't survive a process restart or
    share across multiple worker processes - an acceptable trade-off for a
    single-process Flask dev-server deployment."""
    now = asyncio.get_event_loop().time()
    if _mcp_tools_cache["tools"] is not None and now < _mcp_tools_cache["expires_at"]:
        return _mcp_tools_cache["tools"]

    servers = [s for s in mcp_registry.list_servers() if s.get("enabled", True)]
    if not servers:
        return []
    connections = {
        s["name"]: {
            "transport": "streamable_http",
            "url": s["url"],
            "headers": s.get("headers") or None,
        }
        for s in servers
    }
    client = MultiServerMCPClient(connections)
    tools = await client.get_tools()
    _mcp_tools_cache["tools"] = tools
    _mcp_tools_cache["expires_at"] = now + _MCP_TOOLS_CACHE_TTL
    return tools


def _relevant_mcp_tools(mcp_tools, user_message, max_tools=12, max_chars=6000):
    """Narrow the full MCP tool catalog to a relevant subset before binding
    it to the model - reuses prompts.filter_relevant_tools's keyword-match
    logic (built for chat_handler.py's older hand-rolled loop) against
    these langchain_mcp_adapters BaseTool objects, whose .args_schema is
    already a plain JSON-schema dict (verified live - same shape
    build_tools_description expects from mcp_client.py's raw tool dicts).

    This is the dominant latency lever measured for this app: binding all
    56 real MCP tools (some - e.g. tdvs_create - carry huge parameter
    schemas) costs ~14,000 prompt tokens on EVERY call regardless of hop
    count or mode. Timed live against the real local model: cold prefill of
    that exact 14k-token prompt took ~20s; the identical prompt a second
    time (KV-cache hit) took ~1s. Tool-set size, not reasoning or hop
    count, is the actual bottleneck - trimming to ~12 relevant tools cuts
    the uncached case roughly proportionally.

    Only applied on a turn's initial invocation (see _build_agent's
    user_message param) - never on a resume, where the exact tool the
    paused turn already selected must still be bound or the resume itself
    would break."""
    if not mcp_tools:
        return mcp_tools
    dicts = [
        {"name": t.name, "description": t.description or "", "inputSchema": t.args_schema if isinstance(t.args_schema, dict) else {}}
        for t in mcp_tools
    ]
    selected_names = {d["name"] for d in filter_relevant_tools(dicts, user_message, max_tools=max_tools, max_chars=max_chars)}
    return [t for t in mcp_tools if t.name in selected_names]


def _make_dashboard_tools(captured_blocks):
    """Tools giving the dashboard-agent real autonomy over dashboards, not
    just chart-pinning into whichever one happened to exist first (Phase
    2-4's behavior) - it can list what exists and create/target one by name,
    so "create a dashboard called Ops KPIs and add a chart of X" works
    end-to-end without a human creating the dashboard by hand first."""

    @tool
    def list_dashboards() -> str:
        """List existing dashboards by name, with how many charts each has."""
        dashboards = dashboard_store.list_dashboards()
        if not dashboards:
            return "No dashboards exist yet."
        return "\n".join(f'- "{d["name"]}" ({d["chart_count"]} charts)' for d in dashboards)

    @tool
    def create_dashboard(name: str) -> str:
        """Create a new, empty dashboard with the given name."""
        dashboard_store.create_dashboard(name)
        return f'Created dashboard "{name}".'

    @tool
    def pin_chart(dashboard_name: str, title: str, chart_type: str, labels: list[str], data: list[float], colors: Optional[list[str]] = None) -> str:
        """Pin a chart to a dashboard, found by name (case-insensitive) or
        created if no dashboard with that name exists yet. chart_type is one
        of pie/bar/line/doughnut/radar. labels and data must be the same
        length. colors is optional (a palette is used if omitted)."""
        dashboards = dashboard_store.list_dashboards()
        match = next((d for d in dashboards if d["name"].lower() == dashboard_name.lower()), None)
        dashboard_id = match["id"] if match else dashboard_store.create_dashboard(dashboard_name)["id"]
        dashboard_store.pin_chart(dashboard_id, title, chart_type, labels, data, colors)
        captured_blocks.append({
            "type": "chart",
            "chart": {"type": chart_type, "title": title, "labels": labels, "data": data, "colors": colors},
        })
        return f'Pinned "{title}" to dashboard "{dashboard_name}".'

    return [list_dashboards, create_dashboard, pin_chart]


@tool
def run_python(code: str) -> str:
    """Execute Python code (e.g. for calculations or data transformations) and
    return its stdout/stderr. Requires human approval before running."""
    # A fresh subprocess, not sandboxed beyond that - see the phase-5 plan's
    # explicit scope note. Gated by interrupt_on={"run_python": True} on the
    # data-agent in every mode (see _build_agent) - approval is the sole
    # safety mechanism, per your explicit "always approval-gated" choice,
    # since this subprocess shares the container's filesystem and DB
    # credentials.
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=30,
        )
        output = result.stdout.strip()
        if result.stderr.strip():
            output += f"\n[stderr]\n{result.stderr.strip()}"
        if result.returncode != 0:
            output += f"\n[exit code {result.returncode}]"
        return output[:5000] or "(no output)"
    except subprocess.TimeoutExpired:
        return "Error: execution timed out after 30 seconds"


def _flavor_prompt(base_prompt, persona_id):
    """Prefix any base prompt with a persona's standing domain expertise
    when one is selected for this run - the only place a persona affects
    behavior (see agent_persona_store.py)."""
    if not persona_id:
        return base_prompt
    persona = agent_persona_store.get_persona(persona_id)
    if persona is None:
        return base_prompt
    return f"You are acting as \"{persona['name']}\": {persona['expertise_prompt']}\n\n{base_prompt}"


def _data_agent_prompt_for(persona_id):
    return _flavor_prompt(get_data_agent_prompt(), persona_id)


def _chat_agent_prompt_for(persona_id):
    return _flavor_prompt(get_chat_agent_prompt(), persona_id)


async def _build_agent(captured_blocks, checkpointer, persona_id=None, mode="task", user_message=None):
    """Fresh agent per run - rebuilds from the current MCP registry and LLM
    profile every time (mirrors mcp_client.py's own per-call rebuild), so a
    registry/profile change takes effect on the next run without a restart.

    mode="task" (default) keeps the orchestrator + data-agent/dashboard-agent
    dispatch structure from Phase 2-4, with every dispatch gated behind
    approval (interrupt_on={"task": True}) - real, load-bearing governance
    for one-shot task runs, so the multi-hop structure stays.

    mode="chat" was already running with no dispatch-approval gate
    (interrupt_on=None), so the multi-hop orchestrator->subagent chain there
    bought nothing but extra local-model reasoning round-trips - measured
    live at ~40s wall-clock for a trivial question, dominated by hop count,
    not raw inference speed (each hop is its own full reasoning pass; GPU/
    Metal offload was confirmed fine independently). So chat mode instead
    builds ONE flat agent with every tool (MCP + run_python + dashboard
    tools) attached directly - no subagents, no "task" tool, one reasoning
    pass per turn instead of 3+. run_python stays approval-gated exactly the
    same way (interrupt_on={"run_python": True} works identically whether
    the tool sits on the top-level agent or a nested subagent - verified in
    the phase-5 W2 notes). The checkpointer still persists full message
    history per thread_id either way (verified live: a second .ainvoke() on
    the same thread_id sees prior turns).

    user_message, when given, narrows the bound MCP tool set to whatever's
    relevant to it (see _relevant_mcp_tools) - the single biggest latency
    lever measured for this app. Pass it only when building the agent for a
    turn's initial invocation (start_run/chat_message); leave it None for a
    resume or a state/history read, where the full tool set must stay
    available/consistent with what the paused turn was already built with."""
    model = get_chat_model()
    mcp_tools = await _get_mcp_tools()
    if user_message:
        mcp_tools = _relevant_mcp_tools(mcp_tools, user_message)
    # FilesystemBackend (not the default in-memory StateBackend) so skill
    # files saved via agent_skill_store.py are real, persistent files
    # deepagents' SkillsMiddleware can read - see agent_skill_store.py's
    # docstring for the on-disk shape this expects.
    backend = FilesystemBackend(root_dir=_skills_root())

    if mode == "chat":
        chat_kwargs = {}
        if persona_id:
            chat_kwargs["skills"] = [f"/{persona_id}/"]
        return create_deep_agent(
            model=model,
            system_prompt=_chat_agent_prompt_for(persona_id),
            tools=[*mcp_tools, run_python, *_make_dashboard_tools(captured_blocks)],
            interrupt_on={"run_python": True},
            checkpointer=checkpointer,
            backend=backend,
            # Bounds prompt growth for long-running chat threads: only acts
            # once a thread's history actually reaches ~3000 tokens (most
            # chats never do - zero overhead until then), replacing older
            # turns with a model-written summary instead of dropping them
            # outright, so the last 12 messages stay verbatim and older
            # context survives as a compressed summary rather than vanishing.
            middleware=[SummarizationMiddleware(model=model, trigger=("tokens", 3000), keep=("messages", 12))],
            **chat_kwargs,
        )

    data_agent_spec = {
        "name": "data-agent",
        "description": "Queries the connected database via tools to look up, count, filter, or verify data. Also handles plain conversation.",
        "tools": [*mcp_tools, run_python],
        "system_prompt": _data_agent_prompt_for(persona_id),
        # Gated in every mode, not just "task" - code execution shares the
        # container's filesystem and DB credentials, so approval is required
        # regardless of whether this is a one-shot task or an open chat
        # (verified live: a nested interrupt_on on a sub-agent's own tool
        # surfaces through the top-level .ainvoke() exactly like the
        # top-level task-dispatch interrupt does, and resumes the same way -
        # see the phase-5 plan's W2 verification notes).
        "interrupt_on": {"run_python": True},
    }
    if persona_id:
        # One source per persona (data/agent_skills/<persona_id>/) - any
        # skills saved for this persona (agent_skill_store.py) load into the
        # data-agent's context automatically via deepagents' own mechanism.
        data_agent_spec["skills"] = [f"/{persona_id}/"]

    return create_deep_agent(
        model=model,
        system_prompt=ORCHESTRATOR_SYSTEM_PROMPT,
        subagents=[
            data_agent_spec,
            {"name": "dashboard-agent", "description": "Manages dashboards autonomously: lists existing ones, creates new ones by name, and pins charts to them. Use only after a data-agent step has produced numbers to chart.", "tools": _make_dashboard_tools(captured_blocks), "system_prompt": get_dashboard_agent_prompt()},
        ],
        interrupt_on={"task": True} if mode == "task" else None,
        checkpointer=checkpointer,
        backend=backend,
    )


def _final_text(messages):
    """Last non-blank AIMessage text, walking back from the end - copies
    deepagents' own approach (subagents.py's _return_command_with_state_update)
    verbatim: some models emit a trailing empty/whitespace-only AIMessage
    after their real final answer (observed live, against a local model, as
    a trailing "\\n\\n"), so content must be stripped before the truthiness
    check, and .text (not .content) handles non-string content shapes."""
    for msg in reversed(messages):
        if msg.__class__.__name__ == "AIMessage":
            text = msg.text.rstrip() if msg.text else ""
            if text:
                return text
    return None


def _pending_actions_from_interrupt(interrupt_value):
    """Generic {tool, args} per pending action - covers both the top-level
    "task" dispatch interrupt (args: subagent_type, description) and a
    nested tool interrupt like "run_python" (args: code) with the same
    shape, since HumanInTheLoopMiddleware's action_requests already carry
    the real tool name and args regardless of which graph level raised it
    (verified live - see the phase-5 plan's W2 notes). The frontend
    branches on "tool" to render the right approval card."""
    return [
        {"tool": ar["name"], "args": ar["args"]}
        for ar in interrupt_value.get("action_requests", [])
    ]


def _run_state_from_result(result, captured_blocks):
    if "__interrupt__" in result:
        interrupt_value = result["__interrupt__"][0].value
        return {
            "status": "interrupted",
            "pending_actions": _pending_actions_from_interrupt(interrupt_value),
            "blocks": captured_blocks,
        }

    blocks = list(captured_blocks)
    text = _final_text(result.get("messages", []))
    if text:
        blocks.append({"type": "text", "content": text})
    return {"status": "done", "pending_actions": [], "blocks": blocks}


def _config_for(thread_id, persona_id):
    """Standard graph-invoke config: thread id plus the observability
    callback stack (in-app activity log always, Langfuse when configured -
    see observability.get_callbacks, which never raises)."""
    return {"configurable": {"thread_id": thread_id}, "callbacks": observability.get_callbacks(thread_id, persona_id)}


async def _start_run_async(thread_id, user_request, persona_id):
    captured_blocks = []
    observability.log_event(thread_id, persona_id, "run_start", label=user_request)
    async with AsyncSqliteSaver.from_conn_string(_checkpoint_path()) as checkpointer:
        agent = await _build_agent(captured_blocks, checkpointer, persona_id, user_message=user_request)
        result = await agent.ainvoke({"messages": [{"role": "user", "content": user_request}]}, config=_config_for(thread_id, persona_id))
        state = _run_state_from_result(result, captured_blocks)
        observability.log_event(thread_id, persona_id, state["status"], status="ok")
        return state


async def _resume_run_async(thread_id, decision, persona_id):
    # persona_id must match the persona the run was started with - a deep
    # agent's system prompts are part of how it's built, not part of the
    # checkpointed state, so resuming with a different persona would silently
    # swap the data-agent's expertise mid-run. Callers pass the persona_id
    # recorded on the run (agent_run_store) at creation time.
    captured_blocks = []
    async with AsyncSqliteSaver.from_conn_string(_checkpoint_path()) as checkpointer:
        agent = await _build_agent(captured_blocks, checkpointer, persona_id)
        config = _config_for(thread_id, persona_id)
        snapshot = await agent.aget_state(config)
        if not snapshot.interrupts:
            raise ValueError(f"Run {thread_id} has no pending interrupt to resume")
        pending_count = len(snapshot.interrupts[0].value.get("action_requests", []))
        decisions = [{"type": decision}] * pending_count
        observability.log_event(thread_id, persona_id, "resume", label=decision)
        result = await agent.ainvoke(Command(resume={"decisions": decisions}), config=config)
        state = _run_state_from_result(result, captured_blocks)
        observability.log_event(thread_id, persona_id, state["status"], status="ok")
        return state


async def _get_run_state_async(thread_id, persona_id):
    captured_blocks = []
    async with AsyncSqliteSaver.from_conn_string(_checkpoint_path()) as checkpointer:
        agent = await _build_agent(captured_blocks, checkpointer, persona_id)
        config = {"configurable": {"thread_id": thread_id}}
        snapshot = await agent.aget_state(config)
        if not snapshot.values:
            return None
        if snapshot.interrupts:
            return {
                "status": "interrupted",
                "pending_actions": _pending_actions_from_interrupt(snapshot.interrupts[0].value),
                "blocks": [],
            }
        text = _final_text(snapshot.values.get("messages", []))
        blocks = [{"type": "text", "content": text}] if text else []
        return {"status": "done", "pending_actions": [], "blocks": blocks}


def start_run(thread_id, user_request, persona_id=None):
    """Invoke a fresh graph on a new thread, running to the first interrupt
    (a proposed subagent dispatch) or straight to completion. persona_id, if
    given, flavors the data-agent's system prompt with that persona's
    standing domain expertise (see agent_persona_store.py)."""
    return _run_async(_start_run_async(thread_id, user_request, persona_id))


def resume_run(thread_id, decision, persona_id=None):
    """Resume a paused run with an approve/reject decision, running to the
    next interrupt or completion. decision: "approve" or "reject". persona_id
    must match the persona the run was started with (see _resume_run_async)."""
    return _run_async(_resume_run_async(thread_id, decision, persona_id))


def get_run_state(thread_id, persona_id=None):
    """Re-derive the current RunState from checkpointed state alone - for
    reloading or replaying a run without resuming it. persona_id must match
    the persona the run was started with (see _resume_run_async)."""
    return _run_async(_get_run_state_async(thread_id, persona_id))


# ---- Chat mode (W1): multi-turn conversation per persona ----
# Same graph and checkpointer as task runs, built with mode="chat" so the
# top-level task-dispatch gate is off; a chat thread's id is independent of
# any task run's thread id (agent_chat_store.py, not agent_run_store.py).
# Still interrupt-aware, same as task runs: run_python is gated in every
# mode (see _build_agent), so a chat turn can pause for code approval just
# like a task dispatch does - chat_message()/resume_chat() return the same
# {status, pending_actions, blocks} shape start_run()/resume_run() do.

async def _chat_message_async(thread_id, user_message, persona_id):
    captured_blocks = []
    observability.log_event(thread_id, persona_id, "chat_message", label=user_message)
    async with AsyncSqliteSaver.from_conn_string(_checkpoint_path()) as checkpointer:
        agent = await _build_agent(captured_blocks, checkpointer, persona_id, mode="chat", user_message=user_message)
        result = await agent.ainvoke({"messages": [{"role": "user", "content": user_message}]}, config=_config_for(thread_id, persona_id))
        state = _run_state_from_result(result, captured_blocks)
        observability.log_event(thread_id, persona_id, state["status"], status="ok")
        return state


def chat_message(thread_id, user_message, persona_id=None):
    """Send one message in a multi-turn chat thread and get the agent's
    reply for just this turn - prior turns are already in the checkpointer
    under this thread_id, so only the new message is sent. May come back
    "interrupted" (e.g. a run_python call pending approval) instead of
    "done" - resume with resume_chat()."""
    return _run_async(_chat_message_async(thread_id, user_message, persona_id))


async def _resume_chat_async(thread_id, decision, persona_id):
    captured_blocks = []
    async with AsyncSqliteSaver.from_conn_string(_checkpoint_path()) as checkpointer:
        agent = await _build_agent(captured_blocks, checkpointer, persona_id, mode="chat")
        config = _config_for(thread_id, persona_id)
        snapshot = await agent.aget_state(config)
        if not snapshot.interrupts:
            raise ValueError(f"Chat {thread_id} has no pending interrupt to resume")
        pending_count = len(snapshot.interrupts[0].value.get("action_requests", []))
        decisions = [{"type": decision}] * pending_count
        observability.log_event(thread_id, persona_id, "resume", label=decision)
        result = await agent.ainvoke(Command(resume={"decisions": decisions}), config=config)
        state = _run_state_from_result(result, captured_blocks)
        observability.log_event(thread_id, persona_id, state["status"], status="ok")
        return state


def resume_chat(thread_id, decision, persona_id=None):
    """Resume a chat turn paused on a pending tool approval (e.g. run_python)."""
    return _run_async(_resume_chat_async(thread_id, decision, persona_id))


# ---- Chat mode, streaming variant: real token-by-token output instead of
# one blocking call. Same graph/checkpointer/interrupt semantics as
# chat_message/resume_chat above - this only changes how the reply is
# delivered, not what gets computed, so it's additive, not a replacement.
#
# Verified live against the real local model (stream_mode="messages"):
# this reasoning model emits ~30-40 AIMessageChunks of empty content while
# "thinking" before any visible answer text starts - only chunks with
# non-empty .content are forwarded as "token" events, so a UI naturally
# shows its existing "thinking" indicator during that phase and switches to
# live text the moment real output starts. Also verified: an interrupt
# (e.g. run_python) still lands in agent.aget_state(config).interrupts
# exactly the same after streaming via .astream() as it does after
# .ainvoke() - reading state, not the stream itself, is what determines
# status/pending_actions here.

async def _stream_run(agent, input_value, config, captured_blocks):
    """Shared streaming core for a turn's initial invocation or its resume
    (input_value is either a {"messages": [...]} dict or a Command(resume=...)).
    Yields {"type": "token", "text": ...} for each real content delta, then
    exactly one {"type": "result", "data": {...}} event with the same
    status/pending_actions/blocks shape _run_state_from_result returns."""
    async for chunk in agent.astream(input_value, config=config, stream_mode="messages"):
        message, _meta = chunk
        # Only AIMessageChunk carries the model's own generated text -
        # stream_mode="messages" also emits ToolMessage chunks (a tool's raw
        # output, e.g. run_python's stdout), whose .content is non-empty too
        # and would otherwise leak into the live-typing bubble ahead of the
        # model's real answer (observed live: a "225" token from
        # run_python's stdout arriving before the synthesized "15 x 15 =
        # 225" text).
        if type(message).__name__ != "AIMessageChunk":
            continue
        text = message.content or ""
        if text:
            yield {"type": "token", "text": text}

    snapshot = await agent.aget_state(config)
    if snapshot.interrupts:
        yield {"type": "result", "data": {
            "status": "interrupted",
            "pending_actions": _pending_actions_from_interrupt(snapshot.interrupts[0].value),
            "blocks": captured_blocks,
        }}
        return
    blocks = list(captured_blocks)
    text = _final_text(snapshot.values.get("messages", []))
    if text:
        blocks.append({"type": "text", "content": text})
    yield {"type": "result", "data": {"status": "done", "pending_actions": [], "blocks": blocks}}


async def _chat_message_stream_async(thread_id, user_message, persona_id):
    captured_blocks = []
    observability.log_event(thread_id, persona_id, "chat_message", label=user_message)
    async with AsyncSqliteSaver.from_conn_string(_checkpoint_path()) as checkpointer:
        agent = await _build_agent(captured_blocks, checkpointer, persona_id, mode="chat", user_message=user_message)
        config = _config_for(thread_id, persona_id)
        async for event in _stream_run(agent, {"messages": [{"role": "user", "content": user_message}]}, config, captured_blocks):
            if event["type"] == "result":
                observability.log_event(thread_id, persona_id, event["data"]["status"], status="ok")
            yield event


async def _resume_chat_stream_async(thread_id, decision, persona_id):
    captured_blocks = []
    async with AsyncSqliteSaver.from_conn_string(_checkpoint_path()) as checkpointer:
        agent = await _build_agent(captured_blocks, checkpointer, persona_id, mode="chat")
        config = _config_for(thread_id, persona_id)
        snapshot = await agent.aget_state(config)
        if not snapshot.interrupts:
            raise ValueError(f"Chat {thread_id} has no pending interrupt to resume")
        pending_count = len(snapshot.interrupts[0].value.get("action_requests", []))
        decisions = [{"type": decision}] * pending_count
        observability.log_event(thread_id, persona_id, "resume", label=decision)
        async for event in _stream_run(agent, Command(resume={"decisions": decisions}), config, captured_blocks):
            if event["type"] == "result":
                observability.log_event(thread_id, persona_id, event["data"]["status"], status="ok")
            yield event


def chat_message_stream(thread_id, user_message, persona_id, event_callback):
    """Sync bridge for a Flask SSE route: runs the streaming turn on a fresh
    event loop (see _run_async), calling event_callback(event) for each
    token/result event as it's produced."""
    async def _drain():
        async for event in _chat_message_stream_async(thread_id, user_message, persona_id):
            event_callback(event)
    _run_async(_drain())


def resume_chat_stream(thread_id, decision, persona_id, event_callback):
    async def _drain():
        async for event in _resume_chat_stream_async(thread_id, decision, persona_id):
            event_callback(event)
    _run_async(_drain())


async def _get_chat_history_async(thread_id, persona_id):
    async with AsyncSqliteSaver.from_conn_string(_checkpoint_path()) as checkpointer:
        agent = await _build_agent([], checkpointer, persona_id, mode="chat")
        config = {"configurable": {"thread_id": thread_id}}
        snapshot = await agent.aget_state(config)
        if not snapshot.values:
            return {"messages": [], "status": "done", "pending_actions": []}
        turns = []
        for msg in snapshot.values.get("messages", []):
            cls = msg.__class__.__name__
            if cls not in ("HumanMessage", "AIMessage"):
                continue
            text = msg.text.rstrip() if getattr(msg, "text", None) else ""
            if not text:
                continue
            turns.append({"role": "user" if cls == "HumanMessage" else "assistant", "content": text})
        if snapshot.interrupts:
            return {"messages": turns, "status": "interrupted", "pending_actions": _pending_actions_from_interrupt(snapshot.interrupts[0].value)}
        return {"messages": turns, "status": "done", "pending_actions": []}


def get_chat_history(thread_id, persona_id=None):
    """Reconstruct a chat thread's turns (role + text only) from checkpointed
    state, for reloading a conversation - plus whether it's currently paused
    on a pending tool approval. Charts pinned mid-conversation don't
    reappear inline on reload (same simplification as task-run replay) - they
    stay visible on the Dashboards view, which is their source of truth."""
    return _run_async(_get_chat_history_async(thread_id, persona_id))
