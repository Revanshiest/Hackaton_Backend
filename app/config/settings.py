from dataclasses import dataclass, field
from pathlib import Path

from app.config.llm import OLLAMA_BASE_URL, OLLAMA_MODEL
from app.config.paths import CACHE_DIR, DATA_DIR


@dataclass
class PipelineSettings:
    input_path: Path
    output_dir: Path = field(default_factory=lambda: DATA_DIR / "output")
    cache_dir: Path = field(default_factory=lambda: CACHE_DIR)
    batch_size: int = 16
    top_municipalities: int = 10
    top_hotspots: int = 3
    examples_per_muni: int = 3
    ollama_model: str = OLLAMA_MODEL
    ollama_base_url: str = OLLAMA_BASE_URL
    skip_summary: bool = False
    nrows: int | None = None
    update_demo_snapshot: bool = True
    llm_fast_mode: bool = True
    llm_workers: int = 4
