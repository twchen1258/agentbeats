# Terminal-Bench AgentBeats Integration Guide

## Overview

Terminal-Bench has been fully integrated with AgentBeats platform:

- **Green Agent**: Fully AgentBeats-compatible with `tools.py` wrapper
- **White Agent**: Fully AgentBeats-compatible with `tools.py` wrapper

Both agents now use AgentBeats' standard `@ab.tool` pattern, enabling full integration with the AgentBeats platform including `load_scenario` and `run_scenario` commands.

## Architecture

```
AgentBeats Backend
       ↓ battle_start
Green Agent (tools.py) → TerminalBenchGreenAgentExecutor → Terminal-Bench Harness
       ↓ A2A message
White Agent (tools.py) → solve_terminal_bench_task → MCP Server (task-scoped)
       ↓ bash commands
Docker Container (per task)
```

## Integration Details

### 1. Green Agent (`agents/green_agent/tools.py`)

The green agent wraps the original `TerminalBenchGreenAgentExecutor` in an `@ab.tool`:

- **Entrypoint**: `start_terminal_bench_battle(battle_start_json: str)`
- **Functionality**:
  - Parses `battle_start` JSON from AgentBeats backend
  - Extracts participant agent URL and task configuration
  - Runs Terminal-Bench harness
  - Reports detailed results back to backend (including formatted message)
- **Key Feature**: Maintains code-driven approach - all harness logic preserved

### 2. White Agent (`agents/white_agent/tools.py`)

The white agent is now fully integrated with AgentBeats:

- **Tool**: `solve_terminal_bench_task(task_message: str)`
- **Functionality**:
  - Extracts MCP server URL from Terminal-Bench plain text messages
  - Connects dynamically to task-scoped MCP servers
  - Uses existing `solve_task_with_llm_and_mcp` logic
  - Returns task completion results
- **Key Feature**: Wraps existing white agent logic in `@ab.tool` for AgentBeats compatibility

The agent card description guides the LLM to automatically use this tool when receiving Terminal-Bench messages.

### 3. Configuration

**scenario.toml**:
```toml
# Green agent - AgentBeats compatible
[[agents]]
name = "Green Agent"
card = "agents/green_agent/agent_card.toml"
tools = ["agents/green_agent/tools.py"]
is_green = true

# White agent - Fully AgentBeats compatible
[[agents]]
name = "White Agent"
card = "agents/white_agent/agent_card.toml"
tools = ["agents/white_agent/tools.py"]  # Uses solve_terminal_bench_task tool
model_type = "openai"
model_name = "gpt-4o-mini"
```

**config.toml** (Terminal-Bench specific settings):
The green agent loads configuration from `config.toml` including:
- `evaluation.task_ids`: List of tasks to evaluate (default: 12 easy tasks)
- `evaluation.n_attempts`: Number of attempts per task (default: 1)
- `evaluation.n_concurrent_trials`: Concurrent trial limit (default: 1)
- `evaluation.timeout_multiplier`: Timeout multiplier (default: 1.0)
- `dataset.name`: Dataset name (default: "terminal-bench-core")
- `dataset.version`: Dataset version (default: "0.1.1")

To customize which tasks to run, edit `config.toml` in the `scenarios/terminal_bench/` directory.

**Note**: The `config.toml` file is heavily commented with usage indicators showing which settings apply to standalone mode, AgentBeats mode, or both. Settings like `green_agent.*` and `white_agent.*` are only used in standalone mode - AgentBeats uses `scenario.toml` for those.

## Running the Integration

### Option 1: AgentBeats Platform (Recommended)

1. **Install dependencies** (if not already done):
   ```bash
   pip install -r scenarios/terminal_bench/requirements.txt
   ```

2. **Set environment variables**:
   ```bash
   export OPENAI_API_KEY="your-openai-api-key"
   ```

3. **Start backend**:
   ```bash
   agentbeats run_backend
   ```

4. **Load and register agents**:
   ```bash
   agentbeats load_scenario scenarios/terminal_bench --launch-mode current --register_agents --backend http://localhost:9000
   ```

5. **Run evaluation** (or use the web UI to create battles):
   ```bash
   agentbeats run_scenario scenarios/terminal_bench --launch_mode current --backend http://localhost:9000 --frontend http://localhost:5173
   ```

Alternatively, you can register agents and create battles manually through the AgentBeats web UI after step 4.

### Option 2: Standalone (Original)

For testing without AgentBeats:
```bash
# Terminal 1
python -m white_agent

# Terminal 2  
python -m src.green_agent

# Terminal 3
python -m src.kickoff
```

## Differences from Tau-Bench

| Aspect | Tau-Bench | Terminal-Bench |
|--------|-----------|----------------|
| Green Agent | Wraps code-driven logic in tools.py | Wraps code-driven logic in tools.py ✅ |
| White Agent | Custom A2A executor | Custom A2A executor ✅ |
| Task Protocol | Dynamic prompt + JSON response | Task instruction + MCP execution |
| Winner Reporting | Simple winner (green vs red) | Detailed results (accuracy, scores, etc.) |

## Backend Reporting

The green agent reports comprehensive results:

```python
{
    "is_result": True,
    "message": "Terminal-Bench evaluation completed",
    "timestamp": "2025-01-XX...",
    "reported_by": "Terminal-Bench Green Agent",
    "detail": {
        "accuracy": 0.67,  # Overall accuracy
        "n_resolved": 8,
        "n_unresolved": 4,
        "task_config": {...},
        "participant_url": "http://..."
    },
    "markdown_content": "Terminal-Bench Evaluation Results\n..."
}
```

The `markdown_content` field contains the formatted results summary and is rendered as rich markdown in the AgentBeats frontend, preserving line breaks and formatting. It includes:
- Overall weighted score
- Scores by difficulty (Easy/Medium/Hard)
- Per-task breakdown with test results
- Token usage per task

## Checklist Answers

✅ **1. How to get (remote) agent URL / MCP server URL**
   - Agent URL: Extracted from `red_battle_contexts` in `battle_start_json`
   - MCP URL: Green agent creates task-scoped servers dynamically

✅ **2. How to access LLM API**
   - Configured via `model_type` and `model_name` in `scenario.toml`
   - Auto-loaded from environment (OPENAI_API_KEY, etc.)

✅ **3. How to report result & add traces**
   - `update_battle_process()` for traces (not currently used, but available)
   - `report_on_battle_end` via POST to backend with detailed JSON

✅ **4. Package the repo for platform hosting**
   - Existing: `requirements.txt`, `setup.sh`
   - AgentBeats: `scenario.toml`, agent cards, tools.py
   - Ready for deployment ✅

## Notes

- Both agents are now fully integrated and can be launched via `load_scenario`
- Agents are automatically managed by AgentBeats (launcher handles restarts)
- Evaluation results are saved to `eval_results/` directory
- The white agent's `solve_terminal_bench_task` tool automatically handles dynamic MCP connections per task

