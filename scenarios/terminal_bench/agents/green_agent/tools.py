# -*- coding: utf-8 -*-
"""
Terminal-Bench Green Agent Tools for AgentBeats Integration

This file wraps the Terminal-Bench evaluation logic for AgentBeats platform.
The core harness logic is maintained in src/green_agent/green_agent.py
"""

import json
import sys
import logging
from pathlib import Path
import requests
from datetime import datetime

import agentbeats as ab

# Add parent directories to path for imports
_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))
if str(_repo_root / "src") not in sys.path:
    sys.path.insert(0, str(_repo_root / "src"))

from src.green_agent.green_agent import TerminalBenchGreenAgentExecutor
from src.config.settings import settings, ConfigurationError

logger = logging.getLogger(__name__)


@ab.tool
async def start_terminal_bench_battle(battle_start_json: str) -> str:
    """
    Code-driven entrypoint for Terminal-Bench evaluation.

    Args:
        battle_start_json: JSON string provided by AgentBeats backend on battle start.

    Behavior:
        - Parses battle_id, backend_url, task_config and the participant (white) agent URL
        - Runs Terminal-Bench harness with task configuration
        - Reports detailed results back to AgentBeats backend
        - Returns a compact JSON result string
    """
    try:
        data = json.loads(battle_start_json)
    except Exception as e:
        return json.dumps({"ok": False, "error": f"invalid_json: {str(e)}"})

    if data.get("type") != "battle_start":
        return json.dumps({"ok": False, "error": "not_battle_start"})

    try:
        battle_id = data["battle_id"]
        green_ctx = data.get("green_battle_context", {})
        backend_url = green_ctx.get("backend_url", "")
        
        # Get actual backend_url from context if available
        try:
            from agentbeats.logging import get_backend_url
            actual_backend_url = get_backend_url() or backend_url
        except:
            actual_backend_url = backend_url

        # Get participant URL
        red_ctx_map = data.get("red_battle_contexts", {})
        if red_ctx_map:
            white_agent_url = next(iter(red_ctx_map.keys()))
        else:
            opps = data.get("opponent_infos", [])
            white_agent_url = opps[0]["agent_url"] if opps else None

        if not white_agent_url:
            return json.dumps({"ok": False, "error": "no_participant_agent_url"})

        # Parse task_config with sensible defaults from config.toml
        try:
            default_task_config = {
                "task_ids": settings.eval_task_ids,
                "dataset_name": settings.dataset_name,
                "dataset_version": settings.dataset_version,
                "n_attempts": settings.eval_n_attempts,
                "n_concurrent_trials": settings.eval_n_concurrent_trials,
                "timeout_multiplier": settings.eval_timeout_multiplier,
            }
        except ConfigurationError:
            # Fallback if config.toml is not found or has errors
            logger.warning("Could not load config.toml, using fallback defaults")
            default_task_config = {
                "task_ids": ["hello-world"],
                "dataset_name": "terminal-bench-core",
                "dataset_version": "0.1.1",
                "n_attempts": 1,
                "n_concurrent_trials": 1,
                "timeout_multiplier": 1.0,
            }

        # Extract task_config from battle payload
        raw_task_config = green_ctx.get("task_config", "")
        
        parsed_config = {}
        if isinstance(raw_task_config, str) and raw_task_config.strip():
            raw_str = raw_task_config.strip()
            # Strip "Task description: " prefix if present
            prefix = "Task description:"
            if raw_str.startswith(prefix):
                raw_str = raw_str[len(prefix):].strip()
            # Try to parse as JSON
            if raw_str:
                try:
                    parsed_config = json.loads(raw_str)
                except json.JSONDecodeError:
                    # If parsing fails, use defaults
                    parsed_config = {}
        elif isinstance(raw_task_config, dict):
            parsed_config = raw_task_config

        # Merge defaults with provided overrides
        task_config = {**default_task_config, **parsed_config}
        
        # Ensure task_ids is a non-empty list
        if not task_config.get("task_ids") or not isinstance(task_config["task_ids"], list):
            task_config["task_ids"] = ["hello-world"]  # fallback to simple task

        # Prepare evaluation config for harness
        eval_config = {
            "white_agent_url": white_agent_url,
            "task_ids": task_config["task_ids"],
            "dataset_name": task_config["dataset_name"],
            "dataset_version": task_config["dataset_version"],
            "n_attempts": task_config["n_attempts"],
            "n_concurrent_trials": task_config["n_concurrent_trials"],
            "timeout_multiplier": task_config["timeout_multiplier"],
        }

        # Run the Terminal-Bench evaluation
        executor = TerminalBenchGreenAgentExecutor()
        results = executor.run_terminal_bench_evaluation(eval_config)

        # Format detailed results
        results_message = executor.format_results_message(results, eval_config)

        # Report to backend - detailed results instead of just winner
        try:
            result_data = {
                "is_result": True,
                "message": "Terminal-Bench evaluation completed",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "reported_by": "Terminal-Bench Green Agent",
                "detail": {
                    "accuracy": results.accuracy,
                    "n_resolved": results.n_resolved,
                    "n_unresolved": results.n_unresolved,
                    "task_config": task_config,
                    "participant_url": white_agent_url,
                },
                "markdown_content": results_message,
            }
            
            response = requests.post(
                f"{actual_backend_url}/battles/{battle_id}",
                json=result_data,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 204:
                print(f"[Terminal-Bench] Successfully reported battle result")
            else:
                print(f"[Terminal-Bench] Failed to report battle result: {response.text}")
                
        except Exception as report_error:
            print(f"[Warning] Failed to report battle end: {report_error}")
            # Continue even if reporting fails

        return json.dumps({
            "ok": True,
            "battle_id": battle_id,
            "backend_url": actual_backend_url,
            "participant_url": white_agent_url,
            "accuracy": results.accuracy,
            "n_resolved": results.n_resolved,
            "n_unresolved": results.n_unresolved,
        })

    except Exception as e:
        error_msg = f"Error during evaluation: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return json.dumps({"ok": False, "error": error_msg})

