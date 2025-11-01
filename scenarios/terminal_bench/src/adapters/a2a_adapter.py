"""A2A adapter for terminal-bench that creates task-scoped MCP servers."""

import asyncio
import logging
import time
import threading
from pathlib import Path

from terminal_bench.agents.base_agent import BaseAgent, AgentResult
from terminal_bench.agents.failure_mode import FailureMode
from terminal_bench.terminal.tmux_session import TmuxSession

from src.config import settings
from src.green_agent.task_mcp_server import create_task_mcp_server
from src.utils.a2a_client import send_message_to_agent

logger = logging.getLogger(__name__)


class A2AAdapter(BaseAgent):
    """Terminal-bench adapter that communicates with A2A agent via MCP."""

    _next_port = None
    _port_lock = None

    def __init__(self, agent_url: str, **kwargs):
        self.agent_url = agent_url
        self.mcp_base_port = kwargs.get("mcp_base_port", settings.mcp_base_port)

        if A2AAdapter._next_port is None:
            A2AAdapter._next_port = self.mcp_base_port
            A2AAdapter._port_lock = threading.Lock()

        logger.info(
            f"A2AAdapter initialized: {agent_url}, MCP port: {self.mcp_base_port}"
        )

    @classmethod
    def name(cls) -> str:
        return "a2a-agent"

    def _format_message(self, instruction: str, mcp_url: str) -> str:
        """Format task instruction with MCP details."""
        return f"""You are being evaluated on Terminal-Bench.

TASK: {instruction}

MCP Server URL: {mcp_url}

ENVIRONMENT:
- Tool: execute_bash_command (parameter: command)
- Working Dir: /app (inside Docker container)

Connect to MCP, execute bash commands to complete the task."""

    async def _send_to_agent(self, message: str) -> str:
        """Send message to A2A agent."""
        try:
            logger.info(f"Sending to {self.agent_url}")
            response = await send_message_to_agent(message, self.agent_url)
            logger.info(f"Received {len(response)} chars")
            return response
        except Exception as e:
            logger.error(f"Agent error: {e}")
            return f"Error: {str(e)}"

    def perform_task(
        self, instruction: str, session: TmuxSession, logging_dir: Path
    ) -> AgentResult:
        """Perform task by creating MCP server and sending to A2A agent."""
        container = session.container.name

        # Allocate unique port for this task
        with A2AAdapter._port_lock:
            port = A2AAdapter._next_port
            A2AAdapter._next_port += 1

        mcp_url = f"http://localhost:{port}"
        logger.info(f"Task: {container} on port {port}")

        # Create and start MCP server
        mcp_server = create_task_mcp_server(container, port)

        try:
            mcp_server.start()

            # Wait for server to be ready
            for i in range(20):
                if mcp_server.is_ready():
                    time.sleep(1.0)  # Extra wait for SSE endpoint
                    break
                time.sleep(0.5)

            # Send task to agent
            message = self._format_message(instruction, mcp_url)
            response = asyncio.run(self._send_to_agent(message))

            # Log interaction
            log_file = logging_dir / "agent_interaction.log"
            log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(log_file, "a") as f:
                f.write(f"\n{'='*80}\nMCP: {mcp_url} | Container: {container}\n")
                f.write(f"INSTRUCTION:\n{message}\n{'-'*80}\n")
                f.write(f"RESPONSE:\n{response}\n{'='*80}\n")

            # Check for errors
            failure = (
                FailureMode.UNKNOWN_AGENT_ERROR
                if "Error:" in response
                else FailureMode.NONE
            )

            return AgentResult(
                failure_mode=failure,
                timestamped_markers=[],
                total_input_tokens=0,
                total_output_tokens=0,
            )

        finally:
            logger.info(f"Shutting down MCP server on port {port}")
            mcp_server.shutdown()

    def cleanup(self) -> None:
        pass
