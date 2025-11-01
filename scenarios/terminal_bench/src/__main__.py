"""
Entry point for running kickoff script as a module.
"""

import asyncio
from src.kickoff import main

if __name__ == "__main__":
    asyncio.run(main())
