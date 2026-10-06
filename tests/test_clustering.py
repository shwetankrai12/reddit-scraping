from pain_radar.clustering.embedder import ProblemEmbedder
from pain_radar.clustering.clusterer import ProblemClusterer
from pain_radar.storage.db import Database
from pain_radar.storage.models import PainSignalRecord, RedditPostModel


def test_problem_clustering(tmp_path):
    db = Database(tmp_path / "test.db")
    embedder = ProblemEmbedder("all-MiniLM-L6-v2")

    # Add posts
    db.save_post(RedditPostModel(post_id="p1", subreddit="SaaS", title="Post 1", permalink="https://reddit.com/1"))
    db.save_post(RedditPostModel(post_id="p2", subreddit="startups", title="Post 2", permalink="https://reddit.com/2"))
    db.save_post(RedditPostModel(post_id="p3", subreddit="marketing", title="Post 3", permalink="https://reddit.com/3"))

    # Two similar problems regarding invoice reconciliation
    sig1 = PainSignalRecord(
        signal_id="s1",
        post_id="p1",
        subreddit="SaaS",
        reddit_url="https://reddit.com/1",
        is_real_problem=True,
        pain_level=4,
        recurring_problem=True,
        manual_workaround=True,
        existing_solution_failure=True,
        purchase_signal=False,
        switching_signal=False,
        problem_type="manual_work",
        problem_statement="Manual invoice reconciliation takes hours every Friday in Excel.",
        target_user="Bookkeepers",
        current_workaround="Excel",
        why_painful="Time waste",
        confidence=0.9,
        original_text="text 1",
    )
    sig2 = PainSignalRecord(
        signal_id="s2",
        post_id="p2",
        subreddit="startups",
        reddit_url="https://reddit.com/2",
        is_real_problem=True,
        pain_level=5,
        recurring_problem=True,
        manual_workaround=True,
        existing_solution_failure=False,
        purchase_signal=True,
        switching_signal=False,
        problem_type="manual_work",
        problem_statement="QuickBooks and Stripe reconciliation is broken and requires manual matching.",
        target_user="Bookkeepers",
        current_workaround="Spreadsheets",
        why_painful="Errors",
        confidence=0.92,
        original_text="text 2",
    )
    # One completely different problem (SEO keyword research)
    sig3 = PainSignalRecord(
        signal_id="s3",
        post_id="p3",
        subreddit="marketing",
        reddit_url="https://reddit.com/3",
        is_real_problem=True,
        pain_level=2,
        recurring_problem=False,
        manual_workaround=False,
        existing_solution_failure=False,
        purchase_signal=False,
        switching_signal=False,
        problem_type="workflow_friction",
        problem_statement="Finding long-tail SEO keywords is confusing for beginner bloggers.",
        target_user="Bloggers",
        current_workaround="Google search",
        why_painful="Low traffic",
        confidence=0.8,
        original_text="text 3",
    )

    db.save_pain_signal(sig1)
    db.save_pain_signal(sig2)
    db.save_pain_signal(sig3)

    clusterer = ProblemClusterer(db, embedder, distance_threshold=0.58, min_cluster_size=2)
    results = clusterer.cluster_pain_signals()

    assert len(results) >= 2
    # Find the cluster with invoice reconciliation
    invoice_clusters = [c for c, _ in results if "reconciliation" in c.normalized_problem.lower() or "quickbooks" in c.normalized_problem.lower()]
    assert len(invoice_clusters) == 1
    inv_cluster = invoice_clusters[0]
    assert inv_cluster.mention_count == 2
    assert inv_cluster.unique_discussions == 2
    assert inv_cluster.insufficient_evidence is False
