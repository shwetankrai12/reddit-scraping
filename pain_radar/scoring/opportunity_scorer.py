import json
import logging
import math
from typing import Any, Dict, List
from pain_radar.scoring.trends import TrendDetector
from pain_radar.storage.db import Database
from pain_radar.storage.models import ProblemClusterRecord

logger = logging.getLogger(__name__)


class OpportunityScorer:
    def __init__(self, db: Database, weights: Dict[str, float], window_days: int = 30):
        self.db = db
        self.weights = weights
        self.trend_detector = TrendDetector(window_days=window_days)

    def score_cluster(
        self,
        cluster: ProblemClusterRecord,
        timestamps: List[str]
    ) -> ProblemClusterRecord:
        # 1. Trend detection
        trend_label, growth_rate, audit_counts = self.trend_detector.evaluate_trend(timestamps)
        cluster.trend_label = trend_label
        cluster.growth_rate = growth_rate

        # 2. Normalized component signals [0.0 - 1.0]
        # Frequency (scale to 25 mentions)
        s_frequency = min(1.0, cluster.mention_count / 25.0)

        # Unique discussions (scale to 15 unique posts)
        s_discussions = min(1.0, cluster.unique_discussions / 15.0)

        # Subreddit diversity (scale to 5 subreddits)
        s_diversity = min(1.0, cluster.unique_subreddits / 5.0)

        # Engagement (log scaled, cap at 100 upvotes)
        s_engagement = min(1.0, math.log1p(max(0, cluster.avg_engagement)) / math.log1p(100.0))

        # Recency (30 days decay)
        s_recency = max(0.0, min(1.0, 1.0 - (cluster.recency_days / 30.0)))

        # Growth signal
        s_growth = min(1.0, max(0.0, (growth_rate + 0.2) / 1.5))

        # Workaround intensity (direct rate)
        s_workaround = min(1.0, max(0.0, cluster.manual_workaround_rate))

        # Existing solution dissatisfaction
        s_dissatisfaction = min(1.0, max(0.0, cluster.existing_failure_rate))

        # Purchase / Switching signals
        s_intent = min(1.0, max(0.0, (cluster.purchase_signal_rate + cluster.switching_signal_rate) / 2.0))

        # Weighted calculation
        raw_score = (
            self.weights.get("frequency", 0.25) * s_frequency
            + self.weights.get("unique_discussions", 0.15) * s_discussions
            + self.weights.get("subreddit_diversity", 0.10) * s_diversity
            + self.weights.get("engagement", 0.10) * s_engagement
            + self.weights.get("recency", 0.10) * s_recency
            + self.weights.get("growth", 0.10) * s_growth
            + self.weights.get("workaround_intensity", 0.10) * s_workaround
            + self.weights.get("existing_solution_dissatisfaction", 0.05) * s_dissatisfaction
            + self.weights.get("purchase_switching_signals", 0.05) * s_intent
        )

        pain_score = round(min(100.0, max(0.0, raw_score * 100.0)), 1)
        cluster.pain_score = pain_score

        cluster.score_breakdown = {
            "components": {
                "frequency": round(s_frequency, 3),
                "unique_discussions": round(s_discussions, 3),
                "subreddit_diversity": round(s_diversity, 3),
                "engagement": round(s_engagement, 3),
                "recency": round(s_recency, 3),
                "growth": round(s_growth, 3),
                "workaround_intensity": round(s_workaround, 3),
                "existing_solution_dissatisfaction": round(s_dissatisfaction, 3),
                "purchase_switching_signals": round(s_intent, 3),
            },
            "weights": self.weights,
            "trend_audit": audit_counts,
            "final_score": pain_score,
        }

        return cluster

    def score_all_clusters(self) -> List[Dict[str, Any]]:
        logger.info("Scoring all problem clusters deterministically...")
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM problem_clusters")
            rows = cursor.fetchall()

        updated_clusters = []
        for r in rows:
            c_dict = dict(r)
            # Retrieve timestamps of all evidence signals for this cluster
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                SELECT p.timestamp, s.created_at
                FROM cluster_evidence e
                JOIN pain_signals s ON e.signal_id = s.signal_id
                LEFT JOIN reddit_posts p ON s.post_id = p.post_id
                WHERE e.cluster_id = ?
                """, (c_dict["cluster_id"],))
                ts_rows = cursor.fetchall()
                timestamps = [row[0] or row[1] for row in ts_rows]

            cluster_model = ProblemClusterRecord(**{
                k: v for k, v in c_dict.items()
                if k not in ("score_breakdown", "synthesis_json", "evidence_urls")
            })

            scored_cluster = self.score_cluster(cluster_model, timestamps)

            # Update in DB
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                UPDATE problem_clusters
                SET pain_score = ?,
                    trend_label = ?,
                    growth_rate = ?,
                    score_breakdown = ?
                WHERE cluster_id = ?
                """, (
                    scored_cluster.pain_score,
                    scored_cluster.trend_label,
                    scored_cluster.growth_rate,
                    json.dumps(scored_cluster.score_breakdown),
                    scored_cluster.cluster_id,
                ))
                conn.commit()

            updated_clusters.append(scored_cluster)

        logger.info(f"Scored {len(updated_clusters)} problem clusters.")
        return updated_clusters
