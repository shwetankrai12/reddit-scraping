import logging
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set
from urllib.parse import quote_plus

from scrapling import StealthyFetcher
from pain_radar.crawler.selectors import extract_posts_from_feed, extract_post_details
from pain_radar.storage.db import Database
from pain_radar.storage.models import RedditPostModel, RedditCommentModel

logger = logging.getLogger(__name__)


class RedditSpider:
    def __init__(
        self,
        db: Database,
        subreddits: Optional[List[str]] = None,
        search_queries: Optional[List[str]] = None,
        limit_per_sub: int = 100,
        days: int = 30,
        max_comments: int = 20,
        delay_seconds: float = 1.0,
        headless: bool = True,
        fetch_details: bool = True,
    ):
        self.db = db
        self.subreddits = subreddits or ["SaaS", "startups", "smallbusiness"]
        self.search_queries = search_queries or []
        self.limit_per_sub = limit_per_sub
        self.days = days
        self.max_comments = max_comments
        self.delay_seconds = delay_seconds
        self.headless = headless
        self.fetch_details = fetch_details
        self.cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

    def _is_within_time_window(self, timestamp_str: str) -> bool:
        if not timestamp_str:
            return True
        try:
            # Handle ISO formats like 2026-10-06T10:06:56.954000+0000
            ts_clean = timestamp_str.replace("Z", "+00:00")
            if len(ts_clean) > 5 and ts_clean[-5] in ("+", "-") and ":" not in ts_clean[-5:]:
                ts_clean = ts_clean[:-2] + ":" + ts_clean[-2:]
            dt = datetime.fromisoformat(ts_clean)
            return dt >= self.cutoff_date
        except Exception:
            return True

    def crawl_subreddit_feed(self, subreddit: str, sort: str = "new", max_posts: int = 100) -> List[RedditPostModel]:
        logger.info(f"Crawling r/{subreddit} (sort: {sort}, target: {max_posts} posts)...")
        collected_posts: List[RedditPostModel] = []
        seen_ids: Set[str] = set()

        url = f"https://www.reddit.com/r/{subreddit}/{sort}/"
        try:
            resp = StealthyFetcher.fetch(
                url,
                headless=self.headless,
                timeout=20000,
                wait_selector="shreddit-post",
            )
            page_posts = extract_posts_from_feed(resp, subreddit, discovery_source=f"feed:{sort}")
            for p in page_posts:
                if p.post_id not in seen_ids and self._is_within_time_window(p.timestamp):
                    seen_ids.add(p.post_id)
                    collected_posts.append(p)
            time.sleep(self.delay_seconds)
        except Exception as e:
            logger.error(f"Error fetching initial page for r/{subreddit}: {e}")
            return collected_posts

        # Pagination using /svc/shreddit/community-more-posts/
        last_id = collected_posts[-1].post_id if collected_posts else None
        consecutive_empty = 0

        while len(collected_posts) < max_posts and last_id and consecutive_empty < 2:
            more_url = f"https://www.reddit.com/svc/shreddit/community-more-posts/{sort}/?name={subreddit}&after={last_id}"
            try:
                resp = StealthyFetcher.fetch(more_url, headless=self.headless)
                more_posts = extract_posts_from_feed(resp, subreddit, discovery_source=f"feed:{sort}")
                added = 0
                for p in more_posts:
                    if p.post_id not in seen_ids:
                        seen_ids.add(p.post_id)
                        last_id = p.post_id
                        if self._is_within_time_window(p.timestamp):
                            collected_posts.append(p)
                            added += 1
                        if len(collected_posts) >= max_posts:
                            break

                if added == 0:
                    consecutive_empty += 1
                else:
                    consecutive_empty = 0

                time.sleep(self.delay_seconds)
            except Exception as e:
                logger.warning(f"Error paginating r/{subreddit}: {e}")
                break

        logger.info(f"Collected {len(collected_posts)} posts from r/{subreddit} feed.")
        return collected_posts

    def crawl_subreddit_search(self, subreddit: str, query: str, max_posts: int = 30) -> List[RedditPostModel]:
        logger.info(f"Searching r/{subreddit} for '{query}'...")
        encoded_query = quote_plus(query)
        url = f"https://www.reddit.com/r/{subreddit}/search/?q={encoded_query}&sort=new"
        posts: List[RedditPostModel] = []
        seen_links = set()

        try:
            resp = StealthyFetcher.fetch(url, headless=self.headless)
            links = resp.css("a[href*='/comments/']")
            for link in links:
                href = link.attrib.get("href") or ""
                if not href or href in seen_links:
                    continue
                seen_links.add(href)

                permalink = href if href.startswith("http") else f"https://www.reddit.com{href}"
                title = link.get_all_text(strip=True) or query

                # Extract post_id from url
                parts = href.split("/comments/")
                if len(parts) > 1:
                    post_id = f"t3_{parts[1].split('/')[0]}"
                else:
                    post_id = f"t3_{uuid.uuid4().hex[:8]}"

                post = RedditPostModel(
                    post_id=post_id,
                    subreddit=subreddit,
                    title=title,
                    body="",
                    permalink=permalink,
                    discovery_source=f"search:{query}",
                )
                posts.append(post)
                if len(posts) >= max_posts:
                    break
            time.sleep(self.delay_seconds)
        except Exception as e:
            logger.warning(f"Error searching r/{subreddit} for '{query}': {e}")

        return posts

    def enrich_post(self, post: RedditPostModel) -> tuple[RedditPostModel, List[RedditCommentModel]]:
        """
        Fetch the individual post page to extract the full body and comments.
        """
        try:
            resp = StealthyFetcher.fetch(
                post.permalink,
                headless=self.headless,
                timeout=20000,
                wait_selector="shreddit-post",
            )
            enriched_post, comments = extract_post_details(resp, post, max_comments=self.max_comments)
            time.sleep(self.delay_seconds)
            return enriched_post, comments
        except Exception as e:
            logger.debug(f"Failed to fetch details for {post.permalink}: {e}")
            return post, []

    def run_crawl(self) -> Dict[str, Any]:
        run_id = f"run_{int(time.time())}"
        start_time = datetime.utcnow().isoformat()
        total_posts_saved = 0
        total_comments_saved = 0

        logger.info(f"=== Starting Crawl Run {run_id} ===")
        logger.info(f"Subreddits: {', '.join(self.subreddits)}")
        logger.info(f"Limit per subreddit: {self.limit_per_sub}, Days cutoff: {self.days}")

        all_collected_posts: List[RedditPostModel] = []
        seen_global_ids: Set[str] = set()

        for sub in self.subreddits:
            sub_posts: List[RedditPostModel] = []

            # 1. Crawl /new feed
            new_posts = self.crawl_subreddit_feed(sub, sort="new", max_posts=self.limit_per_sub)
            for p in new_posts:
                if p.post_id not in seen_global_ids:
                    seen_global_ids.add(p.post_id)
                    sub_posts.append(p)

            # 2. Search queries if provided and limit not reached
            remaining = self.limit_per_sub - len(sub_posts)
            if remaining > 0 and self.search_queries:
                for q in self.search_queries[:3]:
                    if remaining <= 0:
                        break
                    search_results = self.crawl_subreddit_search(sub, q, max_posts=min(remaining, 15))
                    for p in search_results:
                        if p.post_id not in seen_global_ids:
                            seen_global_ids.add(p.post_id)
                            sub_posts.append(p)
                            remaining -= 1

            # Enforce limit per subreddit
            if len(sub_posts) > self.limit_per_sub:
                sub_posts = sub_posts[:self.limit_per_sub]

            # Save initial posts metadata
            self.db.save_posts_batch(sub_posts)
            total_posts_saved += len(sub_posts)
            all_collected_posts.extend(sub_posts)
            logger.info(f"Saved {len(sub_posts)} initial post records for r/{sub}")

        # 3. Enrich posts with full body & comments
        if self.fetch_details:
            logger.info(f"Enriching {len(all_collected_posts)} posts with body and comments...")
            for idx, post in enumerate(all_collected_posts):
                enriched, comments = self.enrich_post(post)
                self.db.save_post(enriched)
                if comments:
                    saved_c = self.db.save_comments_batch(comments)
                    total_comments_saved += saved_c

                if (idx + 1) % 10 == 0 or (idx + 1) == len(all_collected_posts):
                    logger.info(f"Enriched {idx + 1}/{len(all_collected_posts)} posts ({total_comments_saved} comments saved)")

        # Record run
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO crawl_runs (run_id, created_at, subreddits, total_posts, total_comments, status)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (
                run_id, start_time, ",".join(self.subreddits),
                total_posts_saved, total_comments_saved, "COMPLETED"
            ))
            conn.commit()

        logger.info(f"=== Crawl Completed: {total_posts_saved} posts, {total_comments_saved} comments ===")
        return {
            "run_id": run_id,
            "posts_count": total_posts_saved,
            "comments_count": total_comments_saved,
        }
