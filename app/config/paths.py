from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = PROJECT_ROOT / "cache"
JOBS_DIR = CACHE_DIR / "jobs"
MODEL_DIR = PROJECT_ROOT / "fast_rubert"
