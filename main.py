import argparse
import logging
import sys
from pathlib import Path

# Ensure UTF-8 stdout on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

from pain_radar.config import config
from pain_radar.storage.db import Database
from pain_radar.crawler.reddit_spider import RedditSpider
from pain_radar.preprocessing.cleaner import Preprocessor
from pain_radar.ai.cerebras_client import CerebrasClient
from pain_radar.ai.pass1_classifier import Pass1Classifier
from pain_radar.ai.pass2_synthesizer import Pass2Synthesizer
from pain_radar.clustering.embedder import ProblemEmbedder
from pain_radar.clustering.clusterer import ProblemClusterer
from pain_radar.scoring.opportunity_scorer import OpportunityScorer
from pain_radar.reporting.report_generator import ReportGenerator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("pain_radar")


def get_db() -> Database:
    return Database(config.sqlite_path)


def cmd_crawl(args: argparse.Namespace) -> None:
    db = get_db()
    subreddits = [s.strip() for s in args.subreddits.split(",")] if args.subreddits else config.subreddits
    spider = RedditSpider(
        db=db,
        subreddits=subreddits,
        search_queries=config.search_queries,
        limit_per_sub=args.limit,
        days=args.days,
        max_comments=args.max_comments,
        delay_seconds=args.delay,
        headless=config.headless,
    )
    result = spider.run_crawl()
    db.export_raw_jsonl(config.raw_posts_jsonl, config.raw_comments_jsonl)
    print(f"\nCrawl complete. Posts: {result['posts_count']}, Comments: {result['comments_count']}")


def cmd_analyze(args: argparse.Namespace) -> None:
    db = get_db()
    if args.mock_ai:
        config.mock_mode = True
    else:
        config.validate_cerebras()

    client = CerebrasClient(config)
    preprocessor = Preprocessor(db)
    candidates = preprocessor.prepare_post_candidates()
    print(f"\nPrepared {len(candidates)} candidates for AI analysis.")

    classifier = Pass1Classifier(db, client, concurrency=args.concurrency or config.cerebras_concurrency)
    res = classifier.classify_batch(candidates)
    print(f"\nAnalysis complete. Real problems identified: {res['real_problems']} / {res['total_candidates']}")


def cmd_cluster(args: argparse.Namespace) -> None:
    db = get_db()
    embedder = ProblemEmbedder(config.embedding_model)
    clusterer = ProblemClusterer(
        db=db,
        embedder=embedder,
        distance_threshold=config.distance_threshold,
        min_cluster_size=config.min_cluster_size,
    )
    results = clusterer.cluster_pain_signals()
    print(f"\nClustering complete. Formed {len(results)} clusters.")


def cmd_score(args: argparse.Namespace) -> None:
    db = get_db()
    scorer = OpportunityScorer(db, weights=config.scoring_weights, window_days=args.days)
    scored = scorer.score_all_clusters()
    print(f"\nScoring complete. Scored {len(scored)} clusters.")


def cmd_report(args: argparse.Namespace) -> None:
    db = get_db()
    reporter = ReportGenerator(db, output_dir=config.reports_dir, top_n=args.top or config.reports_top_n)
    paths = reporter.generate_all_reports()
    print("\nReports generated:")
    for fmt, p in paths.items():
        print(f"  {fmt.upper()}: {p}")


