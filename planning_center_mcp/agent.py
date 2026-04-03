import json
import logging
import os
from datetime import date

import httpx

log = logging.getLogger(__name__)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://192.168.1.13:11434")
AGENT_MODEL = os.getenv("AGENT_MODEL", "mistral-small3.1")
MAX_ITERATIONS = 10
OLLAMA_TIMEOUT = 120.0
MAX_TOOL_RESULT_CHARS = 8000

AGENT_TOOL_NAMES = {
    "get_service_types",
    "get_plans",
    "get_plan_details",
    "get_songs",
    "get_song",
    "get_song_schedules",
    "get_arrangements",
    "get_song_tags",
    "find_songs_by_tags",
    "search_people",
    "get_person",
    "get_person_field_data",
    "get_team_names",
    "song_usage_report",
    "volunteer_activity_report",
    "service_plan_report",
    "song_detail_report",
    "upcoming_services_report",
    "search_prophecies",
    "get_sync_status",
}

SYSTEM_PROMPT = """\
You are a church administration assistant with access to Planning Center Online data.
You only answer questions related to Planning Center: songs, service plans, volunteer schedules, and team information.
If a question is unrelated to church administration or Planning Center data, politely decline and explain you can only help with Planning Center topics.

Rules:
- Call tools to get real data. Never guess or make up information.
- Prefer cached report tools (ending in _report) — they are faster than direct API tools.
- For service/plan lookups, call get_service_types first to get the service type IDs.
- For song key questions (e.g. "what key is this song usually played in?"), call song_detail_report — it includes key_name per schedule entry. Count occurrences to find the most common key.
- Keep answers concise. Use bullet points or short tables for lists.
- If you cannot find the requested information, say so clearly.
- Only pass parameters that are explicitly listed in the tool's parameter schema. Never invent parameters.
- Today is {today}.
"""

_tool_cache = None


async def _build_ollama_tools(mcp_server):
    global _tool_cache
    if _tool_cache is not None:
        return _tool_cache

    tools_meta = await mcp_server.list_tools()

    ollama_tools = []
    for tool in tools_meta:
        if tool.name not in AGENT_TOOL_NAMES:
            continue
        mcp_tool = tool.to_mcp_tool()
        schema = mcp_tool.inputSchema or {"type": "object", "properties": {}}
        ollama_tools.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or "",
                "parameters": schema,
            },
        })

    _tool_cache = ollama_tools
    log.info("Built Ollama tool definitions for %d tools", len(ollama_tools))
    return ollama_tools


async def _call_tool(mcp_server, tool_name, arguments):
    try:
        result = await mcp_server.call_tool(tool_name, arguments)
        texts = [c.text for c in result if hasattr(c, "text")]
        output = "\n".join(texts) if texts else str(result)
    except Exception as e:
        log.warning("Tool %s failed: %s", tool_name, e)
        output = json.dumps({"error": f"Tool {tool_name} failed: {e}"})

    if len(output) > MAX_TOOL_RESULT_CHARS:
        output = output[:MAX_TOOL_RESULT_CHARS] + "\n... (truncated)"
    return output


async def ask(question, mcp_server, ollama_url=None, model=None, max_iterations=None):
    ollama_url = ollama_url or OLLAMA_URL
    model = model or AGENT_MODEL
    max_iterations = max_iterations or MAX_ITERATIONS

    ollama_tools = await _build_ollama_tools(mcp_server)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(today=date.today().isoformat())},
        {"role": "user", "content": question},
    ]

    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
        for iteration in range(max_iterations):
            payload = {
                "model": model,
                "messages": messages,
                "tools": ollama_tools,
                "stream": False,
                "think": False,
                "options": {"num_predict": 2048},
            }

            try:
                resp = await client.post(f"{ollama_url}/api/chat", json=payload)
                resp.raise_for_status()
            except httpx.ConnectError:
                return f"Cannot reach the AI service at {ollama_url}. Is Ollama running?"
            except httpx.TimeoutException:
                return "The AI service timed out. The model may be busy — try again shortly."
            except httpx.HTTPStatusError as e:
                return f"AI service error: {e.response.status_code}"

            data = resp.json()
            assistant_msg = data["message"]
            messages.append(assistant_msg)

            tool_calls = assistant_msg.get("tool_calls")
            if not tool_calls:
                return assistant_msg.get("content", "").strip() or "No response generated."

            for tc in tool_calls:
                fn = tc["function"]
                tool_name = fn["name"]
                tool_args = fn.get("arguments", {})

                log.info("Agent [iter %d] calling %s(%s)", iteration + 1, tool_name, json.dumps(tool_args)[:200])

                if tool_name not in AGENT_TOOL_NAMES:
                    result_text = json.dumps({"error": f"Unknown tool: {tool_name}"})
                else:
                    result_text = await _call_tool(mcp_server, tool_name, tool_args)

                messages.append({"role": "tool", "content": result_text})

    return "Reached the maximum number of steps without a final answer. Please try a more specific question."


def register_agent_tool(mcp_server):
    @mcp_server.tool
    async def ask_question(question: str) -> str:
        """Ask a natural language question about Planning Center data.
        Uses AI to interpret your question, call the appropriate tools,
        and return a human-readable answer."""
        return await ask(question, mcp_server)
