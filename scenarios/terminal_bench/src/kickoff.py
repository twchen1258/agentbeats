"""Kickoff script to send evaluation request to green agent."""

import asyncio
import json
import sys
import httpx
from src.utils.a2a_client import send_message_to_agent
from src.config.settings import settings


async def check_agent(url: str, name: str) -> bool:
    """Check if agent is running."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{url}/.well-known/agent.json")
            if response.status_code == 200:
                print(f"✓ {name} running at {url}")
                return True
    except httpx.ConnectError:
        print(f"✗ {name} NOT running at {url}")
    except Exception as e:
        print(f"✗ {name} check failed: {e}")
    return False


async def main():
    # Load config
    task_config = {
        "task_ids": settings.eval_task_ids,
        "white_agent_url": settings.white_agent_url,
        "n_attempts": settings.eval_n_attempts,
        "n_concurrent_trials": settings.eval_n_concurrent_trials,
        "timeout_multiplier": settings.eval_timeout_multiplier,
        "dataset_name": settings.dataset_name,
        "dataset_version": settings.dataset_version,
    }

    green_url = f"http://{settings.green_agent_host}:{settings.green_agent_port}"
    white_url = task_config["white_agent_url"]

    # Check agents are running
    print("=" * 80)
    print("Terminal-Bench Evaluation Kickoff")
    print("=" * 80)
    print("\nChecking agents...\n")

    green_ok = await check_agent(green_url, "Green agent")
    white_ok = await check_agent(white_url, "White agent")

    if not green_ok:
        print("\nStart green agent: python -m src.green_agent")
        sys.exit(1)
    if not white_ok:
        print("\nStart white agent: python -m white_agent")
        sys.exit(1)

    # Show config and start evaluation
    print(f"\n✓ Both agents running. Starting evaluation...")
    print(
        f"\nConfig: {len(task_config['task_ids'])} tasks, "
        f"{task_config['n_attempts']} attempts, "
        f"{task_config['n_concurrent_trials']} concurrent\n"
    )

    message = f"""Launch terminal-bench evaluation for agent at {white_url}.

Configuration:
<task_config>
{json.dumps(task_config, indent=2)}
</task_config>

Report results including tasks attempted, resolved, accuracy, and failure modes."""

    response = await send_message_to_agent(message, green_url)

    print("=" * 80)
    print("GREEN AGENT RESPONSE:")
    print("=" * 80)
    print(response)


if __name__ == "__main__":
    asyncio.run(main())