def cmd_run(args: argparse.Namespace) -> None:
    db = get_db()
    if args.mock_ai:
        config.mock_mode = True
    else:
        # Validate Cerebras config early before doing long crawl
        config.validate_cerebras()

    subreddits = [s.strip() for s in args.subreddits.split(",")] if args.subreddits else config.subreddits

    # 1. CRAWL
    spider = RedditSpider(
        db=db,
        subreddits=subreddits,
        search_queries=config.search_queries,
        limit_per_sub=args.limit,
        days=args.days,
        max_comments=args.max_comments,
        delay_seconds=args.delay,
        headless=config.headless,
    )
    crawl_res = spider.run_crawl()
    db.export_raw_jsonl(config.raw_posts_jsonl, config.raw_comments_jsonl)

    # 2. PREPROCESS
    preprocessor = Preprocessor(db)
    candidates = preprocessor.prepare_post_candidates()

    # 3. PASS 1 AI ANALYSIS
    client = CerebrasClient(config)
    classifier = Pass1Classifier(db, client, concurrency=args.concurrency or config.cerebras_concurrency)
    analysis_res = classifier.classify_batch(candidates)

    # 4. CLUSTERING
    embedder = ProblemEmbedder(config.embedding_model)
    clusterer = ProblemClusterer(
        db=db,
        embedder=embedder,
        distance_threshold=config.distance_threshold,
        min_cluster_size=config.min_cluster_size,
    )
    clusters = clusterer.cluster_pain_signals()

    # 5. SCORING & TRENDS
    scorer = OpportunityScorer(db, weights=config.scoring_weights, window_days=args.days)
    scorer.score_all_clusters()

    # 6. PASS 2 SYNTHESIS
    synthesizer = Pass2Synthesizer(db, client)
    synthesizer.synthesize_top_clusters(top_n=config.reports_top_n)

    # 7. REPORT GENERATION
    reporter = ReportGenerator(db, output_dir=config.reports_dir, top_n=config.reports_top_n)
    reporter.generate_all_reports()

    top_opportunities = db.get_clusters_for_reporting(top_n=config.reports_top_n)

    # Section 21 Observability Printout
    print("\n" + "=" * 50)
    print("RUN SUMMARY")
    print("=" * 50)
    print(f"Posts scraped:       {crawl_res['posts_count']}")
    print(f"Comments scraped:    {crawl_res['comments_count']}")
    print(f"Candidates analyzed: {len(candidates)}")
    print(f"Real problems:       {analysis_res['real_problems']}")
    print(f"Problem clusters:    {len(clusters)}")
    print(f"Top opportunities:   {len(top_opportunities)}")
    print("=" * 50)
    print(f"Reports saved in:    {config.reports_dir.resolve()}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="reddit-pain-radar",
        description="Evidence-backed Reddit problem discovery engine."
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Common crawl flags
    def add_crawl_flags(p):
        p.add_argument("--subreddits", type=str, help="Comma-separated list of subreddits (e.g. SaaS,startups)")
        p.add_argument("--limit", type=int, default=100, help="Max posts per subreddit")
        p.add_argument("--days", type=int, default=30, help="Time window in days")
        p.add_argument("--max-comments", type=int, default=20, help="Max comments per post")
        p.add_argument("--concurrency", type=int, default=3, help="Concurrency workers")
        p.add_argument("--delay", type=float, default=1.0, help="Delay between requests in seconds")

    # Crawl
    p_crawl = subparsers.add_parser("crawl", help="Crawl public Reddit content via Scrapling")
    add_crawl_flags(p_crawl)

    # Analyze
    p_analyze = subparsers.add_parser("analyze", help="Classify pain candidates with Cerebras Qwen")
    p_analyze.add_argument("--concurrency", type=int, default=4, help="LLM request concurrency")
    p_analyze.add_argument("--mock-ai", action="store_true", help="Use offline mock AI responses")

    # Cluster
    p_cluster = subparsers.add_parser("cluster", help="Group pain signals using semantic embeddings")

    # Score
    p_score = subparsers.add_parser("score", help="Compute deterministic opportunity scores")
    p_score.add_argument("--days", type=int, default=30, help="Time window for trends")

    # Report
    p_report = subparsers.add_parser("report", help="Generate Markdown, CSV, and JSON reports")
    p_report.add_argument("--top", type=int, default=15, help="Number of top problems to include")

    # Run (Full Pipeline)
    p_run = subparsers.add_parser("run", help="Run the full end-to-end discovery pipeline")
    add_crawl_flags(p_run)
    p_run.add_argument("--mock-ai", action="store_true", help="Use offline mock AI responses")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "crawl":
        cmd_crawl(args)
    elif args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "cluster":
        cmd_cluster(args)
    elif args.command == "score":
        cmd_score(args)
    elif args.command == "report":
        cmd_report(args)
    elif args.command == "run":
        cmd_run(args)


if __name__ == "__main__":
    main()
