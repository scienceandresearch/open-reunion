"""Run from any working directory, without installing the package."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from openreunion.__main__ import main

if __name__ == "__main__":
    main()
