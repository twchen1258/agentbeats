"""Helper for solving tasks using LLM with MCP tools."""

import json
import logging
from typing import Any
from openai import OpenAI
from mcp import ClientSession
from mcp.client.sse import sse_client

logger = logging.getLogger(__name__)


class MCPConnection:
    """Context manager for MCP connections with proper cleanup."""

    def __init__(self, mcp_url: str):
        self.mcp_url = mcp_url
        self.sse_context = None
        self.session = None
        self.read_stream = None
        self.write_stream = None

    async def __aenter__(self) -> ClientSession:
        """Connect to MCP server."""
        sse_url = f"{self.mcp_url}/sse"
        logger.info(f"Connecting to {sse_url}")

        self.sse_context = sse_client(sse_url)
        self.read_stream, self.write_stream = await self.sse_context.__aenter__()

        self.session = ClientSession(self.read_stream, self.write_stream)
        await self.session.__aenter__()
        await self.session.initialize()

        tools = await self.session.list_tools()
        logger.info(f"Connected. Tools: {[t.name for t in tools.tools]}")

        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Cleanup MCP resources."""
        if self.session:
            try:
                await self.session.__aexit__(exc_type, exc_val, exc_tb)
            except Exception as e:
                logger.warning(f"Session close error: {e}")

        if self.sse_context:
            try:
                await self.sse_context.__aexit__(exc_type, exc_val, exc_tb)
            except Exception as e:
                logger.warning(f"SSE close error: {e}")

        logger.info("MCP closed")


def connect_to_mcp(mcp_url: str) -> MCPConnection:
    """Create MCP connection context manager."""
    return MCPConnection(mcp_url)


def convert_mcp_tools_to_openai(tools_result) -> list[dict]:
    """Convert MCP tools to OpenAI function calling format."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema,
            },
        }
        for tool in tools_result.tools
    ]


async def call_mcp_tool(
    session: ClientSession, tool_name: str, arguments: dict
) -> dict[str, Any]:
    """Call MCP tool and return result."""
    logger.debug(f"Calling {tool_name}: {arguments}")

    result = await session.call_tool(tool_name, arguments=arguments)

    if result.content and len(result.content) > 0:
        return json.loads(result.content[0].text)
    return {"error": "No result from MCP server"}


async def solve_task_with_llm_and_mcp(
    user_input: str,
    mcp_session: ClientSession,
    openai_client: OpenAI,
    model: str,
    max_iterations: int = 10,
) -> str:
    """Solve task using LLM with MCP tools."""
    tools_result = await mcp_session.list_tools()
    openai_tools = convert_mcp_tools_to_openai(tools_result)
    logger.info(f"Using {len(openai_tools)} MCP tools")

    messages = [
        {
            "role": "system",
            "content": """You are a helpful assistant being evaluated on Terminal-Bench.

Your goal is to complete terminal tasks by executing bash commands.

Guidelines:
- Break down complex tasks into simple steps
- Execute one command at a time and check the result
- If a command fails, analyze the error and try a different approach
- When complete, provide a clear summary
- Be concise but thorough""",
        },
        {"role": "user", "content": user_input},
    ]

    for iteration in range(1, max_iterations + 1):
        logger.info(f"=== Iteration {iteration}/{max_iterations} ===")

        response = openai_client.chat.completions.create(
            model=model, messages=messages, tools=openai_tools, tool_choice="auto"
        )

        assistant_msg = response.choices[0].message
        logger.info(
            f"LLM: {assistant_msg.content[:200] if assistant_msg.content else 'None'} | "
            f"Tools: {len(assistant_msg.tool_calls) if assistant_msg.tool_calls else 0}"
        )

        messages.append(
            {
                "role": "assistant",
                "content": assistant_msg.content,
                "tool_calls": (
                    [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in assistant_msg.tool_calls
                    ]
                    if assistant_msg.tool_calls
                    else None
                ),
            }
        )

        if not assistant_msg.tool_calls:
            logger.info("No tool calls. Done.")
            return assistant_msg.content or "Task completed."

        logger.info(f"Executing {len(assistant_msg.tool_calls)} tool(s)")
        for tool_call in assistant_msg.tool_calls:
            fn_name = tool_call.function.name
            fn_args = json.loads(tool_call.function.arguments)
            logger.info(f"Tool: {fn_name} | Args: {fn_args}")

            result = await call_mcp_tool(mcp_session, fn_name, fn_args)
            logger.debug(f"Result: {result}")

            if "error" in result:
                result_msg = f"Error: {result['error']}"
            else:
                result_msg = f"Command: {result.get('command', 'N/A')}\n"
                result_msg += f"Exit code: {result.get('returncode', 'N/A')}\n"
                if result.get("stdout"):
                    result_msg += f"Output:\n{result['stdout']}"
                if result.get("stderr"):
                    result_msg += f"Error:\n{result['stderr']}"

            messages.append(
                {"role": "tool", "tool_call_id": tool_call.id, "content": result_msg}
            )

    return "Task completed (reached iteration limit)."
