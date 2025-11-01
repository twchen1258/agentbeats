# -*- coding: utf-8 -*-
"""
Terminal-Bench White Agent Tools for AgentBeats Integration

This file wraps the Terminal-Bench white agent logic for AgentBeats platform.
The core task-solving logic is maintained in white_agent/white_agent_helpers.py
"""

import re
import sys
import logging
from pathlib import Path

import agentbeats as ab

# Add parent directories to path for imports
_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))
if str(_repo_root / "src") not in sys.path:
    sys.path.insert(0, str(_repo_root / "src"))

from white_agent.white_agent_helpers import connect_to_mcp, solve_task_with_llm_and_mcp
from src.config import settings
from openai import OpenAI

logger = logging.getLogger(__name__)


@ab.tool
async def solve_terminal_bench_task(task_message: str) -> str:
    """
    Solve a Terminal-Bench task by connecting to a task-scoped MCP server and executing commands.
    
    This tool should be used when you receive a Terminal-Bench evaluation message that contains:
    - A TASK description
    - An MCP Server URL
    
    The message format is:
    "You are being evaluated on Terminal-Bench.
    
    TASK: [task description]
    
    MCP Server URL: [url]
    
    ENVIRONMENT: ..."
    
    Args:
        task_message: The full Terminal-Bench task message containing the task and MCP URL
        
    Returns:
        A string describing the task completion status and results
    """
    # Extract MCP server URL from user input
    mcp_match = re.search(r"MCP Server URL: (.+)", task_message)
    if not mcp_match:
        return "Error: MCP Server URL not found in task message. Expected format: 'MCP Server URL: [url]'"
    
    mcp_url = mcp_match.group(1).strip()
    logger.info(f"Connecting to MCP server: {mcp_url}")
    
    # Initialize OpenAI client
    client = OpenAI(api_key=settings.openai_api_key)
    model = settings.white_agent_model
    
    try:
        # Connect to MCP server and solve task
        async with connect_to_mcp(mcp_url) as mcp_session:
            response = await solve_task_with_llm_and_mcp(
                task_message,
                mcp_session,
                client,
                model,
                settings.agent_max_iterations,
            )
        logger.info(f"Task completed successfully")
        return response
    except Exception as e:
        error_msg = f"Error solving task: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return error_msg

