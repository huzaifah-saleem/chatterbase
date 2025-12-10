"""Chat request handler with multi-step execution logic"""
import json
import re
from mcp_client import run_async, get_mcp_tools, call_mcp_tool
from llm_providers import LLMProvider
from prompts import get_system_prompt, get_summary_prompt
from config import Config


def summarize_result(result):
    """Summarize a large result for LLM feedback"""
    result_str = json.dumps(result, indent=2)
    if len(result_str) <= 5000:
        return result_str

    try:
        content = result.get("content", [])
        if content and isinstance(content, list) and len(content) > 0:
            first_content = content[0]
            if isinstance(first_content, str):
                try:
                    parsed = json.loads(first_content)
                    if isinstance(parsed, list):
                        return f"The tool returned a list with {len(parsed)} items."
                    elif isinstance(parsed, dict):
                        return f"The tool returned data with keys: {list(parsed.keys())[:10]}."
                except json.JSONDecodeError:
                    pass
    except Exception:
        pass

    return "Result received (truncated)."


def process_chat_request(user_message, history=None, progress_callback=None):
    """Process a chat request with multi-step execution

    Args:
        user_message: The user's message
        history: Chat history
        progress_callback: Optional callback function to report progress
    """
    history = history or []

    # Helper to report progress
    def report_progress(status, detail=""):
        if progress_callback:
            progress_callback(status, detail)

    # Get MCP tools
    tools = []
    mcp_error = None
    try:
        report_progress("connecting", "Fetching available tools...")
        tools = run_async(get_mcp_tools())
        print(f"[Chat] Got {len(tools)} tools")
    except Exception as e:
        mcp_error = str(e)
        print(f"[Chat] MCP error: {e}")

    # Build system prompt
    if tools:
        system_prompt = get_system_prompt(tools)
    else:
        system_prompt = f"You are a helpful assistant. MCP connection issue: {mcp_error or 'No tools available'}."

    # Multi-step execution loop
    all_results = []
    current_message = user_message
    current_history = history.copy()

    for iteration in range(1, Config.MAX_ITERATIONS + 1):
        print(f"[Chat] Iteration {iteration}")

        report_progress("thinking", f"Step {iteration}: Analyzing request...")

        # Get LLM response
        print(f"[Chat] Calling LLM for tool selection...")
        llm_response = LLMProvider.call(system_prompt, current_message, current_history)
        print(f"[Chat] LLM response received: {llm_response[:200]}...")

        # Check for MCP tool call (flexible pattern to handle typos like "m-cp_call")
        mcp_match = re.search(r"```m[_-]?cp_call\s*(.*?)\s*```", llm_response, re.DOTALL)

        if mcp_match and tools:
            try:
                mcp_call = json.loads(mcp_match.group(1))
                requested_tool = mcp_call.get("tool", "")

                # Validate tool exists
                valid_tool_names = [t['name'] for t in tools]
                if requested_tool not in valid_tool_names:
                    error_msg = f"Error: Tool '{requested_tool}' does not exist. Available tools: {', '.join(valid_tool_names)}"
                    print(f"[Chat] {error_msg}")
                    return {
                        "response": f"{error_msg}\n\nPlease use one of the available tool names exactly as listed.",
                        "error": error_msg
                    }

                print(f"[Chat] Calling tool: {mcp_call}")
                report_progress("executing", f"Running: {mcp_call['tool']}")
                mcp_result = run_async(call_mcp_tool(mcp_call["tool"], mcp_call.get("arguments", {})))

                # Store result
                all_results.append({
                    "tool": mcp_call["tool"],
                    "arguments": mcp_call.get("arguments", {}),
                    "result": mcp_result
                })

                # Prepare for next iteration
                result_summary = summarize_result(mcp_result)
                current_history.append({"role": "user", "content": current_message})
                current_history.append({"role": "assistant", "content": f"```mcp_call\n{json.dumps(mcp_call)}\n```"})
                current_history.append({"role": "user", "content": f"[RESULT] {result_summary[:800]}"})
                current_message = "Tool executed successfully. What is the NEXT task from the original user request? If there are more tasks, execute the next tool. If ALL tasks are complete, respond with only: DONE"
                continue

            except json.JSONDecodeError:
                break
        else:
            # No tool call - check if DONE or regular response
            if "DONE" in llm_response and all_results:
                print(f"[Chat] LLM signaled DONE, all tasks complete")
                break
            else:
                print(f"[Chat] No tool call detected, treating as final response")
                return {"response": llm_response}

    # Generate final summary if tools were executed
    if all_results:
        print(f"[Chat] Generating final response for {len(all_results)} tool calls")
        report_progress("summarizing", f"Generating summary for {len(all_results)} operations...")

        operations_summary = "\n".join([
            f"{i+1}. Tool '{r['tool']}': {json.dumps(r['result'], indent=2)[:500]}..."
            for i, r in enumerate(all_results)
        ])

        followup = f"""The user asked: "{user_message}"

I executed {len(all_results)} operations:
{operations_summary}

Provide a comprehensive summary of all results. If the user asked for analysis or visualization, include appropriate charts using the ```chart``` format. Do NOT just repeat the JSON data - explain what it means in plain English."""

        print(f"[Chat] Calling LLM to generate explanation...")
        try:
            explanation = LLMProvider.call(get_summary_prompt(), followup)
            print(f"[Chat] Explanation generated successfully")
        except Exception as e:
            print(f"[Chat] Error generating explanation: {e}")
            explanation = f"Tool executed successfully but error generating summary: {str(e)}"

        return {
            "response": explanation,
            "mcp_call": all_results[-1] if all_results else None,
            "mcp_result": all_results[-1]["result"] if all_results else None,
            "all_tool_calls": all_results,
            "tool_result_for_history": json.dumps(all_results, indent=2)[:15000]
        }

    return {"response": "No response generated."}
