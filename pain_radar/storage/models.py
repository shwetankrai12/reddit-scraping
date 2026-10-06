from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RedditPostModel(BaseModel):
    post_id: str
    subreddit: str
    title: str
    body: str = ""
    timestamp: str = ""
    score: int = 0
    comment_count: int = 0
    permalink: str
    post_type: str = "text"
    discovery_source: str = "feed"
    created_at: str = Field(default_factory=_now_iso)


class RedditCommentModel(BaseModel):
    comment_id: str
    post_id: str
    body: str = ""
    timestamp: str = ""
    score: int = 0
    parent_id: Optional[str] = None
    created_at: str = Field(default_factory=_now_iso)


class PainSignalRecord(BaseModel):
    signal_id: str
    post_id: str
    subreddit: str
    reddit_url: str
    is_real_problem: bool
    pain_level: int
    recurring_problem: bool
    manual_workaround: bool
    existing_solution_failure: bool
    purchase_signal: bool
    switching_signal: bool
    problem_type: str
    problem_statement: str
    target_user: str
    current_workaround: str
    why_painful: str
    confidence: float
    original_text: str
    created_at: str = Field(default_factory=_now_iso)


class ClusterEvidenceRecord(BaseModel):
    cluster_id: str
    signal_id: str
    reddit_url: str
    subreddit: str
    post_id: str
    original_text: str
    similarity_score: float = 1.0


class ProblemClusterRecord(BaseModel):
    cluster_id: str
    normalized_problem: str
    target_user: str
    category: str
    mention_count: int = 0
    unique_discussions: int = 0
    unique_subreddits: int = 0
    avg_engagement: float = 0.0
    recency_days: float = 0.0
    growth_rate: float = 0.0
    trend_label: str = "NEW"
    manual_workaround_rate: float = 0.0
    existing_failure_rate: float = 0.0
    purchase_signal_rate: float = 0.0
    switching_signal_rate: float = 0.0
    avg_pain_level: float = 0.0
    pain_score: float = 0.0
    score_breakdown: Dict[str, Any] = Field(default_factory=dict)
    insufficient_evidence: bool = False
    evidence_urls: List[str] = Field(default_factory=list)
    synthesis: Optional[Dict[str, Any]] = None
    created_at: str = Field(default_factory=_now_iso)
