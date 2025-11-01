#!/usr/bin/env python3
"""Download terminal-bench dataset if not already present."""

import subprocess
import sys
from pathlib import Path

DATASET = "terminal-bench-core"


def main():
    # Check if dataset already exists
    cache_dir = Path.home() / ".cache" / "terminal-bench" / DATASET
    if cache_dir.exists() and any(cache_dir.iterdir()):
        print(f"✅ Dataset '{DATASET}' already downloaded")
        return 0

    # Download dataset
    print(f"📦 Downloading dataset: {DATASET}...")
    try:
        subprocess.run(
            ["terminal-bench", "datasets", "download", "--dataset", DATASET],
            check=True,
        )
        print(f"✅ Dataset downloaded successfully")
        return 0
    except FileNotFoundError:
        print("❌ terminal-bench not installed. Run: pip install terminal-bench")
        return 1
    except subprocess.CalledProcessError:
        print("❌ Download failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
