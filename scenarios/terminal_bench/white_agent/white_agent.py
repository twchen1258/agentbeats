"""LLM-powered white agent using MCP tools for terminal-bench evaluation."""

import logging
import re
import uvicorn
from openai import OpenAI
from a2a.server.apps import A2AStarletteApplication
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.types import (
    AgentCard,
    AgentCapabilities,
    AgentSkill,
    Part,
    TextPart,
    TaskState,
)
from a2a.utils import new_task, new_agent_text_message
from src.config import settings
from white_agent.white_agent_helpers import connect_to_mcp, solve_task_with_llm_and_mcp

logger = logging.getLogger(__name__)


class LLMWhiteAgentExecutor(AgentExecutor):
    """White agent that uses MCP tools to solve tasks."""

    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.white_agent_model

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        """Execute task using LLM with MCP tools."""
        task = context.current_task or new_task(context.message)
        if context.current_task is None:
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)
        await updater.update_status(
            TaskState.working,
            new_agent_text_message("Processing task...", task.context_id, task.id),
        )

        try:
            # Extract MCP server URL from user input
            user_input = context.get_user_input()
            mcp_match = re.search(r"MCP Server URL: (.+)", user_input)
            if not mcp_match:
                raise ValueError("MCP Server URL not found")

            mcp_url = mcp_match.group(1).strip()
            logger.info(f"MCP: {mcp_url}")

            # Connect to MCP server and solve task
            async with connect_to_mcp(mcp_url) as mcp_session:
                response = await solve_task_with_llm_and_mcp(
                    user_input,
                    mcp_session,
                    self.client,
                    self.model,
                    settings.agent_max_iterations,
                )

            await updater.add_artifact(
                [Part(root=TextPart(text=response))], name="response"
            )
            await updater.complete()

        except Exception as e:
            error_msg = f"Error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            await updater.add_artifact(
                [Part(root=TextPart(text=error_msg))], name="error"
            )
            await updater.failed(
                new_agent_text_message(error_msg, task.context_id, task.id)
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise NotImplementedError("cancel not supported")


def prepare_white_agent_card(url: str) -> AgentCard:
    """Create agent card."""
    return AgentCard(
        name="terminal_bench_white_agent",
        description="White agent for terminal-bench evaluation using MCP tools",
        url=url,
        version="1.0.0",
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[
            AgentSkill(
                id="terminal_task_solving",
                name="Terminal Task Solving",
                description="Solves terminal-bench tasks using MCP tools",
                tags=["terminal", "bash", "problem-solving"],
                examples=[],
            )
        ],
    )


def create_llm_white_agent_app(url: str) -> A2AStarletteApplication:
    """Create A2A application."""
    return A2AStarletteApplication(
        agent_card=prepare_white_agent_card(url),
        http_handler=DefaultRequestHandler(
            agent_executor=LLMWhiteAgentExecutor(),
            task_store=InMemoryTaskStore(),
        ),
    ).build()


def main():
    """Main entry point."""
    logging.basicConfig(
        level=getattr(logging, settings.log_level), format=settings.log_format
    )

    url = f"http://{settings.white_agent_host}:{settings.white_agent_port}"
    print(f"Starting White Agent at {url} | Model: {settings.white_agent_model}\n")

    app = create_llm_white_agent_app(url)
    uvicorn.run(app, host=settings.white_agent_host, port=settings.white_agent_port)


if __name__ == "__main__":
    main()
