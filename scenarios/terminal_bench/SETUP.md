# Setup Guide

Guide for installing, configuring, and building white agents for terminal-bench evaluation.

## Table of Contents

- [Quick Setup](#quick-setup)
- [Manual Installation](#manual-installation)
- [Configuration](#configuration)
- [Running Evaluations](#running-evaluations)
- [Building Your White Agent](#building-your-white-agent)

## Prerequisites

- **Python 3.10+** - `python --version`
- **Docker** - `docker ps` should work without errors
- **OpenAI API Key** - For example white agent (optional)

## Quick Setup

The fastest way to get started:

```bash
# 1. Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # macOS/Linux
# OR: venv\Scripts\activate  # Windows

# 2. Run setup script, which install dependencies and download terminal-bench dataset
bash scripts/setup.sh

# 3. Configure API key
echo "OPENAI_API_KEY=your_key_here" > .env
```

## Configuration

Edit `config.toml` to configure evaluation. Key settings:

```toml
[white_agent]
model = "gpt-4o-mini"      # LLM model
max_iterations = 30         # Max commands per task

[evaluation]
task_ids = ["hello-world", "create-bucket"]  # Tasks to run
n_attempts = 1              # Attempts per task
n_concurrent_trials = 2     # Parallel trials
timeout_multiplier = 1.0    # Adjust timeouts

[dataset]
name = "terminal-bench-core"
version = "0.1.1"

[scoring]
# Weights for computing overall weighted score
[scoring.difficulty_weights]
easy = 1
medium = 2
hard = 3
unknown = 1
# ... (see config.toml for complete list)
```

**Available tasks:** Check `~/.cache/terminal-bench/terminal-bench-core/tasks/` for all task IDs.

**Scoring Configuration:** The evaluation system computes a weighted overall score based on task difficulty. Each task gets a score from 0.0 to 1.0 (50% from test case pass rate, 50% from is_resolved status). The overall score is weighted by difficulty (easy=1, medium=2, hard=3). You can customize these weights in `config.toml` under the `[scoring]` section.

See `config.toml` for all configuration options (ports, logging, A2A settings, etc).

## Building Your White Agent

Your white agent needs three components:

1. **A2A Server** - Receives evaluation requests
2. **MCP Client** - Connects to task-scoped MCP servers
3. **Solver Logic** - Executes bash commands to solve tasks

### Task Instruction Format

Each task includes an MCP server URL. Below is an example instruction for the "hello-world" task.

```
You are being evaluated on Terminal-Bench.

TASK: Create a file called hello.txt with "Hello, World!"

MCP Server URL: http://localhost:10000

ENVIRONMENT:
- Tool: execute_bash_command (parameter: command)
- Working directory: /app (Docker container)
- Each command runs in fresh shell (no state between commands)
```

### A2A Server

```python
from a2a.server.apps import A2AStarletteApplication
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import Part, TextPart
import uvicorn

class WhiteAgentExecutor(AgentExecutor):
    async def execute(self, context: RequestContext, event_queue: EventQueue):
        updater = TaskUpdater(event_queue, task.id, task.context_id)
        instruction = context.get_user_input()

        # Extract MCP URL and solve task
        mcp_url = extract_mcp_url(instruction)
        result = await solve_task(instruction, mcp_url)

        # Return result
        await updater.add_artifact([Part(root=TextPart(text=result))], name="response")
        await updater.complete()
```

### MCP Client

```python
from mcp.client.sse import sse_client
from mcp import ClientSession
import json

async def execute_command(mcp_url: str, command: str):
    async with sse_client(f"{mcp_url}/sse") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            result = await session.call_tool(
                "execute_bash_command",
                arguments={"command": command}
            )

            # Returns: {command, returncode, stdout, stderr}
            return json.loads(result.content[0].text)
```

### LLM Solver

```python
from openai import AsyncOpenAI

async def solve_with_llm(instruction: str, mcp_url: str, max_iterations: int = 30):
    client = AsyncOpenAI()
    messages = [{"role": "user", "content": instruction}]

    async with sse_client(f"{mcp_url}/sse") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            for _ in range(max_iterations):
                response = await client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    tools=[{
                        "type": "function",
                        "function": {
                            "name": "execute_bash_command",
                            "parameters": {"type": "object", "properties": {"command": {"type": "string"}}}
                        }
                    }]
                )

                if response.choices[0].message.tool_calls:
                    # Execute command via MCP
                    # Add result to messages
                    # Continue loop
                elif "TASK_COMPLETE" in response.choices[0].message.content:
                    return "Task completed"
```

### Reference Implementation

See complete working example:

- `white_agent/white_agent.py` - A2A server
- `white_agent/white_agent_helpers.py` - MCP client + LLM integration

## Running Evaluations

Start three terminals with the virtual environment activated:

**Terminal 1 - White Agent:**

```bash
python -m white_agent
```

**Terminal 2 - Green Agent:**

```bash
python -m src.green_agent
```

**Terminal 3 - Kickoff:**

```bash
python -m src.kickoff
```

The kickoff script validates both agents are running, then starts evaluation. Results are saved to `eval_results/green_agent_eval_TIMESTAMP/`.

**Stop evaluation:** Press `Ctrl+C` in any terminal.
