SAMPLE_REDDIT_FEED_HTML = """
<html>
<body>
  <shreddit-feed>
    <shreddit-post
      id="t3_abc123"
      post-title="How do you handle invoice reconciliation without spending hours every week?"
      score="42"
      comment-count="15"
      created-timestamp="2026-10-01T12:00:00+0000"
      permalink="/r/SaaS/comments/abc123/invoice_reconciliation/"
      post-type="text"
      subreddit-prefixed-name="r/SaaS"
    ></shreddit-post>
    <shreddit-post
      id="t3_def456"
      post-title="Looking for an alternative to Jira for small 5-person agencies"
      score="18"
      comment-count="8"
      created-timestamp="2026-09-25T14:30:00+0000"
      permalink="/r/startups/comments/def456/jira_alternative/"
      post-type="text"
      subreddit-prefixed-name="r/startups"
    ></shreddit-post>
  </shreddit-feed>
</body>
</html>
"""

SAMPLE_REDDIT_POST_HTML = """
<html>
<body>
  <shreddit-post
    id="t3_abc123"
    post-title="How do you handle invoice reconciliation without spending hours every week?"
    score="42"
    comment-count="2"
    created-timestamp="2026-10-01T12:00:00+0000"
    permalink="/r/SaaS/comments/abc123/invoice_reconciliation/"
  >
    <div slot="text-body">
      I spend three hours every single Friday matching Stripe invoices to QuickBooks records.
      QuickBooks constantly loses the fee breakdown and we end up doing everything manually in Excel.
      Does anyone have a tool or workaround that actually works?
    </div>
  </shreddit-post>

  <shreddit-comment
    thingid="t1_comm1"
    score="12"
    created-timestamp="2026-10-01T13:00:00+0000"
  >
    <div slot="comment">
      Same here. We have tried three different integration apps and all of them fail when there are refunds or multi-currency charges.
    </div>
  </shreddit-comment>

  <shreddit-comment
    thingid="t1_comm2"
    score="5"
    created-timestamp="2026-10-01T14:00:00+0000"
  >
    <div slot="comment">
      I currently pay an offshore VA $400/mo just to do this manual spreadsheet matching. Would happily pay for a tool that just solves this.
    </div>
  </shreddit-comment>
</body>
</html>
"""
