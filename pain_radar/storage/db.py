import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from pain_radar.storage.models import (
    RedditPostModel,
    RedditCommentModel,
    PainSignalRecord,
    ProblemClusterRecord,
    ClusterEvidenceRecord,
)


class Database:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Crawl Runs
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS crawl_runs (
                run_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                subreddits TEXT NOT NULL,
                total_posts INTEGER DEFAULT 0,
                total_comments INTEGER DEFAULT 0,
                status TEXT NOT NULL
            );
            """)

            # Reddit Posts
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS reddit_posts (
                post_id TEXT PRIMARY KEY,
                subreddit TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT,
                timestamp TEXT,
                score INTEGER DEFAULT 0,
                comment_count INTEGER DEFAULT 0,
                permalink TEXT NOT NULL,
                post_type TEXT DEFAULT 'text',
                discovery_source TEXT DEFAULT 'feed',
                created_at TEXT NOT NULL
            );
            """)

            # Reddit Comments
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS reddit_comments (
                comment_id TEXT PRIMARY KEY,
                post_id TEXT NOT NULL,
                body TEXT NOT NULL,
                timestamp TEXT,
                score INTEGER DEFAULT 0,
                parent_id TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (post_id) REFERENCES reddit_posts (post_id)
            );
            """)

            # Pain Signals
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS pain_signals (
                signal_id TEXT PRIMARY KEY,
                post_id TEXT NOT NULL,
                subreddit TEXT NOT NULL,
                reddit_url TEXT NOT NULL,
                is_real_problem INTEGER NOT NULL,
                pain_level INTEGER NOT NULL,
                recurring_problem INTEGER NOT NULL,
                manual_workaround INTEGER NOT NULL,
                existing_solution_failure INTEGER NOT NULL,
                purchase_signal INTEGER NOT NULL,
                switching_signal INTEGER NOT NULL,
                problem_type TEXT NOT NULL,
                problem_statement TEXT NOT NULL,
                target_user TEXT NOT NULL,
                current_workaround TEXT NOT NULL,
                why_painful TEXT NOT NULL,
                confidence REAL NOT NULL,
                original_text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (post_id) REFERENCES reddit_posts (post_id)
            );
            """)

            # Problem Clusters
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS problem_clusters (
                cluster_id TEXT PRIMARY KEY,
                normalized_problem TEXT NOT NULL,
                target_user TEXT NOT NULL,
                category TEXT NOT NULL,
                mention_count INTEGER DEFAULT 0,
                unique_discussions INTEGER DEFAULT 0,
                unique_subreddits INTEGER DEFAULT 0,
                avg_engagement REAL DEFAULT 0.0,
                recency_days REAL DEFAULT 0.0,
                growth_rate REAL DEFAULT 0.0,
                trend_label TEXT DEFAULT 'NEW',
                manual_workaround_rate REAL DEFAULT 0.0,
                existing_failure_rate REAL DEFAULT 0.0,
                purchase_signal_rate REAL DEFAULT 0.0,
                switching_signal_rate REAL DEFAULT 0.0,
                avg_pain_level REAL DEFAULT 0.0,
                pain_score REAL DEFAULT 0.0,
                score_breakdown TEXT,
                insufficient_evidence INTEGER DEFAULT 0,
                synthesis_json TEXT,
                created_at TEXT NOT NULL
            );
            """)

            # Cluster Evidence
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS cluster_evidence (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cluster_id TEXT NOT NULL,
                signal_id TEXT NOT NULL,
                reddit_url TEXT NOT NULL,
                subreddit TEXT NOT NULL,
                post_id TEXT NOT NULL,
                original_text TEXT NOT NULL,
                similarity_score REAL DEFAULT 1.0,
                FOREIGN KEY (cluster_id) REFERENCES problem_clusters (cluster_id),
                FOREIGN KEY (signal_id) REFERENCES pain_signals (signal_id)
            );
            """)

            # Indexes for performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_sub ON reddit_posts (subreddit);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_time ON reddit_posts (timestamp);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_comments_post ON reddit_comments (post_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_real ON pain_signals (is_real_problem);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_evidence_cluster ON cluster_evidence (cluster_id);")

            conn.commit()

    # Post operations
    def save_post(self, post: RedditPostModel) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO reddit_posts (
                post_id, subreddit, title, body, timestamp, score,
                comment_count, permalink, post_type, discovery_source, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(post_id) DO UPDATE SET
                title = excluded.title,
                body = excluded.body,
                score = excluded.score,
                comment_count = excluded.comment_count
            """, (
                post.post_id, post.subreddit, post.title, post.body, post.timestamp,
                post.score, post.comment_count, post.permalink, post.post_type,
                post.discovery_source, post.created_at
            ))
            conn.commit()
            return True

    def save_posts_batch(self, posts: List[RedditPostModel]) -> int:
        count = 0
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for post in posts:
                cursor.execute("""
                INSERT INTO reddit_posts (
                    post_id, subreddit, title, body, timestamp, score,
                    comment_count, permalink, post_type, discovery_source, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(post_id) DO UPDATE SET
                    title = excluded.title,
                    body = CASE WHEN excluded.body != '' THEN excluded.body ELSE reddit_posts.body END,
                    score = excluded.score,
                    comment_count = excluded.comment_count
                """, (
                    post.post_id, post.subreddit, post.title, post.body, post.timestamp,
                    post.score, post.comment_count, post.permalink, post.post_type,
                    post.discovery_source, post.created_at
                ))
                count += 1
            conn.commit()
        return count

    # Comment operations
    def save_comments_batch(self, comments: List[RedditCommentModel]) -> int:
        count = 0
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for comment in comments:
                cursor.execute("""
                INSERT INTO reddit_comments (
                    comment_id, post_id, body, timestamp, score, parent_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(comment_id) DO UPDATE SET
                    body = excluded.body,
                    score = excluded.score
                """, (
                    comment.comment_id, comment.post_id, comment.body, comment.timestamp,
                    comment.score, comment.parent_id, comment.created_at
                ))
                count += 1
            conn.commit()
        return count

    def get_all_posts(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM reddit_posts ORDER BY timestamp DESC")
            return [dict(row) for row in cursor.fetchall()]

    def get_post_comments(self, post_id: str) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM reddit_comments WHERE post_id = ? ORDER BY score DESC",
                (post_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    # Pain Signals
    def save_pain_signal(self, signal: PainSignalRecord) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO pain_signals (
                signal_id, post_id, subreddit, reddit_url, is_real_problem,
                pain_level, recurring_problem, manual_workaround,
                existing_solution_failure, purchase_signal, switching_signal,
                problem_type, problem_statement, target_user, current_workaround,
                why_painful, confidence, original_text, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(signal_id) DO UPDATE SET
                is_real_problem = excluded.is_real_problem,
                pain_level = excluded.pain_level,
                confidence = excluded.confidence
            """, (
                signal.signal_id, signal.post_id, signal.subreddit, signal.reddit_url,
                1 if signal.is_real_problem else 0, signal.pain_level,
                1 if signal.recurring_problem else 0, 1 if signal.manual_workaround else 0,
                1 if signal.existing_solution_failure else 0, 1 if signal.purchase_signal else 0,
                1 if signal.switching_signal else 0, signal.problem_type,
                signal.problem_statement, signal.target_user, signal.current_workaround,
                signal.why_painful, signal.confidence, signal.original_text, signal.created_at
            ))
            conn.commit()

    def get_real_pain_signals(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT p.*, r.timestamp as post_timestamp, r.score as post_score
            FROM pain_signals p
            LEFT JOIN reddit_posts r ON p.post_id = r.post_id
            WHERE p.is_real_problem = 1
            ORDER BY p.confidence DESC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def clear_clusters(self) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM cluster_evidence;")
            cursor.execute("DELETE FROM problem_clusters;")
            conn.commit()

    # Problem Clusters
    def save_problem_cluster(
        self,
        cluster: ProblemClusterRecord,
        evidence_list: List[ClusterEvidenceRecord]
    ) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            score_json = json.dumps(cluster.score_breakdown)
            synth_json = json.dumps(cluster.synthesis) if cluster.synthesis else None

            cursor.execute("""
            INSERT INTO problem_clusters (
                cluster_id, normalized_problem, target_user, category,
                mention_count, unique_discussions, unique_subreddits,
                avg_engagement, recency_days, growth_rate, trend_label,
                manual_workaround_rate, existing_failure_rate, purchase_signal_rate,
                switching_signal_rate, avg_pain_level, pain_score, score_breakdown,
                insufficient_evidence, synthesis_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cluster_id) DO UPDATE SET
                pain_score = excluded.pain_score,
                trend_label = excluded.trend_label,
                synthesis_json = excluded.synthesis_json
            """, (
                cluster.cluster_id, cluster.normalized_problem, cluster.target_user, cluster.category,
                cluster.mention_count, cluster.unique_discussions, cluster.unique_subreddits,
                cluster.avg_engagement, cluster.recency_days, cluster.growth_rate, cluster.trend_label,
                cluster.manual_workaround_rate, cluster.existing_failure_rate, cluster.purchase_signal_rate,
                cluster.switching_signal_rate, cluster.avg_pain_level, cluster.pain_score, score_json,
                1 if cluster.insufficient_evidence else 0, synth_json, cluster.created_at
            ))

            for ev in evidence_list:
                cursor.execute("""
                INSERT INTO cluster_evidence (
                    cluster_id, signal_id, reddit_url, subreddit, post_id, original_text, similarity_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    ev.cluster_id, ev.signal_id, ev.reddit_url, ev.subreddit, ev.post_id,
                    ev.original_text, ev.similarity_score
                ))

            conn.commit()

    def update_cluster_synthesis(self, cluster_id: str, synthesis: Dict[str, Any]) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE problem_clusters
            SET synthesis_json = ?
            WHERE cluster_id = ?
            """, (json.dumps(synthesis), cluster_id))
            conn.commit()

    def get_clusters_for_reporting(self, top_n: int = 15) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM problem_clusters
            WHERE insufficient_evidence = 0
            ORDER BY pain_score DESC
            LIMIT ?
            """, (top_n,))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                c_dict = dict(r)
                # fetch evidence URLs
                cursor.execute(
                    "SELECT reddit_url, original_text, subreddit FROM cluster_evidence WHERE cluster_id = ?",
                    (c_dict["cluster_id"],)
                )
                ev_rows = cursor.fetchall()
                c_dict["evidence"] = [dict(ev) for ev in ev_rows]
                if c_dict.get("score_breakdown"):
                    try:
                        c_dict["score_breakdown"] = json.loads(c_dict["score_breakdown"])
                    except Exception:
                        pass
                if c_dict.get("synthesis_json"):
                    try:
                        c_dict["synthesis"] = json.loads(c_dict["synthesis_json"])
                    except Exception:
                        pass
                results.append(c_dict)
            return results

    # JSONL Export
    def export_raw_jsonl(self, posts_path: Path, comments_path: Path) -> None:
        posts_path.parent.mkdir(parents=True, exist_ok=True)
        comments_path.parent.mkdir(parents=True, exist_ok=True)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM reddit_posts")
            posts = [dict(r) for r in cursor.fetchall()]

            cursor.execute("SELECT * FROM reddit_comments")
            comments = [dict(r) for r in cursor.fetchall()]

        with open(posts_path, "w", encoding="utf-8") as f:
            for p in posts:
                f.write(json.dumps(p, ensure_ascii=False) + "\n")

        with open(comments_path, "w", encoding="utf-8") as f:
            for c in comments:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
