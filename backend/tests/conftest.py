import os
import sys
import tempfile
from pathlib import Path

# Offline, isolated test run: replay cache only (no live API calls), throwaway memory DB.
os.environ["LLM_MODE"] = "replay"
os.environ["LLM_CACHE_DIR"] = tempfile.mkdtemp(prefix="unclaimed-cache-")
os.environ["MEMORY_DB"] = str(Path(tempfile.mkdtemp(prefix="unclaimed-mem-")) / "memory.db")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
