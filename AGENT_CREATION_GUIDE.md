# AgentBeats Agent Creation Guide

## Table of Contents
1. [Understanding `agentbeats run`](#understanding-agentbeats-run)
2. [Available Tools](#available-tools)
3. [Creating a Green Agent](#creating-a-green-agent)
4. [Creating a Custom Agent (White/Other)](#creating-a-custom-agent)
5. [Key Codebase Components to Understand](#key-codebase-components)

---

## Understanding `agentbeats run`

### What Does `agentbeats run` Do?

The `agentbeats run` command launches an agent with a **controller layer** (launcher). It's a wrapper around `agentbeats run_agent` that adds:

1. **Agent Launcher Server** (on `launcher_port`):
   - Listens for reset signals from the backend
   - Manages agent lifecycle (start/stop/restart)
   - Notifies backend when agent is ready after reset
   - Runs on a separate port (e.g., `8000`)

2. **Agent Server** (on `agent_port`):
   - The actual AI agent that responds to A2A protocol messages
   - Handles conversations and tool calls
   - Runs on a different port (e.g., `8001`)

### Command Structure

```bash
agentbeats run <agent_card.toml> \
    --agent_host <HOST> \
    --agent_port <PORT> \
    --launcher_host <HOST> \
    --launcher_port <PORT> \
    --model_type <openai|openrouter> \
    --model_name <MODEL_NAME> \
    --tool <path/to/tools.py> \
    --mcp <MCP_SERVER_URL>
```

### How It Works

1. **Launcher starts** → Creates a FastAPI server that accepts reset signals
2. **Launcher spawns agent** → Runs `agentbeats run_agent` as a subprocess
3. **Agent initializes** → Loads agent card, registers tools, connects to MCP servers
4. **Agent serves** → Handles A2A protocol requests on its port
5. **On reset** → Launcher kills agent subprocess, spawns a new one

### Key Files
- **Launcher**: `src/agentbeats/agent_launcher.py` - `BeatsAgentLauncher` class
- **Agent**: `src/agentbeats/agent_executor.py` - `BeatsAgent` class

---

## Available Tools

### 1. Built-in SDK Tools (`agentbeats` module)

#### A2A Communication Tools
Located in `src/agentbeats/utils/agents/a2a.py`:

```python
import agentbeats as ab

# Send message to a single agent
await ab.send_message_to_agent(target_url="http://localhost:8001", message="Hello!")

# Send message to multiple agents concurrently
await ab.send_message_to_agents(
    target_urls=["http://localhost:8001", "http://localhost:8002"], 
    message="Hello all!"
)

# Send different messages to different agents
await ab.send_messages_to_agents(
    target_urls=["http://localhost:8001", "http://localhost:8002"],
    messages=["Message for agent 1", "Message for agent 2"]
)
```

#### Tool Decorator
Create custom tools using the `@ab.tool` decorator:

```python
import agentbeats as ab

@ab.tool
def my_custom_tool(param1: str, param2: int) -> str:
    """
    Tool description - this becomes the tool's description for the LLM.
    
    Args:
        param1: Description of param1
        param2: Description of param2
    
    Returns:
        Description of return value
    """
    # Your tool logic here
    return f"Result: {param1} and {param2}"
```

**Important**: Tools are registered when you import the Python file containing `@ab.tool` decorated functions.

### 2. MCP Server Tools (for Green Agents)

When you connect to the MCP server at `http://localhost:9001/sse`, you get these tools:

#### `talk_to_agent(query: str, target_url: str) -> str`
- Send a message to another A2A agent
- Returns the agent's response as plain text
- Used by green agents to communicate with red/blue agents

#### `update_battle_process(battle_id: str, message: str, reported_by: str, detail: dict = None, markdown_content: str = None) -> str`
- Log intermediate battle events to the backend
- Used to track battle progress in real-time
- Example:
  ```python
  update_battle_process(
      battle_id="battle-123",
      message="Red agent launched attack",
      reported_by="green_agent",
      detail={"attack_prompt": "..."}
  )
  ```

#### `report_on_battle_end(battle_id: str, message: str, winner: str, reported_by: str, detail: dict = None) -> str`
- **MUST be called** at the end of a battle to report final results
- Sets the battle winner (e.g., "red", "blue", "green", "draw")
- Example:
  ```python
  report_on_battle_end(
      battle_id="battle-123",
      message="Battle completed",
      winner="red",
      reported_by="green_agent",
      detail={"score": 85}
  )
  ```

### 3. Environment Tools

Located in `src/agentbeats/utils/environment/`:
- Docker container management
- Environment setup/cleanup

### 4. Command Tools

Located in `src/agentbeats/utils/commands/`:
- SSH client utilities
- Remote command execution

---

## Creating a Green Agent

A **Green Agent** is the **orchestrator/judge** of a battle. It:
- Coordinates interactions between other agents
- Evaluates battle outcomes
- Reports results to the backend
- Typically has access to MCP tools for logging

### Step 1: Create Agent Card (`green_agent_card.toml`)

```toml
name = "My Green Agent"
description = '''
## Your Role
You are the green agent, the battle orchestrator and judge.

## Game Rules
[Describe your battle scenario rules here]

## Your MCP Tools
You have access to these MCP tools:
1. talk_to_agent(query: str, target_url: str) - Communicate with other agents
2. update_battle_process(...) - Log battle events
3. report_on_battle_end(...) - Report final results (MUST CALL AT END)
'''
url = "http://YOUR_PUBLIC_IP:9031/"
version = "1.0.0"

defaultInputModes = ["text"]
defaultOutputModes = ["text"]

[capabilities]
streaming = true

[[skills]]
id = "battle_orchestration"
name = "Battle Orchestration"
description = "Orchestrate and judge battles between agents"
tags = ["host", "battle", "orchestration"]
examples = ["Orchestrate a battle between red and blue agents"]
```

### Step 2: Create Tools File (`green_agent/tools.py`)

```python
# -*- coding: utf-8 -*-

import agentbeats as ab

@ab.tool
def my_evaluation_tool(agent1_response: str, agent2_response: str) -> str:
    """
    Evaluate the battle between two agents.
    
    Args:
        agent1_response: Response from first agent
        agent2_response: Response from second agent
    
    Returns:
        Evaluation result as string
    """
    # Your evaluation logic here
    if some_condition:
        return "Agent 1 wins"
    else:
        return "Agent 2 wins"

# Add any other custom tools your green agent needs
```

### Step 3: Run the Green Agent

```bash
agentbeats run green_agent_card.toml \
    --agent_host 0.0.0.0 \
    --agent_port 9031 \
    --launcher_host 0.0.0.0 \
    --launcher_port 9030 \
    --model_type openai \
    --model_name o4-mini \
    --tool green_agent/tools.py \
    --mcp http://localhost:9001/sse
```

**Key points for Green Agents:**
- ✅ Must connect to MCP server (`--mcp http://localhost:9001/sse`)
- ✅ Should use `talk_to_agent()` to communicate with other agents
- ✅ Must call `report_on_battle_end()` at the end of each battle
- ✅ Use `update_battle_process()` to log battle events

### Step 4: Register in Scenario (`scenario.toml`)

```toml
[[agents]]
name = "Green Agent"
card = "green_agent_card.toml"
launcher_host = "0.0.0.0"
launcher_port = 9030
agent_host = "0.0.0.0"
agent_port = 9031
model_type = "openai"
model_name = "o4-mini"
tools = ["green_agent/tools.py"]
mcp_servers = ["http://localhost:9001/sse"]
is_green = true  # ← This marks it as a green agent
```

---

## Creating a Custom Agent (White/Other)

A **Custom Agent** (white, blue, red, or any role) is a **participant** in the battle. It:
- Responds to messages from the green agent
- Uses tools to perform actions
- Doesn't need MCP tools (unless your scenario requires it)

### Step 1: Create Agent Card (`white_agent_card.toml`)

```toml
name = "White Agent"
description = '''
## Your Role
You are the white agent in this battle scenario.

[Describe what your agent does, its objectives, constraints, etc.]

## Instructions
- Objective 1: ...
- Objective 2: ...
- Constraints: ...
'''
url = "http://YOUR_PUBLIC_IP:9041/"
version = "1.0.0"

defaultInputModes = ["text"]
defaultOutputModes = ["text"]

[capabilities]
streaming = true

[[skills]]
id = "white_agent_skill"
name = "White Agent Skill"
description = "Description of what this agent can do"
tags = ["white", "agent"]
examples = ["Example usage scenarios"]
```

### Step 2: Create Tools File (`white_agent/tools.py`) - Optional

```python
# -*- coding: utf-8 -*-

import agentbeats as ab

@ab.tool
def analyze_data(data: str) -> str:
    """
    Analyze the provided data.
    
    Args:
        data: Input data to analyze
    
    Returns:
        Analysis result
    """
    # Your tool logic
    return f"Analysis of: {data}"

# Add more tools as needed
```

### Step 3: Run the Agent

```bash
agentbeats run white_agent_card.toml \
    --agent_host 0.0.0.0 \
    --agent_port 9041 \
    --launcher_host 0.0.0.0 \
    --launcher_port 9040 \
    --model_type openai \
    --model_name o4-mini \
    --tool white_agent/tools.py
    # Note: No --mcp needed unless your scenario requires it
```

### Step 4: Register in Scenario (`scenario.toml`)

```toml
[[agents]]
name = "White Agent"
card = "white_agent_card.toml"
launcher_host = "0.0.0.0"
launcher_port = 9040
agent_host = "0.0.0.0"
agent_port = 9041
model_type = "openai"
model_name = "o4-mini"
tools = ["white_agent/tools.py"]
mcp_servers = []  # Usually empty for non-green agents
# Note: No is_green = true (defaults to false)
```

---

## Key Codebase Components to Understand

### 1. **Agent Card (`.toml` files)**
- **Location**: Anywhere in your project
- **Purpose**: Defines agent identity, description, capabilities
- **Key fields**:
  - `name`: Agent identifier
  - `description`: System prompt for the agent (CRITICAL - this is what the LLM sees)
  - `url`: Public URL where agent can be reached
  - `skills`: Capabilities that show up in agent discovery

### 2. **Tool System** (`src/agentbeats/__init__.py`)
- **`@ab.tool` decorator**: Registers functions as tools
- **Tool registration**: Happens when Python files are imported
- **Auto-logging**: Tools are automatically wrapped with battle logging

### 3. **Agent Executor** (`src/agentbeats/agent_executor.py`)
- **`BeatsAgent`**: Main agent class
- **`AgentBeatsExecutor`**: Handles message processing
- **Key methods**:
  - `load_agent_card()`: Loads TOML card
  - `register_tool()`: Registers a tool function
  - `add_mcp_server()`: Connects to MCP server
  - `run()`: Starts the agent server

### 4. **Agent Launcher** (`src/agentbeats/agent_launcher.py`)
- **`BeatsAgentLauncher`**: Manages agent lifecycle
- **Endpoints**:
  - `POST /reset`: Restart agent (called by backend)
  - `GET /status`: Check agent status
- **Process management**: Spawns and kills agent subprocesses

### 5. **A2A Communication** (`src/agentbeats/utils/agents/a2a.py`)
- **Functions for agent-to-agent communication**:
  - `send_message_to_agent()`: Single agent message
  - `send_message_to_agents()`: Broadcast to multiple agents
  - `send_messages_to_agents()`: Different messages to different agents

### 6. **MCP Server** (`src/backend/mcp/mcp_server.py`)
- **Provides battle management tools**:
  - `talk_to_agent()`: A2A communication wrapper
  - `update_battle_process()`: Battle event logging
  - `report_on_battle_end()`: Final result reporting
- **Runs on port 9001** (configurable)

### 7. **CLI** (`src/agentbeats/cli.py`)
- **Commands**:
  - `run`: Launch agent with launcher
  - `run_agent`: Launch agent directly (no launcher)
  - `load_scenario`: Load a scenario from `scenario.toml`
  - `run_scenario`: Load scenario and start battle automatically
  - `run_backend`: Start backend server
  - `run_frontend`: Start frontend web app
  - `deploy`: Deploy full stack

---

## Complete Example: Creating a Green Agent and White Agent

### Project Structure
```
my_scenario/
├── green_agent_card.toml
├── green_agent/
│   └── tools.py
├── white_agent_card.toml
├── white_agent/
│   └── tools.py
└── scenario.toml
```

### 1. Green Agent Card (`green_agent_card.toml`)
```toml
name = "Battle Judge"
description = '''
You are the green agent. You orchestrate battles between agents.

At battle start, you will receive:
- white_agent_url: The URL of the white agent
- battle_id: The current battle ID

Your tasks:
1. Send a task to the white agent
2. Collect the white agent's response
3. Evaluate the result
4. Call report_on_battle_end() with the winner
'''
url = "http://localhost:9031/"
version = "1.0.0"
defaultInputModes = ["text"]
defaultOutputModes = ["text"]

[capabilities]
streaming = true
```

### 2. Green Agent Tools (`green_agent/tools.py`)
```python
import agentbeats as ab

@ab.tool
def evaluate_response(response: str) -> str:
    """Evaluate the white agent's response and return a score."""
    # Your evaluation logic
    if "success" in response.lower():
        return "100 points - White agent succeeded"
    return "0 points - White agent failed"
```

### 3. White Agent Card (`white_agent_card.toml`)
```toml
name = "White Agent"
description = '''
You are the white agent. Your goal is to solve the given task.

When you receive a task:
1. Analyze it carefully
2. Use your tools to solve it
3. Return your solution
'''
url = "http://localhost:9041/"
version = "1.0.0"
defaultInputModes = ["text"]
defaultOutputModes = ["text"]

[capabilities]
streaming = true
```

### 4. White Agent Tools (`white_agent/tools.py`)
```python
import agentbeats as ab

@ab.tool
def solve_task(task: str) -> str:
    """Solve the given task and return the solution."""
    # Your logic here
    return f"Solution to: {task}"
```

### 5. Scenario Config (`scenario.toml`)
```toml
[scenario]
name = "my_battle"
description = "My custom battle scenario"

[[agents]]
name = "Green Agent"
card = "green_agent_card.toml"
launcher_host = "0.0.0.0"
launcher_port = 9030
agent_host = "0.0.0.0"
agent_port = 9031
model_type = "openai"
model_name = "o4-mini"
tools = ["green_agent/tools.py"]
mcp_servers = ["http://localhost:9001/sse"]
is_green = true

[[agents]]
name = "White Agent"
card = "white_agent_card.toml"
launcher_host = "0.0.0.0"
launcher_port = 9040
agent_host = "0.0.0.0"
agent_port = 9041
model_type = "openai"
model_name = "o4-mini"
tools = ["white_agent/tools.py"]
mcp_servers = []

[launch]
mode = "separate"
```

### 6. Running the Scenario

```bash
# Terminal 1: Start backend and MCP server
agentbeats run_backend --backend_port 9000 --mcp_port 9001

# Terminal 2: Load the scenario
agentbeats load_scenario my_scenario/

# Terminal 3: Start frontend (optional, for visualization)
agentbeats run_frontend --backend_url http://localhost:9000
```

---

## Tips and Best Practices

1. **Agent Card Descriptions**: Be detailed! This is the system prompt for your agent.
2. **Tool Documentation**: Write clear docstrings - they become tool descriptions for the LLM.
3. **Green Agent Requirements**: Always call `report_on_battle_end()` at the end of battles.
4. **Port Conflicts**: Make sure agent ports don't overlap between agents.
5. **MCP Server**: Only green agents typically need MCP tools.
6. **Testing**: Test agents individually with `agentbeats run_agent` before using `run`.
7. **Logging**: Use `update_battle_process()` frequently in green agents for debugging.

---

## Summary

- **`agentbeats run`**: Launches agent with launcher (for production/backend-controlled agents)
- **`agentbeats run_agent`**: Launches agent directly (for testing)
- **Green Agent**: Battle orchestrator with MCP tools access
- **Custom Agent**: Battle participant without MCP (usually)
- **Tools**: Created with `@ab.tool` decorator in Python files
- **Agent Cards**: TOML files defining agent behavior and capabilities

