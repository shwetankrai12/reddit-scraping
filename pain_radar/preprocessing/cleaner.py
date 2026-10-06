import re
from typing import Any, Dict, List, Optional
from pain_radar.storage.db import Database


SPAM_PATTERNS = [
    r"\b(telegram|t\.me\/|whatsapp\b|crypto\s*pump|airdrop|free\s*bitcoin|forex\s*trading)\b",
    r"\b(hire\s*me|dm\s*me\s*for\s*services|check\s*out\s*my\s*link|upvote\s*for\s*upvote)\b",
]

PROMO_PATTERNS = [
    r"\b(we\s+just\s+launched|i\s+built\s+a\s+tool|check\s+out\s+my\s+saas|use\s+discount\s+code)\b",
    r"\b(launching\s+on\s+product\s+hunt|giveaway|sign\s+up\s+here\s*:\s*https?:\/\/)\b",
]

BOT_PATTERNS = [
    r"\bi\s+am\s+a\s+bot\b",
    r"\bautomoderator\b",
    r"\bthis\s+action\s+was\s+performed\s+automatically\b",
]


class Preprocessor:
    def __init__(self, db: Database, max_context_chars: int = 3500):
        self.db = db
        self.max_context_chars = max_context_chars

    def is_spam_or_promo(self, text: str) -> bool:
        lower = text.lower()
        for pat in SPAM_PATTERNS:
            if re.search(pat, lower):
                return True
        for pat in PROMO_PATTERNS:
            if re.search(pat, lower):
                return True
        return False

    def is_bot_or_deleted(self, text: str) -> bool:
        lower = text.lower()
        if "[deleted]" in lower or "[removed]" in lower:
            return True
        for pat in BOT_PATTERNS:
            if re.search(pat, lower):
                return True
        return False

    def clean_text(self, text: str) -> str:
        if not text:
            return ""
        # Remove markdown image embeds and excessive URLs
        text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
        text = re.sub(r"\n\s*\n+", "\n\n", text)
        return text.strip()

    def prepare_post_candidates(self) -> List[Dict[str, Any]]:
        raw_posts = self.db.get_all_posts()
        candidates: List[Dict[str, Any]] = []
        seen_titles = set()

        for post in raw_posts:
            title = self.clean_text(post.get("title", ""))
            body = self.clean_text(post.get("body", ""))
            post_id = post.get("post_id", "")
            subreddit = post.get("subreddit", "")
            permalink = post.get("permalink", "")
            score = post.get("score", 0)

            # Skip empty or deleted
            if not title:
                continue
            if self.is_bot_or_deleted(title) or self.is_bot_or_deleted(body):
                continue

            # Title deduplication
            norm_title = title.lower().strip()
            if norm_title in seen_titles:
                continue
            seen_titles.add(norm_title)

            # Filter short / spam
            combined = f"{title} {body}"
            if len(combined) < 25:
                continue
            if self.is_spam_or_promo(combined):
                continue

            # Fetch top comments for context
            comments = self.db.get_post_comments(post_id)
            filtered_comments: List[str] = []
            for c in comments:
                c_body = self.clean_text(c.get("body", ""))
                if not c_body or self.is_bot_or_deleted(c_body) or self.is_spam_or_promo(c_body):
                    continue
                if len(c_body) >= 20:
                    filtered_comments.append(c_body)
                if len(filtered_comments) >= 4:
                    break

            # Build structured context representation
            context_parts = [
                f"TITLE: {title}",
            ]
            if body:
                context_parts.append(f"POST BODY:\n{body}")

            if filtered_comments:
                comments_text = "\n---\n".join(filtered_comments)
                context_parts.append(f"RELEVANT COMMENTS:\n{comments_text}")

            full_context = "\n\n".join(context_parts)
            if len(full_context) > self.max_context_chars:
                full_context = full_context[: self.max_context_chars] + "... [truncated]"

            candidates.append({
                "post_id": post_id,
                "subreddit": subreddit,
                "reddit_url": permalink,
                "title": title,
                "body": body,
                "full_context": full_context,
                "score": score,
                "timestamp": post.get("timestamp", ""),
            })

        return candidates
