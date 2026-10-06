from scrapling.parser import Selector
from pain_radar.crawler.selectors import extract_posts_from_feed, extract_post_details
from pain_radar.storage.models import RedditPostModel
from tests.fixtures.sample_data import SAMPLE_REDDIT_FEED_HTML, SAMPLE_REDDIT_POST_HTML


def test_extract_posts_from_feed():
    sel = Selector(content=SAMPLE_REDDIT_FEED_HTML)
    posts = extract_posts_from_feed(sel, subreddit="SaaS")

    assert len(posts) == 2
    p1 = posts[0]
    assert p1.post_id == "t3_abc123"
    assert "invoice reconciliation" in p1.title.lower()
    assert p1.score == 42
    assert p1.comment_count == 15
    assert p1.permalink == "https://www.reddit.com/r/SaaS/comments/abc123/invoice_reconciliation/"

    p2 = posts[1]
    assert p2.post_id == "t3_def456"
    assert p2.score == 18


def test_extract_post_details():
    sel = Selector(content=SAMPLE_REDDIT_POST_HTML)
    dummy_post = RedditPostModel(
        post_id="t3_abc123",
        subreddit="SaaS",
        title="Sample Title",
        permalink="https://www.reddit.com/r/SaaS/comments/abc123/",
    )

    enriched_post, comments = extract_post_details(sel, dummy_post, max_comments=10)

    assert "matching Stripe invoices to QuickBooks" in enriched_post.body
    assert len(comments) == 2
    assert comments[0].comment_id == "t1_comm1"
    assert comments[0].score == 12
    assert "multi-currency" in comments[0].body
    assert comments[1].comment_id == "t1_comm2"
    assert "offshore VA" in comments[1].body
