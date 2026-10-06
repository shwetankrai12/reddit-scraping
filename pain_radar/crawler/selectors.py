from typing import Any, Dict, List, Optional
from scrapling.parser import Selector
from pain_radar.storage.models import RedditPostModel, RedditCommentModel


def extract_posts_from_feed(selector: Selector, subreddit: str, discovery_source: str = "feed") -> List[RedditPostModel]:
    posts: List[RedditPostModel] = []
    shreddit_posts = selector.css("shreddit-post")

    for p in shreddit_posts:
        try:
            attribs = p.attrib
            post_id = attribs.get("id") or ""
            if not post_id:
                continue

            title = attribs.get("post-title") or ""
            permalink = attribs.get("permalink") or ""
            if not permalink.startswith("http"):
                permalink = f"https://www.reddit.com{permalink}"

            try:
                score = int(attribs.get("score") or "0")
            except (ValueError, TypeError):
                score = 0

            try:
                comment_count = int(attribs.get("comment-count") or "0")
            except (ValueError, TypeError):
                comment_count = 0

            timestamp = attribs.get("created-timestamp") or ""
            post_type = attribs.get("post-type") or "text"

            post = RedditPostModel(
                post_id=post_id,
                subreddit=subreddit,
                title=title,
                body="",
                timestamp=timestamp,
                score=score,
                comment_count=comment_count,
                permalink=permalink,
                post_type=post_type,
                discovery_source=discovery_source,
            )
            posts.append(post)
        except Exception:
            continue

    return posts


def extract_post_details(selector: Selector, post: RedditPostModel, max_comments: int = 25) -> tuple[RedditPostModel, List[RedditCommentModel]]:
    # Extract body text if present
    body_el = selector.css("div[slot='text-body']")
    if body_el:
        post.body = body_el[0].get_all_text(strip=True)
    else:
        # Fallback to general paragraph selection inside post container
        p_elems = selector.css("div[data-click-id='text'] p, shreddit-post p")
        if p_elems:
            post.body = "\n".join([p.get_all_text(strip=True) for p in p_elems if p.get_all_text(strip=True)])

    # Extract comments
    comment_elements = selector.css("shreddit-comment")
    comments: List[RedditCommentModel] = []

    for c in comment_elements[:max_comments]:
        try:
            attribs = c.attrib
            comment_id = attribs.get("thingid") or attribs.get("id") or ""
            if not comment_id:
                continue

            try:
                score = int(attribs.get("score") or "0")
            except (ValueError, TypeError):
                score = 0

            timestamp = attribs.get("created-timestamp") or ""
            parent_id = attribs.get("parentid") or attribs.get("parent-id")

            c_body = c.css("div[slot='comment']")
            if c_body:
                body_text = c_body[0].get_all_text(strip=True)
            else:
                body_text = c.get_all_text(strip=True)

            if body_text:
                comments.append(RedditCommentModel(
                    comment_id=comment_id,
                    post_id=post.post_id,
                    body=body_text,
                    timestamp=timestamp,
                    score=score,
                    parent_id=parent_id,
                ))
        except Exception:
            continue

    return post, comments
