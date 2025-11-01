# -*- coding: utf-8 -*-

import json
import sys
from pathlib import Path
import agentbeats as ab

from tau_bench.envs import get_env

# Add the repo root to Python path so we can import from src
_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

# Reuse the existing, code-driven orchestration logic
from src.green_agent.agent import ask_agent_to_solve


@ab.tool
async def start_tau_battle(battle_start_json: str) -> str:
    """
    Code-driven entrypoint for Tau-bench evaluation.

    Args:
        battle_start_json: JSON string provided by AgentBeats backend on battle start.

    Behavior:
        - Parses battle_id, backend_url, task_config and the participant (white/red) agent URL
        - Instantiates Tau-bench env using task_config
        - Calls the existing ask_agent_to_solve(...) loop against the participant agent
        - Returns a compact JSON result string { ok, battle_id, success, metrics }
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

        # Prefer new format red_battle_contexts { url: context }
        red_ctx_map = data.get("red_battle_contexts", {})
        if red_ctx_map:
            # pick the first participant
            white_agent_url = next(iter(red_ctx_map.keys()))
        else:
            # Fallback to legacy opponent_infos
            opps = data.get("opponent_infos", [])
            white_agent_url = opps[0]["agent_url"] if opps else None

        # Parse task_config with sensible defaults (like other scenarios)
        # Default configuration (self-contained, no external dependency)
        default_task_config = {
            "env": "retail",
            "user_strategy": "llm",
            "user_model": "openai/gpt-4o",
            "user_provider": "openai",
            "task_split": "test",
            "task_ids": [1],
        }

        # Extract task_config from battle payload
        raw_task_config = green_ctx.get("task_config", "")
        
        # Handle string format (backend may send "Task description: {...}" or just JSON)
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
                    # If not JSON, might be a task index number or description
                    # Try to extract task index if it's a simple number
                    try:
                        task_idx = int(raw_str)
                        parsed_config = {"task_ids": [task_idx]}
                    except ValueError:
                        # If all parsing fails, use defaults
                        parsed_config = {}
        elif isinstance(raw_task_config, dict):
            parsed_config = raw_task_config

        # Merge defaults with provided overrides (provided values take precedence)
        task_config = {**default_task_config, **parsed_config}
        
        # Ensure task_ids is a non-empty list
        if not task_config.get("task_ids") or not isinstance(task_config["task_ids"], list):
            task_config["task_ids"] = [1]  # fallback to default task

        task_index = task_config["task_ids"][0]

        # Instantiate Tau-bench environment with merged config
        env = get_env(
            env_name=task_config["env"],
            user_strategy=task_config["user_strategy"],
            user_model=task_config["user_model"],
            task_split=task_config["task_split"],
            user_provider=task_config.get("user_provider"),
            task_index=task_index,
        )

        # Run the existing code-driven loop
        res = await ask_agent_to_solve(white_agent_url, env, task_index, max_num_steps=30)
        success = (res.reward == 1)
        
        # Report result to AgentBeats backend
        try:
            import requests
            from datetime import datetime
            
            # Get actual backend_url from context if available
            try:
                from agentbeats.logging import get_backend_url
                actual_backend_url = get_backend_url()
            except:
                actual_backend_url = None
                
            actual_backend_url = actual_backend_url or backend_url
            
            # Determine winner - red/white agent wins if successful, green wins otherwise
            winner = "white_agent" if success else "green_agent"
            
            # Report to backend
            result_data = {
                "is_result": True,
                "message": "Tau-bench evaluation completed",
                "winner": winner,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "reported_by": "Tau Green Agent",
                "detail": {
                    "success": success,
                    "task_config": task_config,
                    "participant_url": white_agent_url,
                    "metrics": {
                        "total_cost": getattr(res, "total_cost", None),
                    },
                },
            }
            
            response = requests.post(
                f"{actual_backend_url}/battles/{battle_id}",
                json=result_data,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 204:
                print(f"[Tau-Bench] Successfully reported battle result: winner={winner}")
            else:
                print(f"[Tau-Bench] Failed to report battle result: {response.text}")
                
        except Exception as report_error:
            print(f"[Warning] Failed to report battle end: {report_error}")
            # Continue even if reporting fails

        return json.dumps({
            "ok": True,
            "battle_id": battle_id,
            "backend_url": backend_url,
            "participant_url": white_agent_url,
            "success": success,
            "metrics": {
                # res.total_cost is maintained by the original code (currently 0.0)
                "total_cost": getattr(res, "total_cost", None),
            },
        })

    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})


