import logging
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple
import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sklearn.metrics.pairwise import cosine_similarity

from pain_radar.clustering.embedder import ProblemEmbedder
from pain_radar.storage.db import Database
from pain_radar.storage.models import ProblemClusterRecord, ClusterEvidenceRecord

logger = logging.getLogger(__name__)


class ProblemClusterer:
    def __init__(
        self,
        db: Database,
        embedder: ProblemEmbedder,
        distance_threshold: float = 0.38,
        min_cluster_size: int = 2,
    ):
        self.db = db
        self.embedder = embedder
        self.distance_threshold = distance_threshold
        self.min_cluster_size = min_cluster_size

    def cluster_pain_signals(self) -> List[Tuple[ProblemClusterRecord, List[ClusterEvidenceRecord]]]:
        raw_signals = self.db.get_real_pain_signals()
        if not raw_signals:
            logger.info("No real pain signals found to cluster.")
            return []

        logger.info(f"Clustering {len(raw_signals)} pain signals...")

        problem_texts = [s["problem_statement"] for s in raw_signals]
        embeddings = self.embedder.embed_texts(problem_texts)

        if len(raw_signals) == 1:
            labels = [0]
        else:
            clustering = AgglomerativeClustering(
                metric="cosine",
                linkage="average",
                distance_threshold=self.distance_threshold,
                n_clusters=None,
            )
            labels = clustering.fit_predict(embeddings)

        # Group signals by label
        clusters_map: Dict[int, List[int]] = {}
        for idx, lbl in enumerate(labels):
            clusters_map.setdefault(lbl, []).append(idx)

        logger.info(f"Formed {len(clusters_map)} semantic clusters from {len(raw_signals)} signals.")

        # Clear old clusters in DB
        self.db.clear_clusters()

        results: List[Tuple[ProblemClusterRecord, List[ClusterEvidenceRecord]]] = []

        now_utc = datetime.now(timezone.utc)

        for cluster_label, item_indices in clusters_map.items():
            cluster_signals = [raw_signals[i] for i in item_indices]
            cluster_embeddings = embeddings[item_indices]

            # Compute centroid and pick central problem statement
            centroid = np.mean(cluster_embeddings, axis=0, keepdims=True)
            similarities = cosine_similarity(centroid, cluster_embeddings)[0]
            best_idx = int(np.argmax(similarities))
            representative_statement = cluster_signals[best_idx]["problem_statement"]

            # Aggregate metadata
            unique_posts = set(s["post_id"] for s in cluster_signals)
            unique_subs = set(s["subreddit"] for s in cluster_signals)
            mention_count = len(cluster_signals)
            unique_discussions = len(unique_posts)

            # Target user (most common)
            target_users = [s["target_user"] for s in cluster_signals if s.get("target_user")]
            target_user = Counter(target_users).most_common(1)[0][0] if target_users else "General Users"

            # Category / problem type
            types = [s["problem_type"] for s in cluster_signals if s.get("problem_type")]
            category = Counter(types).most_common(1)[0][0] if types else "general_pain"

            # Rates
            workaround_rate = sum(1 for s in cluster_signals if s["manual_workaround"]) / mention_count
            failure_rate = sum(1 for s in cluster_signals if s["existing_solution_failure"]) / mention_count
            purchase_rate = sum(1 for s in cluster_signals if s["purchase_signal"]) / mention_count
            switching_rate = sum(1 for s in cluster_signals if s["switching_signal"]) / mention_count
            avg_pain = sum(s["pain_level"] for s in cluster_signals) / mention_count

            # Engagement (scores)
            scores = [s.get("post_score") or 0 for s in cluster_signals]
            avg_engagement = sum(scores) / len(scores) if scores else 0.0

            # Recency in days
            recency_days_list = []
            for s in cluster_signals:
                ts = s.get("post_timestamp") or s.get("created_at") or ""
                try:
                    ts_clean = ts.replace("Z", "+00:00")
                    if len(ts_clean) > 5 and ts_clean[-5] in ("+", "-") and ":" not in ts_clean[-5:]:
                        ts_clean = ts_clean[:-2] + ":" + ts_clean[-2:]
                    dt = datetime.fromisoformat(ts_clean)
                    days_ago = (now_utc - dt).total_seconds() / 86400.0
                    recency_days_list.append(max(0.0, days_ago))
                except Exception:
                    recency_days_list.append(15.0)

            avg_recency = sum(recency_days_list) / len(recency_days_list) if recency_days_list else 15.0

            # Evidence validation
            insufficient = (unique_discussions < self.min_cluster_size)

            cluster_id = f"cl_{uuid.uuid4().hex[:10]}"
            evidence_urls = list(set(s["reddit_url"] for s in cluster_signals))

            cluster_record = ProblemClusterRecord(
                cluster_id=cluster_id,
                normalized_problem=representative_statement,
                target_user=target_user,
                category=category,
                mention_count=mention_count,
                unique_discussions=unique_discussions,
                unique_subreddits=len(unique_subs),
                avg_engagement=round(avg_engagement, 2),
                recency_days=round(avg_recency, 1),
                growth_rate=0.0,  # Will be calculated by TrendDetector
                trend_label="NEW",
                manual_workaround_rate=round(workaround_rate, 2),
                existing_failure_rate=round(failure_rate, 2),
                purchase_signal_rate=round(purchase_rate, 2),
                switching_signal_rate=round(switching_rate, 2),
                avg_pain_level=round(avg_pain, 2),
                pain_score=0.0,   # Will be calculated by Scorer
                insufficient_evidence=insufficient,
                evidence_urls=evidence_urls,
            )

            evidence_records: List[ClusterEvidenceRecord] = []
            for idx_s, sig in enumerate(cluster_signals):
                ev = ClusterEvidenceRecord(
                    cluster_id=cluster_id,
                    signal_id=sig["signal_id"],
                    reddit_url=sig["reddit_url"],
                    subreddit=sig["subreddit"],
                    post_id=sig["post_id"],
                    original_text=sig.get("original_text", "")[:600],
                    similarity_score=round(float(similarities[idx_s]), 3),
                )
                evidence_records.append(ev)

            # Save to DB
            self.db.save_problem_cluster(cluster_record, evidence_records)
            results.append((cluster_record, evidence_records))

        logger.info(f"Successfully saved {len(results)} clusters with evidence.")
        return results
