from pain_radar.preprocessing.cleaner import Preprocessor
from pain_radar.storage.db import Database
from pain_radar.storage.models import RedditPostModel, RedditCommentModel


def test_spam_and_promo_filtering(tmp_path):
    db = Database(tmp_path / "test.db")
    prep = Preprocessor(db)

    # Obvious spam
    assert prep.is_spam_or_promo("Join my telegram group for crypto pump signals!") is True
    # Promotional post
    assert prep.is_spam_or_promo("We just launched our new SaaS tool on Product Hunt today!") is True
    # Genuine pain
    assert prep.is_spam_or_promo("I spend 3 hours every Friday reconciling invoices in Excel") is False

    # Deleted / bot
    assert prep.is_bot_or_deleted("[deleted]") is True
    assert prep.is_bot_or_deleted("I am a bot. Contact moderators if you have issues.") is True
    assert prep.is_bot_or_deleted("Normal user text") is False


def test_prepare_candidates(tmp_path):
    db = Database(tmp_path / "test.db")
    prep = Preprocessor(db)

    post = RedditPostModel(
        post_id="t3_1",
        subreddit="SaaS",
        title="I spend hours reconciling QuickBooks and Stripe",
        body="Does anyone know an automated way to do this? Excel is driving me crazy.",
        permalink="https://reddit.com/r/SaaS/comments/1/",
        score=25,
    )
    db.save_post(post)

    comm = RedditCommentModel(
        comment_id="c1",
        post_id="t3_1",
        body="I have the exact same problem. Tried 3 tools and none work.",
        score=10,
    )
    db.save_comments_batch([comm])

    candidates = prep.prepare_post_candidates()
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand["post_id"] == "t3_1"
    assert "TITLE:" in cand["full_context"]
    assert "POST BODY:" in cand["full_context"]
    assert "RELEVANT COMMENTS:" in cand["full_context"]
    assert "reconciling QuickBooks" in cand["full_context"]
