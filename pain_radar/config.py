import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = BASE_DIR / "config.yaml"

# Load .env file from project root
load_dotenv(BASE_DIR / ".env", override=True)


class AppConfig:
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self.raw_config: Dict[str, Any] = self._load_yaml()

        # Cerebras config
        self.cerebras_api_key: Optional[str] = os.getenv("CEREBRAS_API_KEY")
        self.cerebras_model: str = (
            os.getenv("CEREBRAS_MODEL")
            or self.raw_config.get("cerebras", {}).get("model", "qwen-3.8-27b")
        )
        self.cerebras_temperature: float = float(
            self.raw_config.get("cerebras", {}).get("temperature", 0.1)
        )
        self.cerebras_max_tokens: int = int(
            self.raw_config.get("cerebras", {}).get("max_tokens", 1000)
        )
        self.cerebras_timeout: float = float(
            self.raw_config.get("cerebras", {}).get("timeout_seconds", 30.0)
        )
        self.cerebras_concurrency: int = int(
            self.raw_config.get("cerebras", {}).get("concurrency", 4)
        )
        self.cerebras_max_retries: int = int(
            self.raw_config.get("cerebras", {}).get("max_retries", 3)
        )
        self.mock_mode: bool = os.getenv("CEREBRAS_MOCK_MODE", "0").lower() in ("1", "true", "yes")

        # Crawler config
        c_conf = self.raw_config.get("crawler", {})
        self.subreddits: List[str] = c_conf.get("subreddits", ["SaaS", "startups", "smallbusiness"])
        self.search_queries: List[str] = c_conf.get("search_queries", ["looking for a tool", "workaround"])
        self.default_limit: int = int(c_conf.get("default_limit_per_sub", 200))
        self.default_days: int = int(c_conf.get("default_days", 30))
        self.max_comments: int = int(c_conf.get("max_comments_per_post", 25))
        self.delay_seconds: float = float(c_conf.get("delay_seconds", 1.2))
        self.crawler_concurrency: int = int(c_conf.get("concurrency", 3))
        self.headless: bool = bool(c_conf.get("headless", True))

        # Storage paths
        s_conf = self.raw_config.get("storage", {})
        self.sqlite_path: Path = BASE_DIR / s_conf.get("sqlite_path", "data/reddit_pain_radar.db")
        self.raw_posts_jsonl: Path = BASE_DIR / s_conf.get("raw_posts_jsonl", "data/raw/posts.jsonl")
        self.raw_comments_jsonl: Path = BASE_DIR / s_conf.get("raw_comments_jsonl", "data/raw/comments.jsonl")

        # Clustering config
        cl_conf = self.raw_config.get("clustering", {})
        self.embedding_model: str = cl_conf.get("embedding_model", "all-MiniLM-L6-v2")
        self.distance_threshold: float = float(cl_conf.get("distance_threshold", 0.38))
        self.min_cluster_size: int = int(cl_conf.get("min_cluster_size", 2))

        # Scoring weights
        self.scoring_weights: Dict[str, float] = self.raw_config.get("scoring_weights", {
            "frequency": 0.25,
            "unique_discussions": 0.15,
            "subreddit_diversity": 0.10,
            "engagement": 0.10,
            "recency": 0.10,
            "growth": 0.10,
            "workaround_intensity": 0.10,
            "existing_solution_dissatisfaction": 0.05,
            "purchase_switching_signals": 0.05,
        })

        # Reports
        r_conf = self.raw_config.get("reports", {})
        self.reports_dir: Path = BASE_DIR / r_conf.get("output_dir", "reports")
        self.reports_top_n: int = int(r_conf.get("top_n", 15))

    def _load_yaml(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            return {}
        with open(self.config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def validate_cerebras(self, raise_error: bool = True) -> bool:
        """
        Validates Cerebras configuration.
        """
        if self.mock_mode:
            return True

        if not self.cerebras_api_key or not self.cerebras_api_key.strip():
            msg = (
                "CEREBRAS_API_KEY is not set or empty. "
                "Please configure CEREBRAS_API_KEY in your .env file or environment variables. "
                "To run with mock responses for testing, set CEREBRAS_MOCK_MODE=1."
            )
            if raise_error:
                raise ValueError(msg)
            return False

        if not self.cerebras_model or not self.cerebras_model.strip():
            msg = "CEREBRAS_MODEL is not set. Please set CEREBRAS_MODEL (e.g. qwen-3.8-27b)."
            if raise_error:
                raise ValueError(msg)
            return False

        return True


config = AppConfig()
