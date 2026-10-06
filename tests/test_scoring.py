from pain_radar.scoring.opportunity_scorer import OpportunityScorer
from pain_radar.storage.models import ProblemClusterRecord
from pain_radar.storage.db import Database


def test_deterministic_scoring(tmp_path):
    db = Database(tmp_path / "test.db")
    weights = {
        "frequency": 0.25,
        "unique_discussions": 0.15,
        "subreddit_diversity": 0.10,
        "engagement": 0.10,
        "recency": 0.10,
        "growth": 0.10,
        "workaround_intensity": 0.10,
        "existing_solution_dissatisfaction": 0.05,
        "purchase_switching_signals": 0.05,
    }
    scorer = OpportunityScorer(db, weights=weights, window_days=30)

    cluster = ProblemClusterRecord(
        cluster_id="cl_1",
        normalized_problem="Small agencies struggle to collect client approvals",
        target_user="Agencies",
        category="workflow_friction",
        mention_count=20,
        unique_discussions=15,
        unique_subreddits=4,
        avg_engagement=50.0,
        recency_days=2.0,
        manual_workaround_rate=0.8,
        existing_failure_rate=0.6,
        purchase_signal_rate=0.3,
        switching_signal_rate=0.2,
        avg_pain_level=4.5,
    )

    scored = scorer.score_cluster(cluster, [])

    # Score should be between 0 and 100
    assert 0 <= scored.pain_score <= 100
    assert scored.pain_score > 50  # Strong signals should score well
    breakdown = scored.score_breakdown
    assert "components" in breakdown
    assert "frequency" in breakdown["components"]
    assert "workaround_intensity" in breakdown["components"]
    assert breakdown["final_score"] == scored.pain_score
